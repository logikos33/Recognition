"""Pulls a clip from an already-resolved RTSP playback URL, streamed as chunks.

Shared by OnvifRecorderClient and RtspTimestampRecorderClient: once either
protocol has resolved a playback URL (ONVIF GetReplayUri, or a Dahua/
Intelbras-style `?starttime=&endtime=` RTSP URL), pulling actual bytes off
that URL is identical regardless of which protocol produced it — ffmpeg
remuxes (no re-encode, `-c copy`) into fragmented MP4 on stdout, read in
chunks. Nothing is ever written to disk (ADR-0033/0045 — reserva de disco
intocável no edge); evidence_api.py streams the generator straight into the
HTTP response.

Runtime dependency: `ffmpeg` must be on PATH in the edge-sync-agent
container/host. This is a new operational requirement for this service
(previously it only made outbound HTTPS calls) — tracked in AGENT.md.

PENDÊNCIA (same discipline as onvif_recorder_client.py): never exercised
against a real RTSP playback endpoint — no NVR/DVR hardware available in
this environment. Tests cover subprocess wiring, chunking, and error paths
with a fake Popen; they do not prove ffmpeg's actual behavior against a real
gravador. Validation against RVB's real Intelbras hardware is go-live scope
(task-095/task-097), same as the rest of the NVR client family.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Iterator
from typing import Any

from .recorder_client import RecorderError
from .redact import redact_url_credentials
from .rtsp_validator import RTSPUrlValidator

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 64 * 1024
_STDERR_TAIL = 500


def stream_rtsp_clip(
    rtsp_url: str,
    duration_seconds: float,
    popen: Any = subprocess.Popen,
) -> Iterator[bytes]:
    """Yields MP4 chunks remuxed by ffmpeg from *rtsp_url* for *duration_seconds*.

    *popen* is injectable for tests (defaults to subprocess.Popen) — same DI
    style as the rest of edge-sync-agent's http_client-injected pollers.
    Never logs rtsp_url itself: it may carry recorder credentials.
    """
    validated_url = RTSPUrlValidator.validate(rtsp_url)
    if duration_seconds <= 0:
        raise RecorderError("duration_seconds deve ser positivo para extrair um clipe")

    cmd = [
        "ffmpeg",
        "-nostdin",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        validated_url,
        "-t",
        f"{duration_seconds:.3f}",
        "-c",
        "copy",
        "-f",
        "mp4",
        "-movflags",
        "frag_keyframe+empty_moov",
        "pipe:1",
    ]

    try:
        proc = popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        # Never interpolate cmd/validated_url here — could leak credentials in logs.
        raise RecorderError(f"ffmpeg indisponível para extrair clipe: {exc}") from exc

    try:
        if proc.stdout is None:
            raise RecorderError("ffmpeg não expôs stdout para o pull do clipe")

        first_chunk = proc.stdout.read(_CHUNK_SIZE)
        if not first_chunk:
            stderr_tail = _read_stderr_tail(proc)
            logger.warning("rtsp_clip_pull_empty stderr_tail=%s", stderr_tail)
            raise RecorderError(f"ffmpeg não produziu bytes para o clipe: {stderr_tail}")

        chunk = first_chunk
        while chunk:
            yield chunk
            chunk = proc.stdout.read(_CHUNK_SIZE)
    finally:
        if proc.poll() is None:
            proc.terminate()


def _read_stderr_tail(proc: Any) -> str:
    if proc.stderr is None:
        return ""
    try:
        raw = proc.stderr.read()
    except (OSError, ValueError):
        return ""
    if not raw:
        return ""
    # O ffmpeg ecoa a URL de entrada inteira no erro de conexão — a
    # senha do gravador ia pro log e pra mensagem do RecorderError.
    return redact_url_credentials(raw.decode(errors="replace"))[:_STDERR_TAIL]
