"""
Redis → SocketIO bridge.

Assina det:*, training:*, alert:* e emite para browsers.
"""
import json
import logging
import threading
import time

from .redis_client import make_redis

logger = logging.getLogger(__name__)

_PATTERNS = ("det:*", "training:*", "alert:*")


class RedisBridge:
    """Consome mensagens Redis e emite via SocketIO."""

    def __init__(self, socketio) -> None:
        self._socketio = socketio
        self._running = True

    def stop(self) -> None:
        self._running = False

    def start(self) -> None:
        t = threading.Thread(target=self._loop, daemon=True, name="redis-bridge")
        t.start()
        logger.info("redis_bridge_started: patterns=%s", _PATTERNS)

    def _loop(self) -> None:
        backoff = 2.0
        while self._running:
            pubsub = None
            try:
                r = make_redis(for_subscribe=True)
                pubsub = r.pubsub()
                pubsub.psubscribe(*_PATTERNS)
                logger.info("redis_bridge_subscribed")
                backoff = 2.0
                for msg in pubsub.listen():
                    if not self._running:
                        return
                    if msg.get("type") != "pmessage":
                        continue
                    try:
                        channel = msg["channel"]
                        if isinstance(channel, bytes):
                            channel = channel.decode()
                        data = json.loads(msg["data"])
                        self._dispatch(channel, data)
                    except Exception as exc:
                        logger.warning("bridge_msg_error: %s", exc)
            except Exception as exc:
                logger.error("redis_bridge_error: %s, retry_in=%.0fs", exc, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
            finally:
                if pubsub is not None:
                    try:
                        pubsub.close()
                    except Exception:
                        pass

    def _dispatch(self, channel: str, data: dict) -> None:
        if channel.startswith("det:"):
            camera_id = channel.split(":", 1)[1]
            self._socketio.emit(
                "detection",
                data,
                namespace="/monitor",
                room=f"camera:{camera_id}",
            )
        elif channel.startswith("training:"):
            job_id = channel.split(":", 1)[1]
            self._socketio.emit(
                "training_progress",
                data,
                namespace="/training",
                room=f"job:{job_id}",
            )
        elif channel.startswith("alert:"):
            tenant_id = data.get("tenant_id", "")
            camera_id = data.get("camera_id", "")
            room = f"tenant:{tenant_id}" if tenant_id else f"camera:{camera_id}"
            self._socketio.emit("alert", data, namespace="/monitor", room=room)
