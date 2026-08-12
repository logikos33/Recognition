"""LiveViewLoop — mantém o transcode local vivo e empurra os segmentos (LV-2).

Fecha o caminho que a LV-1 abriu do lado da nuvem: FFmpeg local
(hls_transcoder) -> POST /api/v1/edge/live-view/<id>/segment (segment_pusher)
-> Redis na nuvem -> serve_hls -> hls.js no navegador, SEM que a nuvem
precise alcançar a câmera (ADR-0020, task-060 "o modelo da RVB").

Processo próprio (unit systemd separada), mesmo padrão já usado pelo coletor
de frames e pelo updater OTA — reiniciável sem tocar identidade/heartbeat, e
carga de CPU (FFmpeg contínuo) isolada do daemon principal.

Reusa o `RECORDER_CHANNEL_MAP` como lista de câmeras e o
`RtspTimestampRecorderClient`/`OnvifRecorderClient` só pra construir a URL —
a mesma URL ao vivo que o `capture_frame()` já usa, provada contra o NVR real
da RVB. Sem duplicar a lógica de dialeto por fabricante.

LV-3 — sob demanda: só transmite câmera com espectador ativo. O sinal é a
chave `epi:stream:{camera_id}:active` que o resto do sistema JÁ mantém (o
botão "Iniciar Stream" cria; `serve_hls` renova a cada segmento que o player
pede), lida via `GET /api/v1/edge/live-view/wanted`.

Custo de request importa aqui, não só banda: a API roda com UM worker
gunicorn e `--max-requests`, então tráfego contínuo recicla o worker —
medido em campo, a versão contínua da LV-2 gerava ~2,5 req/s e reciclava o
worker a cada ~3min, o que derruba as conexões SocketIO. Por isso:
  - ocioso ou com QUALQUER câmera ociosa: 1 request por tick, pro device
    INTEIRO (não por câmera) — é o único jeito de descobrir espectador novo
    numa câmera que ainda não transmite;
  - TODAS as câmeras conhecidas transmitindo: ZERO poll — a resposta do
    próprio push traz `still_wanted` pra cada uma (D-36).

D-74 — push paralelo por câmera: o custo de request acima é sobre o POLL de
`wanted`, não sobre o push de segmento em si. O push era sequencial — 1
thread, todas as câmeras, um POST bloqueante por vez (timeout 10s) — e isso
media ~19s de ciclo por câmera contra segmentos que só viviam 3s no disco
(hls_time 1 × hls_list_size 3 + delete_segments): ~16 de cada 19 segmentos
eram apagados do disco antes de qualquer tentativa de envio, e o live view
congelava ciclicamente. Cada câmera agora sobe num worker thread próprio
(`ThreadPoolExecutor`, teto `LIVE_VIEW_MAX_PARALLEL_PUSHES`), então o regime
de estado estacionário com N espectadoras passa a ~N req/s de push (1 POST
por câmera por tick) em vez de 1 câmera a cada 19s. Com 8 câmeras nesse
regime (~8 req/s de push, mais o poll ocasional), o `--max-requests=100000`
(+jitter) da API recicla o worker a cada ~3,5h — aceitável — e o piso de
rate-limit por IP (900/min) ainda folga ~1,9x sobre os ~480 req/min de
regime.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Protocol

import httpx

from ..monitoring.status_file import build_live_view_status_from_env
from ..recorder_client import RecorderError
from .hls_transcoder import HlsTranscoder, build_output_dir
from .segment_pusher import (
    PushedFileCache,
    SegmentPushError,
    fetch_wanted_cameras,
    push_segment,
)

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://api-v3-desenvolvimento.up.railway.app"  # DEV — nunca produção
# 2s: ocioso é 1 request a cada 2s (0,5 req/s pro device inteiro); com
# espectador, é a cadência de varredura por segmento novo — segmento dura
# ~1-2s, então não perde nada. Não baixar sem medir: cada tick ocioso é um
# request na API (ver docstring do módulo).
_DEFAULT_POLL_INTERVAL_S = 2.0
# D-74: 2s × 10 segmentos = janela de 20s de vida por segmento no disco (era
# 1s × 3 = 3s — margem zero contra o antigo uploader sequencial). Com
# `-c:v copy` o `hls_time` é PISO preso ao GOP da câmera (o ffmpeg só corta
# em keyframe, nunca no meio de um GOP maior) — o valor real pode passar de
# 2s, o que só aumenta a janela.
#
# A janela anunciada (list_size × segment_seconds) TEM que ficar ABAIXO do
# `_HLS_SEGMENT_TTL` do lado da nuvem (services/api) — o TTL sobe 20s->30s
# em PR separado; se um dos dois lados mudar sem o outro, a margem some.
_DEFAULT_SEGMENT_SECONDS = 2
_DEFAULT_LIST_SIZE = 10
# 8 é o PISO histórico (D-74, site com 8 câmeras) — não mais o default fixo.
# O default efetivo é PROPORCIONAL ao número de câmeras conhecidas do site
# (_proportional_max_pushes, rodada 11/08/D-85): com o iNVD cheio o site vai a
# 29 câmeras, e um teto fixo de 8 traria o rodízio de volta (o bug dos 19s por
# ciclo, #325–#331, em versão mais curta). LIVE_VIEW_MAX_PARALLEL_PUSHES no
# env continua mandando quando setado explicitamente. O lado da nuvem
# acompanha: bucket dedicado edge-live-ingest dimensionado pra 32 canais
# (services/api/app/api/v1/edge/routes.py, EDGE_LIVE_INGEST_IP_LIMIT).
_DEFAULT_MAX_PARALLEL_PUSHES = 8
# Folga acima do nº de câmeras: playlist e segmento da mesma câmera podem
# enfileirar colados, e um slot extra evita que o último push do ciclo espere.
_PUSH_SLOTS_HEADROOM = 2


def _proportional_max_pushes(camera_count: int) -> int:
    """Teto de pushes proporcional ao site, nunca abaixo do piso histórico.

    Um número fixo envelhece: 8 nasceu com 8 câmeras (D-74) e viraria rodízio
    silencioso com 29 (D-85). Proporcional = todas as câmeras conhecidas podem
    empurrar ao mesmo tempo, com folga — o custo é 1 thread ociosa por câmera
    sem espectador, barato no Orin; o rodízio custa live view congelando.
    """
    return max(_DEFAULT_MAX_PARALLEL_PUSHES, camera_count + _PUSH_SLOTS_HEADROOM)


class TokenSource(Protocol):
    def get_bearer(self, ttl_s: int = 300) -> str: ...


class LiveViewLoop:
    """Um transcoder por câmera + push contínuo dos segmentos gerados."""

    def __init__(
        self,
        camera_urls: dict[str, str],
        api_base_url: str,
        token_source: TokenSource,
        work_dir: str,
        http_client: Any = None,
        poll_interval_s: float = _DEFAULT_POLL_INTERVAL_S,
        segment_seconds: int = _DEFAULT_SEGMENT_SECONDS,
        list_size: int = _DEFAULT_LIST_SIZE,
        video_codec: str = "copy",
        push_fn: Any = push_segment,
        fetch_wanted_fn: Any = fetch_wanted_cameras,
        max_parallel_pushes: int = _DEFAULT_MAX_PARALLEL_PUSHES,
        executor: Any = None,
        status: Any = None,
    ) -> None:
        self._api_base_url = api_base_url
        self._token_source = token_source
        self._owns_executor = executor is None
        if http_client is not None:
            self._http = http_client
        else:
            # Um push por câmera em voo ao mesmo tempo (no máximo
            # max_parallel_pushes) + folga pro poll de `wanted` — evita que o
            # pool de conexões do httpx vire gargalo antes do executor.
            self._http = httpx.Client(
                limits=httpx.Limits(
                    max_connections=max_parallel_pushes + 4,
                    max_keepalive_connections=max_parallel_pushes,
                )
            )
        self._poll_interval_s = poll_interval_s
        self._push_fn = push_fn
        self._fetch_wanted_fn = fetch_wanted_fn
        self._wanted: set[str] = set()
        self._transcoders: dict[str, HlsTranscoder] = {
            camera_id: HlsTranscoder(
                camera_id=camera_id,
                rtsp_url=rtsp_url,
                output_dir=build_output_dir(work_dir, camera_id),
                segment_seconds=segment_seconds,
                list_size=list_size,
                video_codec=video_codec,
            )
            for camera_id, rtsp_url in camera_urls.items()
        }
        self._caches: dict[str, PushedFileCache] = {
            camera_id: PushedFileCache() for camera_id in camera_urls
        }
        self._executor = (
            executor
            if executor is not None
            else ThreadPoolExecutor(
                max_workers=max_parallel_pushes, thread_name_prefix="lv-push"
            )
        )
        # No máximo UM job em voo por câmera — enquanto o job da câmera não
        # terminou, o tick pula o lifecycle dela inteiro (nada de stop/start
        # concorrente com o worker thread que está lendo/empurrando arquivos
        # dela). Mutado SÓ no thread principal (via _collect_finished_pushes).
        self._push_futures: dict[str, Future] = {}
        # /monitoring (opcional): LiveViewStatus — métricas por câmera num
        # artefato local que o coletor de monitoramento lê. None = sem custo,
        # comportamento idêntico ao anterior.
        self._status = status

    @property
    def camera_ids(self) -> list[str]:
        return list(self._transcoders)

    def _refresh_wanted(self) -> None:
        """Consulta quem tem espectador — suprimido só quando não há mais
        candidata ociosa pro poll descobrir.

        Com TODAS as câmeras conhecidas já transmitindo, a resposta do
        próprio push já traz `still_wanted`, então o poll é dispensável (zero
        request extra). Mas com qualquer câmera ociosa, ela nunca passa pelo
        push — só o poll pode revelar um espectador novo nela — então o tick
        continua consultando normalmente (D-36: com 1 de N câmeras
        transmitindo, a supressão antiga travava o `_wanted` para sempre e
        nenhuma câmera ociosa era descoberta até TODAS perderem espectador).

        A supressão exige `self._wanted` não-vazio de propósito: sem isso, um
        transcoder rodando com `_wanted` ainda vazio (primeiro tick) nunca
        aprenderia quem quer assistir e seria derrubado no mesmo tick.
        """
        if self._wanted and self._all_known_cameras_streaming:
            return
        try:
            self._wanted = set(
                self._fetch_wanted_fn(
                    self._http, self._api_base_url, self._token_source.get_bearer()
                )
            )
        except SegmentPushError as exc:
            logger.warning("live_view_wanted_poll_failed err=%s", exc)

    def tick(self) -> None:
        # Coleta antes E depois: antes, pra liberar câmeras cujo job já
        # terminou (senão o lifecycle delas ficaria adiado até o PRÓXIMO
        # tick à toa); depois, pra recolher o resultado do job que este tick
        # acabou de submeter sem esperar um ciclo inteiro de poll_interval_s.
        self._collect_finished_pushes()
        self._refresh_wanted()

        for camera_id, transcoder in self._transcoders.items():
            if camera_id in self._push_futures:
                # Job em voo pra essa câmera — lifecycle (stop/start) e nova
                # submissão esperam ele terminar. Evita o worker thread ler
                # arquivos de um transcoder que o thread principal acabou de
                # derrubar/reiniciar por baixo dele.
                continue

            wanted = camera_id in self._wanted

            if not wanted:
                if transcoder.is_running():
                    logger.info("live_view_stopping camera=%s (sem espectador)", camera_id)
                    transcoder.stop()
                    self._caches[camera_id].forget_all()
                if self._status:
                    self._status.record_ffmpeg_state(camera_id, running=False, wanted=False)
                continue

            if not transcoder.is_running():
                tail = transcoder.stderr_tail()
                if tail:
                    logger.warning(
                        "live_view_ffmpeg_died camera=%s stderr=%s", camera_id, tail
                    )
                    if self._status:
                        # Morreu com espectador ativo e vai religar: cada
                        # incremento é uma reconexão RTSP (loop = câmera doente).
                        self._status.record_restart(camera_id)
                # Numeração de segmento reinicia junto com o FFmpeg — esquecer
                # o cache evita pular um segmento novo que reusou um nome antigo.
                self._caches[camera_id].forget_all()
                try:
                    logger.info("live_view_starting camera=%s (espectador ativo)", camera_id)
                    transcoder.start()
                except RecorderError as exc:
                    logger.warning("live_view_start_failed camera=%s err=%s", camera_id, exc)
                if self._status:
                    self._status.record_ffmpeg_state(
                        camera_id, running=transcoder.is_running(), wanted=True
                    )
                continue

            if self._status:
                self._status.record_ffmpeg_state(camera_id, running=True, wanted=True)
            self._push_futures[camera_id] = self._executor.submit(
                self._push_camera_files, camera_id
            )

        self._collect_finished_pushes()
        if self._status:
            self._status.maybe_write()

    def _push_camera_files(self, camera_id: str) -> bool:
        """Lê e empurra os arquivos prontos de UMA câmera. Roda num worker
        thread do `_executor` — nunca no thread principal. Devolve
        `viewer_left` (True se a resposta de algum push sinalizou que o
        espectador saiu).

        Thread-safety: `httpx.Client` é thread-safe (usado por múltiplos
        workers ao mesmo tempo); `token_source.get_bearer()` é stateless
        (assina um JWT novo sobre estado imutável, sem estado compartilhado
        mutável); o `PushedFileCache` desta câmera só é tocado pelo job desta
        câmera (nunca 2 jobs concorrentes na mesma câmera — ver `tick()`).
        `self._wanted` NÃO é tocado aqui — a mutação fica só no thread
        principal, em `_collect_finished_pushes`.
        """
        transcoder = self._transcoders[camera_id]
        cache = self._caches[camera_id]
        files = transcoder.list_ready_files()
        # Correção estrutural dos 425 (#308): a nuvem só pode ANUNCIAR (.m3u8)
        # segmento que JÁ está no Redis. Antes a playlist subia primeiro
        # e cada `.ts` novo abria 1–3s (settle + tick) de janela em que o
        # manifesto na nuvem apontava para um arquivo inexistente.
        #
        # Playlist consistente por construção (correção seguinte, medida em
        # soak de 20min: 425 em 17% das requests de vídeo, 527 segmentos
        # distintos, 526/527 resolvidos ~1,7s depois — o navegador sabia do
        # segmento ANTES dele existir no Redis). Causa: o #308 segurava a
        # playlist INTEIRA (`hold_playlist`) quando qualquer segmento listado
        # não tinha subido ainda (assentando na maioria dos ticks — segmento
        # de ~2s, tick de 2s), e MESMO SEM hold havia outra corrida: o gate
        # decidia sobre `list_ready_files()` do INÍCIO do job, mas o
        # `read_bytes()` da playlist rodava no FIM — no intervalo (com POSTs
        # de segmento no meio) o ffmpeg podia reescrever o `.m3u8` em disco
        # com um segmento recém-fechado, e o conteúdo NOVO subia sob a
        # decisão VELHA.
        #
        # Fix: (1) a playlist é lida em SNAPSHOT logo aqui (stat->read->stat;
        # descarta se mudou no meio da leitura — sobe no próximo tick); esse
        # snapshot é o ÚNICO conteúdo que este tick pode empurrar, nunca
        # relido na hora do push. (2) o hold por settling morre — em vez de
        # segurar a playlist inteira, ela sobe TRUNCADA ao maior PREFIXO de
        # segmentos que a nuvem já tem (`_build_prefix_playlist`), então a
        # playlist avança a cada tick em vez de ficar presa metade do tempo.
        # O fallback conservador (não empurrar) sobrevive só pra falha real:
        # push que falhou, arquivo sumido/vazio no meio do prefixo (nesses
        # casos o nome nunca entra no cache, então o prefixo simplesmente
        # para nele), ou truncamento que zeraria os segmentos (manifesto
        # vazio é pior que playlist velha).
        playlists = [p for p in files if p.name.endswith(".m3u8")]
        segments = [p for p in files if not p.name.endswith(".m3u8")]

        playlist_snapshots: dict[Path, bytes] = {}
        for path in playlists:
            try:
                stat1 = path.stat()
                data = path.read_bytes()
                stat2 = path.stat()
            except OSError:
                continue
            if (stat1.st_mtime, stat1.st_size) != (stat2.st_mtime, stat2.st_size):
                continue  # mudou durante a leitura — sobe íntegra no próximo tick
            playlist_snapshots[path] = data

        viewer_left = False
        for path in segments:
            if cache.is_settling(path):
                continue
            if not cache.should_push(path):
                continue
            try:
                data = path.read_bytes()
            except OSError:
                # arquivo sumiu entre o listar e o ler (delete_segments —
                # backpressure natural: segmento velho sem valor em vídeo ao
                # vivo, não há nada a recuperar aqui).
                continue
            if not data:
                continue
            push_started = time.monotonic()
            try:
                still_wanted = self._push_fn(
                    self._http,
                    self._api_base_url,
                    self._token_source.get_bearer(),
                    camera_id,
                    path.name,
                    data,
                )
            except SegmentPushError as exc:
                logger.warning("live_view_push_failed camera=%s err=%s", camera_id, exc)
                if self._status:
                    self._status.record_push_fail(camera_id)
                continue
            if self._status:
                self._status.record_push_ok(
                    camera_id, (time.monotonic() - push_started) * 1000
                )
            cache.mark_pushed(path)
            if still_wanted is False:
                viewer_left = True
                break

        if not viewer_left:
            for path, data in playlist_snapshots.items():
                built = _build_prefix_playlist(data, cache)
                if built is None:
                    continue
                content, digest = built
                if not cache.should_push_content(path.name, digest):
                    continue
                try:
                    still_wanted = self._push_fn(
                        self._http,
                        self._api_base_url,
                        self._token_source.get_bearer(),
                        camera_id,
                        path.name,
                        content,
                    )
                except SegmentPushError as exc:
                    logger.warning(
                        "live_view_push_failed camera=%s err=%s", camera_id, exc
                    )
                    if self._status:
                        self._status.record_push_fail(camera_id)
                    continue
                cache.mark_pushed_content(path.name, digest)
                if still_wanted is False:
                    viewer_left = True
                    break

        return viewer_left

    def _collect_finished_pushes(self) -> None:
        """Recolhe os jobs de push já concluídos. SÓ roda no thread
        principal — é aqui, e apenas aqui, que `self._wanted` é mutado como
        resultado de um push."""
        for camera_id in list(self._push_futures):
            future = self._push_futures[camera_id]
            if not future.done():
                continue
            del self._push_futures[camera_id]
            try:
                viewer_left = future.result()
            except Exception:
                logger.exception("live_view_push_job_failed camera=%s", camera_id)
                continue
            if viewer_left:
                # Espectador saiu — descobrimos pela resposta do push, sem
                # gastar um request só pra perguntar.
                self._wanted.discard(camera_id)

    @property
    def _all_known_cameras_streaming(self) -> bool:
        """True só quando não sobra candidata ociosa — nenhuma câmera
        conhecida se beneficiaria de um poll (todas já viraram push)."""
        return bool(self._transcoders) and all(
            t.is_running() for t in self._transcoders.values()
        )

    def run(self, stop_event: threading.Event) -> None:
        try:
            while not stop_event.is_set():
                self.tick()
                stop_event.wait(timeout=self._poll_interval_s)
        finally:
            self.stop_all()

    def stop_all(self) -> None:
        for transcoder in self._transcoders.values():
            transcoder.stop()
        if self._owns_executor:
            # Só desliga o executor se fomos nós que o criamos — um executor
            # injetado (teste, ou dono externo) não é nosso pra derrubar.
            self._executor.shutdown(wait=False, cancel_futures=True)


# ── Playlist consistente por construção ─────────────────────────────────────
#
# O gerador é o ffmpeg hls deste repo (`-hls_flags delete_segments+omit_endlist`,
# ver hls_transcoder.py) — sem PROGRAM-DATE-TIME, sem ENDLIST. Só o par
# `#EXTINF:...` + linha do URI do segmento importa pra truncar; qualquer outra
# linha/tag (cabeçalho, `#EXT-X-MEDIA-SEQUENCE`, etc.) é preservada como está.


def _playlist_segment_entries(text: str) -> tuple[list[str], list[tuple[int, int, str]]]:
    """Linhas da playlist (quebra preservada) + as entradas de segmento, na
    ordem em que aparecem: cada entrada é (índice da linha `#EXTINF`, índice
    da linha do URI, nome do segmento)."""
    lines = text.splitlines(keepends=True)
    entries: list[tuple[int, int, str]] = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("#EXTINF"):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and not lines[j].strip().startswith("#"):
                entries.append((i, j, lines[j].strip()))
                i = j + 1
                continue
        i += 1
    return lines, entries


def _truncate_playlist(lines: list[str], entries: list[tuple[int, int, str]], keep: int) -> str:
    """Remove do FIM os pares EXTINF+URI dos segmentos fora do prefixo
    `keep`. `#EXT-X-MEDIA-SEQUENCE` conta a partir da PRIMEIRA entrada, então
    cortar só o rabo não o invalida — e todas as demais linhas ficam intactas."""
    cutoff = len(lines) if keep >= len(entries) else entries[keep][0]
    return "".join(lines[:cutoff])


def _build_prefix_playlist(data: bytes, cache: PushedFileCache) -> tuple[bytes, str] | None:
    """Maior PREFIXO da playlist cujos segmentos já estão na nuvem (via
    `cache.has_pushed`). Devolve `(bytes_a_empurrar, digest_sha256)`, ou
    `None` se nada pode subir neste tick:

    - todos os segmentos listados já subiram -> devolve o snapshot inteiro
      (sem truncar);
    - só os do início subiram -> devolve o snapshot TRUNCADO ao prefixo;
    - nada subiu (prefixo vazio) -> None, fallback conservador;
    - um nome NÃO-enviado no meio com um enviado DEPOIS dele (buraco) -> None
      — não dá pra truncar o meio, só o rabo.

    Nunca devolve playlist com zero segmentos: o player trataria como
    manifesto vazio.
    """
    text = data.decode("utf-8", errors="replace")
    lines, entries = _playlist_segment_entries(text)
    if not entries:
        return None

    keep = 0
    for _, _, name in entries:
        if not cache.has_pushed(name):
            break
        keep += 1

    if any(cache.has_pushed(name) for _, _, name in entries[keep:]):
        return None
    if keep == 0:
        return None

    if keep == len(entries):
        content = data
    else:
        content = _truncate_playlist(lines, entries, keep).encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    return content, digest


def build_live_view_loop_from_env(
    recorder: Any,
    token_source: TokenSource,
    env: dict[str, str] | None = None,
) -> LiveViewLoop:
    """Monta o loop a partir do MESMO RECORDER_CHANNEL_MAP que o coletor usa.

    A URL ao vivo vem do próprio RecorderClient (`_build_live_url` /
    `_get_stream_uri`) — mesma URL provada pelo `capture_frame()` contra o NVR
    real, sem reimplementar dialeto de fabricante aqui.

    LIVE_VIEW_WORK_DIR (default: um tempdir do SO) é buffer transitório
    BOUNDED por câmera (delete_segments + list_size), não "poucos MB" fixo:
    8 câmeras × list_size 10 × ~1,2MB/segmento ≈ ~100MB no total (D-74;
    ADR-0033/0045 — cresce linear com o Nº DE CÂMERAS do site, não com
    LIVE_VIEW_MAX_PARALLEL_PUSHES (que só limita concorrência de upload, não
    retenção em disco) — revisitar a conta ao subir pra ~28 câmeras na RVB).

    LIVE_VIEW_MAX_PARALLEL_PUSHES: teto de câmeras empurrando segmento ao
    mesmo tempo (um `ThreadPoolExecutor`, um worker thread por câmera em voo).
    Quando AUSENTE no env, o default é proporcional ao site:
    `_proportional_max_pushes(len(camera_urls))` = nº de câmeras conhecidas
    + folga, piso 8 (D-74) — um fixo que "sobe junto com o site" na mão
    envelhece e traz o rodízio de volta (rodada 11/08/D-85). Setado no env,
    o valor explícito manda — continua sendo o botão de emergência pra
    estrangular upload sem redeploy. Nunca deixar sem teto.
    """
    source = env if env is not None else os.environ

    camera_urls = _resolve_camera_urls(recorder)
    if not camera_urls:
        raise ValueError(
            "Nenhuma câmera resolvida para live view — RECORDER_CHANNEL_MAP vazio "
            "ou RecorderClient sem suporte a URL ao vivo."
        )

    api_base_url = (source.get("EDGE_API_URL") or _DEFAULT_API_URL).rstrip("/")
    work_dir = source.get("LIVE_VIEW_WORK_DIR") or os.path.join(
        tempfile.gettempdir(), "recognition-live-view"
    )

    return LiveViewLoop(
        camera_urls=camera_urls,
        api_base_url=api_base_url,
        token_source=token_source,
        work_dir=work_dir,
        status=build_live_view_status_from_env(source),
        poll_interval_s=float(
            source.get("LIVE_VIEW_POLL_INTERVAL_S", str(_DEFAULT_POLL_INTERVAL_S))
        ),
        segment_seconds=int(
            source.get("LIVE_VIEW_SEGMENT_SECONDS", str(_DEFAULT_SEGMENT_SECONDS))
        ),
        list_size=int(source.get("LIVE_VIEW_LIST_SIZE", str(_DEFAULT_LIST_SIZE))),
        video_codec=source.get("LIVE_VIEW_VIDEO_CODEC", "copy"),
        max_parallel_pushes=(
            int(env_pushes)
            if (env_pushes := source.get("LIVE_VIEW_MAX_PARALLEL_PUSHES"))
            else _proportional_max_pushes(len(camera_urls))
        ),
    )


def _resolve_camera_urls(recorder: Any) -> dict[str, str]:
    """camera_id -> URL RTSP ao vivo, via o próprio RecorderClient.

    Usa os internos `_channel_map`/`_build_live_url`/`_get_stream_uri` porque o
    Protocol público (recorder_client.py) só expõe `capture_frame(camera_id)`,
    que já consome os bytes — o live view precisa da URL em si pra entregar ao
    FFmpeg. Alternativa seria alargar o Protocol; mantido local por enquanto
    pra não mexer no contrato que o resto do agente já depende.
    """
    channel_map = getattr(recorder, "_channel_map", None)
    if not channel_map:
        return {}

    urls: dict[str, str] = {}
    for camera_id, channel in channel_map.items():
        builder = getattr(recorder, "_build_live_url", None) or getattr(
            recorder, "_get_stream_uri", None
        )
        if builder is None:
            continue
        try:
            urls[camera_id] = builder(channel)
        except RecorderError as exc:
            logger.warning("live_view_url_failed camera=%s err=%s", camera_id, exc)
    return urls
