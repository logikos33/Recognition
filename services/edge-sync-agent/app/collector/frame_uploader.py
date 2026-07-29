"""Uploads one captured frame to POST /api/v1/edge/frames (cloud training pool).

Thin HTTP call, mirrors the multipart contract of
services/api/app/api/v1/edge/routes.py::upload_edge_frame — auth via the
device's own signed bearer (TokenManager.get_bearer(), fetched fresh by the
caller per upload, same as HeartbeatLoop does), same as every other
edge->cloud call in this service (ADR-0019 S7, device-owned RS256 identity).

*http_client* has no default here (unlike rtsp_clip_stream's `popen`,
which legitimately spawns a fresh subprocess per call) — the collector polls
continuously and uploads many frames per run, so CollectorLoop owns ONE
httpx.Client for connection reuse and passes it in on every call, same
pattern as OnvifRecorderClient constructing its client once in __init__.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 15.0


class FrameUploadError(Exception):
    """Raised when the cloud rejects, or is unreachable for, a frame upload."""


def upload_frame(
    http_client: Any,
    api_base_url: str,
    bearer: str,
    camera_id: str,
    recorder_id: str,
    frame_bytes: bytes,
    module_code: str,
    captured_at: datetime,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """POSTs one frame; returns the created frame_id. Raises FrameUploadError on failure."""
    url = f"{api_base_url.rstrip('/')}/api/v1/edge/frames"
    try:
        resp = http_client.post(
            url,
            headers={"Authorization": f"Bearer {bearer}"},
            data={
                "camera_id": camera_id,
                "recorder_id": recorder_id,
                "module_code": module_code,
                "captured_at": captured_at.isoformat(),
            },
            files={"file": ("frame.jpg", frame_bytes, "image/jpeg")},
            timeout=timeout,
        )
    except Exception as exc:  # network / timeout — httpx raises httpx.HTTPError subclasses
        raise FrameUploadError(f"upload de frame falhou: camera={camera_id} err={exc}") from exc

    if resp.status_code != 201:
        raise FrameUploadError(
            f"upload de frame rejeitado: camera={camera_id} status={resp.status_code} "
            f"body={resp.text[:300]}"
        )

    body = resp.json()
    return body["data"]["frame_id"]
