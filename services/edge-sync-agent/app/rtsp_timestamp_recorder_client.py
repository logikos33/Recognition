"""RtspTimestampRecorderClient — RTSP-with-timestamp fallback RecorderClient.

Ported from services/api/app/infrastructure/nvr/generic_rtsp_client.py
(cascata da ADR-0034: ONVIF → SDK do fabricante → este fallback). Used
whenever the site's gravador has no dedicated search API — this is the real
protocol RVB's Intelbras NVR speaks (CLAUDE.md: RVB usa Intelbras). Same
Dahua-dialect timestamp format the monolith already fixed once
(`YYYY_MM_DD_HH_MM_SS`, NOT ISO 8601 — Intelbras licenses the Dahua
platform on several NVR lines, so this dialect *tends* to work, but is not
guaranteed for every Intelbras firmware).

LIMITATION (do not pretend otherwise): there is no real timeline index
here. `list_events` always returns exactly one synthetic RecorderEvent
covering the requested [start, end) window — the RTSP URL itself seeks to
the timestamp; if there is no actual recording in that window, playback
fails when `stream_clip` is called, not here. This mirrors the monolith's
documented behavior/limitation for this same fallback (ADR-0034 accepted
this trade-off already). If RVB's actual Intelbras firmware doesn't speak
this Dahua-OEM dialect, the real fix is Intelbras's CGI-based HTTP API
(`/cgi-bin/playBack.cgi?action=getStream&channel=...&startTime=...`) — not
implemented here because there is no source to confirm its exact contract
without hardware to validate against (documented as a known gap, not
invented).
"""

from __future__ import annotations

import logging
import socket
from collections.abc import Iterator
from datetime import datetime
from urllib.parse import quote

from .recorder_client import (
    RecorderAuthError,
    RecorderError,
    RecorderEvent,
    RecorderHealth,
    is_auth_failure_message,
    resolve_snapshot_channel,
)
from .rtsp_clip_stream import stream_rtsp_clip
from .rtsp_frame_capture import capture_still_frame
from .rtsp_validator import RTSPUrlValidator

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 5.0


def _fmt(dt: datetime) -> str:
    """Dahua/Intelbras timestamp format (e.g. 2012_09_15_12_37_05) — NOT ISO 8601."""
    return dt.strftime("%Y_%m_%d_%H_%M_%S")


