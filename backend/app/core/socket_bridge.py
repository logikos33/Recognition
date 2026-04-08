"""
EPI Monitor V2 — WebSocket Bridge (Redis → SocketIO → Browser).

Pattern: Observer via Redis pub/sub.
Worker publica detecções no Redis → Bridge assina e emite via SocketIO.
Uses socket_timeout=None + health_check_interval to survive idle periods.
"""
import json
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)


def _make_bridge_pubsub(redis_url: str):
    """Dedicated pubsub connection — no socket_timeout (listen blocks)."""
    import redis

    r = redis.from_url(
        redis_url,
        socket_timeout=None,
        socket_keepalive=True,
        health_check_interval=25,
    )
    ps = r.pubsub()
    ps.psubscribe("det:*", "training:*")
    return ps


def start_redis_bridge(socketio) -> None:  # type: ignore[no-untyped-def]
    """Start background thread: Redis pub/sub → SocketIO.

    Channels:
    - det:*       → camera detections → namespace /monitor
    - training:*  → training progress → namespace /training

    Reconnects with exponential backoff on any failure.
    """
    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        logger.info("redis_bridge: REDIS_URL not set, bridge disabled")
        return

    def _bridge_loop() -> None:
        backoff = 2
        while True:
            pubsub = None
            try:
                pubsub = _make_bridge_pubsub(redis_url)
                logger.info("redis_bridge: subscribed to det:* and training:*")
                backoff = 2

                for message in pubsub.listen():
                    if message["type"] != "pmessage":
                        continue
                    try:
                        channel = message["channel"]
                        if isinstance(channel, bytes):
                            channel = channel.decode()
                        data = json.loads(message["data"])

                        if channel.startswith("det:"):
                            cam_id = channel.split(":")[1]
                            socketio.emit(
                                "detection",
                                {"camera_id": cam_id, **data},
                                namespace="/monitor",
                            )
                        elif channel.startswith("training:"):
                            job_id = channel.split(":")[1]
                            socketio.emit(
                                "training_progress",
                                {"job_id": job_id, **data},
                                namespace="/training",
                            )
                    except Exception as exc:
                        logger.warning("redis_bridge_message_error: %s", exc)

            except Exception as exc:
                logger.error("redis_bridge_failed: %s -- reconnecting in %ds", exc, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
            finally:
                if pubsub is not None:
                    try:
                        pubsub.close()
                    except Exception:
                        pass

    thread = threading.Thread(target=_bridge_loop, daemon=True, name="redis-bridge")
    thread.start()
    logger.info("redis_bridge: thread started")
