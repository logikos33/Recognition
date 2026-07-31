"""Grabs a single still frame from a LIVE RTSP stream, no disk write.

Sibling to rtsp_clip_stream.py, same ADR-0033/0045 discipline (edge's 128GB
is SO+app only, never a storage target) — but a different operation: this
hits the camera's *live* feed (task-090's capture_frame() on RecorderClient),
not a recorded/playback window. Used by the Onda 2 motion-triggered frame
collector to pull training frames, not evidence clips.

Unlike stream_rtsp_clip (a generator the caller can abandon mid-stream), this
is a single blocking call — ffmpeg has no natural end-of-input signal from a
live source (`-frames:v 1` stops it after one frame, but if the RTSP
handshake itself never completes, ffmpeg would otherwise hang indefinitely).
An explicit *timeout_seconds* bounds that, which matters here specifically
because task-092's collector calls this in a tight per-camera poll loop — a
wedged ffmpeg subprocess would silently stall the whole collector.

PENDÊNCIA (same discipline as rtsp_clip_stream.py): never exercised against
a real RTSP source — no NVR/camera hardware available in this environment.
Tests cover subprocess wiring and error paths with a fake Popen.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any

from .recorder_client import RecorderError
from .redact import redact_url_credentials
from .rtsp_validator import RTSPUrlValidator

logger = logging.getLogger(__name__)

_STDERR_TAIL = 500
_DEFAULT_TIMEOUT_SECONDS = 10.0


def capture_still_frame(
    rtsp_url: str,
    popen: Any = subprocess.Popen,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> bytes:
    """Returns JPEG bytes for one frame captured from *rtsp_url* right now.

    *popen* is injectable for tests (defaults to subprocess.Popen), same DI
    style as stream_rtsp_clip. Never logs rtsp_url itself: it may carry
    recorder credentials.
    """
    validated_url = RTSPUrlValidator.validate(rtsp_url)

    cmd = [
        "ffmpeg",
        "-nostdin",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        validated_url,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        "-f",
        "mjpeg",
        "pipe:1",
    ]

    try:
        proc = popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        # Never interpolate cmd/validated_url here — could leak credentials in logs.
        raise RecorderError(f"ffmpeg indisponível para capturar frame: {exc}") from exc

    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise RecorderError(
            f"ffmpeg não respondeu em {timeout_seconds}s ao capturar frame"
        ) from None

    if not stdout:
        # Redige antes de logar: o ffmpeg ecoa a URL com a senha do gravador.
        stderr_tail = (
            redact_url_credentials(stderr.decode(errors="replace"))[:_STDERR_TAIL]
            if stderr else ""
        )
        logger.warning("rtsp_frame_capture_empty stderr_tail=%s", stderr_tail)
        raise RecorderError(f"ffmpeg não produziu bytes para o frame: {stderr_tail}")

    return stdout
