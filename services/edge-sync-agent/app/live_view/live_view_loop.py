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
  - ocioso: 1 request por tick, pro device INTEIRO (não por câmera);
  - transmitindo: ZERO poll — a resposta do próprio push traz `still_wanted`.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from typing import Any, Protocol

import httpx

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
_DEFAULT_SEGMENT_SECONDS = 1
_DEFAULT_LIST_SIZE = 3


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
    ) -> None:
        self._api_base_url = api_base_url
        self._token_source = token_source
        self._http = http_client if http_client is not None else httpx.Client()
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

    @property
    def camera_ids(self) -> list[str]:
        return list(self._transcoders)

    def _refresh_wanted(self) -> None:
        """Consulta quem tem espectador — suprimido enquanto já transmite.

        Transmitindo, a resposta do próprio push já traz `still_wanted`, então
        o poll é dispensável (zero request extra durante a transmissão).

        A supressão exige `self._wanted` não-vazio de propósito: sem isso, um
        transcoder rodando com `_wanted` ainda vazio (primeiro tick) nunca
        aprenderia quem quer assistir e seria derrubado no mesmo tick.
        """
        if self._wanted and self._streaming:
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
        self._refresh_wanted()

        for camera_id, transcoder in self._transcoders.items():
            wanted = camera_id in self._wanted

            if not wanted:
                if transcoder.is_running():
                    logger.info("live_view_stopping camera=%s (sem espectador)", camera_id)
                    transcoder.stop()
                    self._caches[camera_id].forget_all()
                continue

            if not transcoder.is_running():
                tail = transcoder.stderr_tail()
                if tail:
                    logger.warning(
                        "live_view_ffmpeg_died camera=%s stderr=%s", camera_id, tail
                    )
                # Numeração de segmento reinicia junto com o FFmpeg — esquecer
                # o cache evita pular um segmento novo que reusou um nome antigo.
                self._caches[camera_id].forget_all()
                try:
                    logger.info("live_view_starting camera=%s (espectador ativo)", camera_id)
                    transcoder.start()
                except RecorderError as exc:
                    logger.warning("live_view_start_failed camera=%s err=%s", camera_id, exc)
                continue

            cache = self._caches[camera_id]
            for path in transcoder.list_ready_files():
                if not cache.should_push(path):
                    continue
                try:
                    data = path.read_bytes()
                except OSError:
                    continue  # arquivo sumiu entre o listar e o ler (delete_segments)
                if not data:
                    continue
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
                    continue
                cache.mark_pushed(path)
                if still_wanted is False:
                    # Espectador saiu — descobrimos pela resposta do push, sem
                    # gastar um request só pra perguntar.
                    self._wanted.discard(camera_id)
                    break

    @property
    def _streaming(self) -> bool:
        return any(t.is_running() for t in self._transcoders.values())

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


def build_live_view_loop_from_env(
    recorder: Any,
    token_source: TokenSource,
    env: dict[str, str] | None = None,
) -> LiveViewLoop:
    """Monta o loop a partir do MESMO RECORDER_CHANNEL_MAP que o coletor usa.

    A URL ao vivo vem do próprio RecorderClient (`_build_live_url` /
    `_get_stream_uri`) — mesma URL provada pelo `capture_frame()` contra o NVR
    real, sem reimplementar dialeto de fabricante aqui.

    LIVE_VIEW_WORK_DIR (default: um tempdir do SO) é buffer transitório de
    poucos MB (delete_segments + list_size 3) — ADR-0033/0045.
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
        poll_interval_s=float(
            source.get("LIVE_VIEW_POLL_INTERVAL_S", str(_DEFAULT_POLL_INTERVAL_S))
        ),
        segment_seconds=int(
            source.get("LIVE_VIEW_SEGMENT_SECONDS", str(_DEFAULT_SEGMENT_SECONDS))
        ),
        list_size=int(source.get("LIVE_VIEW_LIST_SIZE", str(_DEFAULT_LIST_SIZE))),
        video_codec=source.get("LIVE_VIEW_VIDEO_CODEC", "copy"),
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
