"""
EPI Monitor V2 — WebSocket Bridge (Redis → SocketIO → Browser).

Pattern: Observer via Redis pub/sub.
Worker publica detecções no Redis → Bridge assina e emite via SocketIO.
Uses socket_timeout=None + health_check_interval to survive idle periods.

Canais assinados:
  det:*       → emite "detection" em /monitor namespace
  training:*  → emite "training_progress" em /training namespace
                + registra modelo em trained_models quando status=completed
"""
import json
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)


def _register_trained_model(job_id: str, data: dict) -> None:
    """Registra modelo treinado no DB quando training-service reporta completed.

    Roda no thread do bridge — usa DatabasePool diretamente (sem Flask context).
    """
    model_key = data.get("model_key", "")
    metrics = data.get("metrics", {})
    if not model_key:
        logger.warning("training_completed_no_model_key: job=%s", job_id)
        return
    try:
        from app.infrastructure.database.connection import DatabasePool
        from app.infrastructure.database.repositories.training_repository import TrainingRepository
        from uuid import UUID

        pool = DatabasePool.get_instance()
        if pool is None:
            logger.warning("training_model_register_skipped: pool not ready")
            return

        repo = TrainingRepository(pool)
        job = repo.get_job_by_id(UUID(job_id))
        if not job:
            logger.warning("training_model_register_skipped: job not found job=%s", job_id)
            return

        repo.create_model({
            "user_id": str(job["user_id"]),
            "job_id": job_id,
            "name": f"model-{job_id[:8]}",
            "model_path": model_key,
            "map50": metrics.get("mAP50"),
            "precision": metrics.get("precision"),
            "recall": metrics.get("recall"),
        })
        logger.info("trained_model_registered: job=%s path=%s", job_id, model_key)
    except Exception as exc:
        logger.error("trained_model_register_error: job=%s err=%s", job_id, exc)


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
                            if data.get("status") == "completed":
                                threading.Thread(
                                    target=_register_trained_model,
                                    args=(job_id, data),
                                    daemon=True,
                                    name=f"register-model-{job_id[:8]}",
                                ).start()
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
