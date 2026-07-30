"""Empurra os segmentos HLS gerados localmente pro endpoint da nuvem (LV-1).

Contrato: POST /api/v1/edge/live-view/<camera_id>/segment, multipart
`file` + form `filename`, auth pelo bearer auto-assinado do device
(escopo `stream:write`) — mesma direção outbound de todo o resto do agente,
nenhuma porta nova exposta no site (ADR-0020).

A nuvem guarda cada arquivo em Redis com TTL curto, então re-empurrar a
playlist a cada ciclo é NECESSÁRIO (senão ela expira e o player quebra) —
não é desperdício. Segmentos `.ts` já enviados são pulados via cache de
(nome, mtime, tamanho): o mesmo nome pode reaparecer com conteúdo novo se o
FFmpeg reciclar a numeração, e aí precisa subir de novo.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 10.0
_PLAYLIST_SUFFIX = ".m3u8"


class SegmentPushError(Exception):
    """A nuvem rejeitou, ou está inalcançável para, um push de segmento."""


def push_segment(
    http_client: Any,
    api_base_url: str,
    bearer: str,
    camera_id: str,
    filename: str,
    data: bytes,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """POSTa um arquivo HLS. Levanta SegmentPushError em qualquer falha."""
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


class PushedFileCache:
    """Lembra o que já foi empurrado, pra não reenviar segmento inalterado.

    A playlist NUNCA é considerada "já enviada" — ela precisa ser re-empurrada
    a cada ciclo pra renovar o TTL do lado da nuvem (ver docstring do módulo).
    """

    def __init__(self, max_entries: int = 64) -> None:
        self._seen: dict[str, tuple[float, int]] = {}
        self._max_entries = max_entries

    def should_push(self, path: Path) -> bool:
        if path.name.endswith(_PLAYLIST_SUFFIX):
            return True
        try:
            stat = path.stat()
        except OSError:
            return False
        signature = (stat.st_mtime, stat.st_size)
        if self._seen.get(path.name) == signature:
            return False
        return True

    def mark_pushed(self, path: Path) -> None:
        if path.name.endswith(_PLAYLIST_SUFFIX):
            return
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
