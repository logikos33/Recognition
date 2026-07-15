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

from .recorder_client import RecorderError, RecorderEvent, RecorderHealth
from .rtsp_clip_stream import stream_rtsp_clip
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
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        channel_map: dict[str, int],
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._channel_map = dict(channel_map)
        self._timeout = timeout

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
