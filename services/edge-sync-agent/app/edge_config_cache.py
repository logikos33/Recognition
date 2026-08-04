"""Local cache of the recorder channel_map delivered by GET /api/v1/edge/config/poll
(ADR-0058, fatia mínima).

Why a file, not in-process state: `ConfigPoller` lives inside `run_daemon()`'s
"config_poller" thread, but the recorder channel_map (camera_id -> canal do
gravador) is also needed by TWO other things that build their own
`RecorderClient`/camera list independently, at their OWN process/thread
startup, before (or without) any `ConfigPoller` of their own:
  - `build_evidence_app_and_bind()` in main.py — builds the evidence API's
    RecorderClient BEFORE `run_daemon()`'s loops (incl. config_poller) exist.
  - `python -m app.collector` — its OWN systemd unit, a SEPARATE OS process
    from the daemon that runs ConfigPoller (see collector_loop.py's docstring
    for why it's a separate process).
A small JSON file, written by ConfigPoller on every successful poll and read
by both consumers at their own startup, is the simplest way to hand the
value across that thread/process boundary without inventing IPC. This is the
same "structural change needs a controlled reload (restart), not a live
hot-swap" trade-off ADR-0054 (D2) already accepted for other config that
changes the camera set — a new/changed channel takes effect on next
restart of the process that consumes it, not instantly.

Never carries a secret: only camera_id -> channel (int) and the config_version
hash — RECORDER_HOST/PORT/PROTOCOL/USERNAME/PASSWORD stay in the device's own
.env (ADR-0057: segredo não entra na config/poll).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Sibling of SQLITE_BUFFER_PATH's default (/var/edge-sync/buffer.db) — same
# directory convention for edge-local runtime state.
DEFAULT_CACHE_PATH = "/var/edge-sync/config_cache.json"


@dataclass(frozen=True)
class ChannelMapCache:
    channel_map: dict[str, int]
    config_version: str


def write_channel_map(path: str, channel_map: dict[str, int], config_version: str) -> None:
    """Atomically persists *channel_map* (best-effort — NEVER raises).

    A write failure (read-only filesystem, missing dir permissions, full
    disk) must not crash the config-poll loop — it just means this poll's
    channel map won't be picked up by a future process restart, same class
    of "config ruim não derruba o site" discipline as the rest of ADR-0054/56.
    """
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"channel_map": channel_map, "config_version": config_version})
        fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), prefix=".config_cache-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp_path, target)
        finally:
            # tmp_path already gone if os.replace succeeded; ignore if so.
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except OSError as exc:
        logger.warning("edge_config_cache_write_failed path=%s err=%s", path, exc)


def read_channel_map(path: str) -> ChannelMapCache | None:
    """Reads the cached channel map. Returns None if the file is missing,
    unreadable, or malformed — callers treat None as "cloud config not
    available yet", never as "cloud says zero cameras" (that case returns a
    real, empty-but-valid ChannelMapCache instead — see module docstring:
    the FILE existing and parsing is what makes the cloud authoritative, not
    whether the map inside it happens to be non-empty).
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None

    raw_map = data.get("channel_map")
    if not isinstance(raw_map, dict):
        return None
    try:
        channel_map = {str(k): int(v) for k, v in raw_map.items()}
    except (TypeError, ValueError):
        logger.warning("edge_config_cache_corrupt path=%s (canal não-inteiro)", path)
        return None

    config_version = str(data.get("config_version") or "")
    return ChannelMapCache(channel_map=channel_map, config_version=config_version)
