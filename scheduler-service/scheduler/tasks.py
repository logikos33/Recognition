import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
import redis as _redis

from .celery_app import celery
from . import config

logger = logging.getLogger(__name__)


@contextmanager
def _db():
    url = config.DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _r() -> _redis.Redis:
    return _redis.from_url(config.REDIS_URL, socket_timeout=5, decode_responses=True)


@celery.task(name="scheduler.tasks.cleanup_old_alerts")
def cleanup_old_alerts() -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.ALERTS_RETENTION_DAYS)
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM alerts WHERE acknowledged = false AND created_at < %s",
                    (cutoff,),
                )
                deleted = cur.rowcount
        logger.info("cleanup_alerts: deleted=%d", deleted)
        return {"deleted": deleted}
    except Exception as exc:
        logger.error("cleanup_alerts_error: %s", exc)
        return {"error": str(exc)}


@celery.task(name="scheduler.tasks.cleanup_old_frames")
def cleanup_old_frames() -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.FRAMES_RETENTION_DAYS)
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM training_frames WHERE status = 'pending' AND created_at < %s",
                    (cutoff,),
                )
                deleted = cur.rowcount
        logger.info("cleanup_frames: deleted=%d", deleted)
        return {"deleted": deleted}
    except Exception as exc:
        logger.error("cleanup_frames_error: %s", exc)
        return {"error": str(exc)}


@celery.task(name="scheduler.tasks.check_cameras_health")
def check_cameras_health() -> dict:
    try:
        r = _r()
        offline: list[str] = []
        with _db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id::text, name, tenant_id::text FROM cameras WHERE status = 'active'"
                )
                cameras = cur.fetchall() or []
                for cam in cameras:
                    cam_id = cam["id"]
                    raw = r.get(f"camera:last_detection:{cam_id}")
                    if not raw:
                        offline.append(cam_id)
                        continue
                    try:
                        last_dt = datetime.fromisoformat(raw)
                        if datetime.now(timezone.utc) - last_dt > timedelta(minutes=5):
                            offline.append(cam_id)
                    except ValueError:
                        offline.append(cam_id)
                if offline:
                    cur.execute(
                        "UPDATE cameras SET status = 'error' WHERE id = ANY(%s::uuid[])",
                        (offline,),
                    )
                    for cam in cameras:
                        if cam["id"] in offline:
                            r.publish(
                                f"alert:{cam.get('tenant_id', '')}",
                                json.dumps({
                                    "type": "camera_offline",
                                    "camera_id": cam["id"],
                                    "camera_name": cam["name"],
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }),
                            )
        logger.info("camera_health: offline=%d", len(offline))
        return {"offline": len(offline)}
    except Exception as exc:
        logger.error("camera_health_error: %s", exc)
        return {"error": str(exc)}