class RtspTimestampRecorderClient:
    """RecorderClient fallback: RTSP with starttime/endtime, no search API.

    camera_id → channel resolution and connection details are the same
    channel_map convention used by OnvifRecorderClient (see recorder_factory.py).

    Two independent quality axes live here (migration 114):
      - OPERAÇÃO: `stream_subtype` (RECORDER_STREAM_SUBTYPE, global) — used by
        the LIVE VIEW loop via `_build_live_url(channel)` (no override arg),
        never per-camera.
      - COLETA: `collection_subtype_overrides` (camera_id -> 0/1, from the
        cloud-polled cache) — used ONLY by `capture_frame()` (training-frame
        collection), per camera, falling back to `stream_subtype` when a
        camera has no override.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        channel_map: dict[str, int],
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
        stream_subtype: int = 0,
        collection_subtype_overrides: dict[str, int] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._channel_map = dict(channel_map)
        self._timeout = timeout
        self._stream_subtype = stream_subtype
        # Eixo COLETA (migration 114): camera_id -> collection_subtype.
        # Independente de self._stream_subtype (eixo OPERAÇÃO, usado pelo
        # live view). Câmera ausente daqui usa self._stream_subtype.
        self._collection_subtype_overrides = dict(collection_subtype_overrides or {})

    def _channel_for(self, camera_id: str) -> int:
        if camera_id in self._channel_map:
            return self._channel_map[camera_id]
        raise RecorderError(
            f"camera_id={camera_id!r} sem canal RTSP mapeado em RECORDER_CHANNEL_MAP "
            "— sem fallback silencioso (ADR-0017)."
        )

    def health(self) -> RecorderHealth:
        """No HTTP API to probe — checks only that the RTSP port accepts TCP."""
        try:
            with socket.create_connection((self._host, self._port), timeout=self._timeout):
                return RecorderHealth(reachable=True, detail="rtsp port open")
        except OSError as exc:
            logger.warning(
                "rtsp_timestamp_health_check_failed host=%s port=%s err=%s",
                self._host,
                self._port,
                exc,
            )
            return RecorderHealth(reachable=False, detail=str(exc))

    def list_events(
        self, camera_id: str, start: datetime, end: datetime
    ) -> list[RecorderEvent]:
        """No real timeline — one synthetic event covering the requested window.

        See module docstring: this fallback has no search API, so "does a
        recording exist here" can only be answered by attempting playback.
        """
        self._channel_for(camera_id)  # validates mapping even though unused below
        return [
            RecorderEvent(
                event_id=f"rtsp-timestamp:{camera_id}:{start.isoformat()}",
                camera_id=camera_id,
                started_at=start,
                ended_at=end,
                event_type="recording",
                description=(
                    "Sem índice de timeline real neste protocolo (fallback RTSP "
                    "com timestamp) — cobertura assumida, não confirmada."
                ),
            )
        ]

    def stream_clip(
        self, camera_id: str, start: datetime, end: datetime
    ) -> Iterator[bytes]:
        channel = self._channel_for(camera_id)
        playback_url = self._build_playback_url(channel, start, end)
        duration_seconds = (end - start).total_seconds()
        yield from stream_rtsp_clip(playback_url, duration_seconds)

    def _build_playback_url(self, channel: int, start: datetime, end: datetime) -> str:
        user = quote(self._username or "", safe="")
        pwd = quote(self._password or "", safe="")
        creds = f"{user}:{pwd}@" if user else ""
        url = (
            f"rtsp://{creds}{self._host}:{self._port}/cam/playback"
            f"?channel={channel}"
            f"&starttime={_fmt(start)}&endtime={_fmt(end)}"
        )
        return RTSPUrlValidator.validate(url)

    def capture_frame(self, camera_id: str) -> bytes:
        """Coleta de frame de treino (eixo COLETA, migration 114).

        Resolve o subtype POR CÂMERA via `_collection_subtype_overrides`
        (cloud-polled, ver recorder_factory.resolve_collection_subtype_overrides)
        — câmera sem override cai para `self._stream_subtype` (global,
        RECORDER_STREAM_SUBTYPE), o comportamento pré-114.
        """
        channel = self._channel_for(camera_id)
        subtype = self._collection_subtype_overrides.get(camera_id, self._stream_subtype)
        live_url = self._build_live_url(channel, subtype)
        return capture_still_frame(live_url)

    def get_snapshot(self, camera_id: str, channel_hint: "int | None" = None) -> bytes:
        """This backend has no ONVIF GetSnapshotUri equivalent — the snapshot
        triage flow (Bloco A) grabs one live frame, same mechanics as
        `capture_frame`, but with its OWN channel resolution:

        Canal via `resolve_snapshot_channel` (channel_map PRIMEIRO, depois o
        *channel_hint* do payload do comando). Câmera DRAFT nunca entra no
        channel_map por desenho (config_poller filtra is_active — draft não
        pode entrar nos pipelines de HLS/coleta), então o hint é o que
        permite fotografar draft sem ativá-la — o caso central do Bloco A
        (achado em campo na RVB: canal 9 draft falhava como "sem sinal",
        quando na verdade nunca resolvia canal nenhum). O mapa vence quando
        presente, para uma câmera ATIVA nunca dessincronizar de um comando
        antigo na fila. NÃO delega a `capture_frame`, que é map-only de
        propósito (ADR-0017 — para coleta, câmera fora do mapa É
        misconfiguração).

        ffmpeg/RTSP has no structured HTTP status code, so an auth failure
        only shows up as free text in the RecorderError message (stderr tail,
        already redacted — see rtsp_frame_capture.py). Reclassified here via
        `is_auth_failure_message` into RecorderAuthError so the snapshot
        anti-lockout circuit breaker (snapshot_executor.py) still trips on
        it, same as the ONVIF path.
        """
        channel = resolve_snapshot_channel(self._channel_map, camera_id, channel_hint)
        subtype = self._collection_subtype_overrides.get(camera_id, self._stream_subtype)
        live_url = self._build_live_url(channel, subtype)
        try:
            return capture_still_frame(live_url)
        except RecorderError as exc:
            if is_auth_failure_message(str(exc)):
                raise RecorderAuthError(str(exc)) from exc
            raise

    def _build_live_url(self, channel: int, subtype: int | None = None) -> str:
        """Dahua/Intelbras-dialect LIVE stream path — same OEM family as
        _build_playback_url's `/cam/playback`. `subtype=0` (default) selects
        the main (high-res) stream, `subtype=1` the sub stream.

        *subtype* defaults to `self._stream_subtype` (RECORDER_STREAM_SUBTYPE,
        eixo OPERAÇÃO, global) when omitted — this is the LIVE VIEW path
        (`live_view_loop._resolve_camera_urls` calls this with a single
        argument, `_build_live_url(channel)`, and MUST keep using the global
        subtype, never a per-camera collection override). `capture_frame()`
        above passes an explicit *subtype* resolved per-camera (eixo COLETA,
        migration 114) — the two axes are independent on purpose."""
        effective_subtype = self._stream_subtype if subtype is None else subtype
        user = quote(self._username or "", safe="")
        pwd = quote(self._password or "", safe="")
        creds = f"{user}:{pwd}@" if user else ""
        url = (
            f"rtsp://{creds}{self._host}:{self._port}/cam/realmonitor"
            f"?channel={channel}&subtype={effective_subtype}"
        )
        return RTSPUrlValidator.validate(url)
