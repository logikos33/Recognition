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

LIMITAÇÃO (escopo LV-2, não escondida): streaming CONTÍNUO enquanto o
processo estiver de pé — ainda não há start/stop sob demanda pelo botão da
UI (isso é LV-3, via `command_poller`). Pro piloto de 1-2 câmeras isso é
aceitável; pra escala vira desperdício de banda e precisa da LV-3.
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
from .segment_pusher import PushedFileCache, SegmentPushError, push_segment

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://api-v3-desenvolvimento.up.railway.app"  # DEV — nunca produção
_DEFAULT_POLL_INTERVAL_S = 0.5
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
    ) -> None:
        self._api_base_url = api_base_url
        self._token_source = token_source
        self._http = http_client if http_client is not None else httpx.Client()
        self._poll_interval_s = poll_interval_s
        self._push_fn = push_fn
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

    def tick(self) -> None:
        for camera_id, transcoder in self._transcoders.items():
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
                    self._push_fn(
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
