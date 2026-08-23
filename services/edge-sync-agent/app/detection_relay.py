"""DetectionRelay: Redis det:* (pipeline local) → SQLiteBuffer → Uploader.

The producer side of the detections→cloud path. Until this loop existed
nothing in the agent called `SQLiteBuffer.enqueue` outside tests: the Uploader
drained a buffer nobody filled, so `/api/v1/edge/events/ingest` never saw a
single event from a box.

Bus: Redis pub/sub, one channel per camera (ADR-0002). The in-repo publishers
(`services/inference/inference/inference_engine.py`, the Celery task in
`services/api/app/infrastructure/queue/tasks/inference.py`) and the API's
`socket_bridge` use `det:{camera_id}`; ADR-0002 / deployments/edge/
edge.env.example spell it `detections:{camera_id}`. Both patterns are
subscribed so the relay works whichever name the DeepStream probe on the box
ends up publishing — that probe is NOT in this repo (it lives in the
`jetson-experiments/mm` runners the systemd unit calls) and, per
docs/edge/DIAGNOSTICO_OBSERVABILIDADE_2026-07-21.md, was not publishing yet.

Message → event rule: only frames flagged `has_violation` become a
`detection` EVENT in the buffer. det:* is live-overlay traffic (5 FPS × N
cameras, ephemeral by ADR-0002); relaying every frame would grow a buffer
that never discards (sqlite_buffer.py) on a box where a full disk is a
device interlock (CLAUDE.md "Evidência"). The whole published payload is kept
as the event payload — no reshaping, the cloud stores it as JSONB.

Opt-in: `EDGE_REDIS_URL` unset → loop not built (see
build_detection_relay_from_env). Transport errors propagate out of `run()`:
main._supervise restarts the loop with backoff and a fresh pubsub — no
bespoke reconnect logic here.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Callable

from .sqlite_buffer import SQLiteBuffer

logger = logging.getLogger(__name__)

# ponytail: two names for one bus (code says det:*, ADR-0002 says detections:*);
# collapse to one once the box's DeepStream probe fixes which it publishes.
_PATTERNS: tuple[str, ...] = ("det:*", "detections:*")
_EVENT_TYPE = "detection"
_DEFAULT_POLL_S = 1.0


def _text(value: Any) -> str:
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


class DetectionRelay:
    """Subscribes to the local detection bus and enqueues violation frames."""

    def __init__(
        self,
        buffer: SQLiteBuffer,
        pubsub_factory: Callable[[], Any],
        poll_s: float = _DEFAULT_POLL_S,
    ) -> None:
        self._buffer = buffer
        self._pubsub_factory = pubsub_factory
        self._poll_s = poll_s

    def handle(self, channel: Any, data: Any) -> int | None:
        """One bus message → buffer row id, or None when dropped."""
        try:
            payload = json.loads(_text(data))
        except ValueError:
            logger.warning("detection_relay_bad_json channel=%s", _text(channel))
            return None
        if not isinstance(payload, dict) or not payload.get("has_violation"):
            return None
        camera_id = str(payload.get("camera_id") or _text(channel).rsplit(":", 1)[-1])
        return self._buffer.enqueue(_EVENT_TYPE, camera_id, payload)

    def run(self, stop_event: threading.Event) -> None:
        """Drain the bus until *stop_event* is set. Raises on transport error."""
        pubsub = self._pubsub_factory()
        try:
            pubsub.psubscribe(*_PATTERNS)
            logger.info("detection_relay_subscribed patterns=%s", ",".join(_PATTERNS))
            while not stop_event.is_set():
                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=self._poll_s)
                if not msg or msg.get("type") != "pmessage":
                    continue
                self.handle(msg.get("channel"), msg.get("data"))
        finally:
            pubsub.close()


def build_detection_relay_from_env(
    buffer: SQLiteBuffer, env: dict[str, str] | None = None
) -> DetectionRelay | None:
    """`EDGE_REDIS_URL` set → relay on the local Redis; unset → None (off)."""
    source = env if env is not None else os.environ
    url = source.get("EDGE_REDIS_URL", "").strip()
    if not url:
        logger.info("detection_relay_disabled EDGE_REDIS_URL unset")
        return None

    def _factory() -> Any:
        import redis  # lazy: only needed when the relay is on

        return redis.Redis.from_url(url).pubsub()

    return DetectionRelay(buffer, _factory)
