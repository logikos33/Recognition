"""Empurra os segmentos HLS gerados localmente pro endpoint da nuvem (LV-1).

Contrato: POST /api/v1/edge/live-view/<camera_id>/segment, multipart
`file` + form `filename`, auth pelo bearer auto-assinado do device
(escopo `stream:write`) — mesma direção outbound de todo o resto do agente,
nenhuma porta nova exposta no site (ADR-0020).

A nuvem guarda cada arquivo em Redis com TTL curto. Playlist e segmentos são
empurrados APENAS quando mudam (cache por nome+mtime+tamanho) — o TTL de 20s
cobre com folga a cadência real de mudança (~2s), e cada request a mais tem
custo do outro lado: a API roda com um worker gunicorn só e `--max-requests`,
então tráfego contínuo recicla o worker (ver docstring de live_view_loop.py).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 10.0
_PLAYLIST_SUFFIX = ".m3u8"
# Segmento sem escrita há esse tempo é considerado fechado pelo ffmpeg.
# Segmento dura ~1-2s, então 1s de quietude é sinal seguro.
_SETTLE_SECONDS = 1.0


class SegmentPushError(Exception):
    """A nuvem rejeitou, ou está inalcançável para, um push de segmento."""


def fetch_wanted_cameras(
    http_client: Any,
    api_base_url: str,
    bearer: str,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> list[str]:
    """camera_ids com espectador ativo agora (LV-3). Erro -> SegmentPushError.

    Um request só por ciclo pro device inteiro (não por câmera), e só quando
    NÃO está transmitindo — durante a transmissão a resposta do push já
    carrega `still_wanted`.
    """
    url = f"{api_base_url.rstrip('/')}/api/v1/edge/live-view/wanted"
    try:
        resp = http_client.get(
            url, headers={"Authorization": f"Bearer {bearer}"}, timeout=timeout
        )
    except Exception as exc:
        raise SegmentPushError(f"consulta de espectadores falhou: {exc}") from exc
    if resp.status_code != 200:
        raise SegmentPushError(
            f"consulta de espectadores rejeitada: status={resp.status_code}"
        )
    return list((resp.json().get("data") or {}).get("camera_ids") or [])


def push_segment(
    http_client: Any,
    api_base_url: str,
    bearer: str,
    camera_id: str,
    filename: str,
    data: bytes,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> bool:
    """POSTa um arquivo HLS. Devolve `still_wanted` (LV-3) — se False, o
    espectador saiu e o caller deve parar o transcode dessa câmera.
    Levanta SegmentPushError em qualquer falha."""
    url = f"{api_base_url.rstrip('/')}/api/v1/edge/live-view/{camera_id}/segment"
    content_type = (
        "application/vnd.apple.mpegurl" if filename.endswith(_PLAYLIST_SUFFIX) else "video/mp2t"
    )
    try:
        resp = http_client.post(
            url,
            headers={"Authorization": f"Bearer {bearer}"},
            data={"filename": filename},
            files={"file": (filename, data, content_type)},
            timeout=timeout,
        )
    except Exception as exc:
        raise SegmentPushError(
            f"push falhou: camera={camera_id} file={filename} err={exc}"
        ) from exc

    if resp.status_code != 201:
        raise SegmentPushError(
            f"push rejeitado: camera={camera_id} file={filename} "
            f"status={resp.status_code} body={resp.text[:200]}"
        )

    # Default True: nuvem antiga (sem o campo) mantém o comportamento anterior
    # de transmitir — nunca derruba o stream por causa de resposta inesperada.
    try:
        return bool((resp.json().get("data") or {}).get("still_wanted", True))
    except Exception:
        return True


class PushedFileCache:
    """Lembra o que já foi empurrado, pra não reenviar arquivo inalterado.

    Vale para a playlist TAMBÉM (correção de custo): a versão anterior
    re-empurrava o .m3u8 a todo tick "pra renovar o TTL", mas o tick é de
    0,5s e a playlist só muda a cada ~2s (um segmento) — eram 4 pushes por
    mudança real. Como o TTL na nuvem é de 20s, empurrar só na mudança
    mantém ~10x de margem, e ainda dá o comportamento certo quando o FFmpeg
    trava: a playlist para de mudar, expira, e o player recebe 404 em vez de
    ficar tocando um stream morto.

    Assinatura por (mtime, tamanho): o FFmpeg recicla nomes de segmento com
    delete_segments, então o mesmo nome pode voltar com conteúdo novo.
    """

    def __init__(self, max_entries: int = 64) -> None:
        self._seen: dict[str, tuple[float, int]] = {}
        self._max_entries = max_entries

    def is_settling(self, path: Path, now: float | None = None) -> bool:
        """`.ts` ainda "quente" (o ffmpeg pode anexar os últimos bytes).

        Exposto separado de `should_push` para o chamador poder SEGURAR a
        playlist que anuncia este segmento: a nuvem só deve anunciar `.ts`
        que já está no Redis (correção estrutural dos 425 — antes a playlist
        subia primeiro e cada segmento novo abria 1–3s de janela em que o
        manifesto anunciava um arquivo inexistente).
        """
        if path.name.endswith(_PLAYLIST_SUFFIX):
            return False
        try:
            stat = path.stat()
        except OSError:
            return False
        age = (time.time() if now is None else now) - stat.st_mtime
        return age < _SETTLE_SECONDS

    def should_push(self, path: Path, now: float | None = None) -> bool:
        try:
            stat = path.stat()
        except OSError:
            return False

        # Segmento ainda "quente" não sobe: o ffmpeg registra o .ts na playlist
        # e AINDA anexa os últimos bytes. Sem esta espera, o mesmo segmento ia
        # duas vezes — medido em campo: stream77.ts subiu com 276729 e depois
        # com 276760 (31 bytes a mais), dobrando banda e request à toa.
        # A playlist é pequena e precisa ser reenviada quando muda, então não
        # passa por esta regra.
        if self.is_settling(path, now=now):
            return False

        signature = (stat.st_mtime, stat.st_size)
        return self._seen.get(path.name) != signature

    def mark_pushed(self, path: Path) -> None:
        try:
            stat = path.stat()
        except OSError:
            return
        self._seen[path.name] = (stat.st_mtime, stat.st_size)
        # Cap simples: o FFmpeg recicla nomes com delete_segments, então o
        # cache não deveria crescer — mas um teto evita vazamento se crescer.
        if len(self._seen) > self._max_entries:
            for name in list(self._seen)[: len(self._seen) - self._max_entries]:
                self._seen.pop(name, None)

    def forget_all(self) -> None:
        self._seen.clear()
