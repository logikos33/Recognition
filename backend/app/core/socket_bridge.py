"""
EPI Monitor V2 — WebSocket Bridge (Redis → SocketIO → Browser).

Pattern: Observer via Redis pub/sub.
Worker publica detecoes no Redis → Bridge assina e emite via SocketIO.
"""
import json
import logging
import os
import threading

logger = logging.getLogger(__name__)


def start_redis_bridge(socketio) -> None:  # type: ignore[no-untyped-def]
    """Inicia thread que assina Redis pub/sub e emite via SocketIO.

    Canais:
    - det:*        → detecoes de cameras → namespace /monitor
    - training:*   → progresso de treino → namespace /training
    """
    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        logger.info("redis_bridge: REDIS_URL not set, bridge disabled")
        return

    def _bridge_loop() -> None:
        try:
            import redis

            client = redis.from_url(redis_url, socket_timeout=5)
            pubsub = client.pubsub()
            pubsub.psubscribe("det:*", "training:*")
            logger.info("redis_bridge: subscribed to det:* and training:*")

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
                            f"detection",
                            {"camera_id": cam_id, **data},
                            namespace="/monitor",
                        )
                    elif channel.startswith("training:"):
                        job_id = channel.split(":")[1]
                        socketio.emit(
                            f"training_progress",
                            {"job_id": job_id, **data},
                            namespace="/training",
                        )
                except Exception as exc:
                    logger.warning("redis_bridge_message_error: %s", exc)

        except Exception as exc:
            logger.error("redis_bridge_failed: %s", exc)

    thread = threading.Thread(target=_bridge_loop, daemon=True, name="redis-bridge")
    thread.start()
    logger.info("redis_bridge: thread started")
