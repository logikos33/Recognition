"""
EPI Monitor V2 — Streams status (public, no JWT).

Reports Celery worker status via Redis inspection.
"""
import json
import logging
import os

import redis
from flask import Blueprint, jsonify

from app.constants import RedisChannel

logger = logging.getLogger(__name__)

streams_bp = Blueprint("streams", __name__, url_prefix="/api/streams")


@streams_bp.route("/status", methods=["GET"])
def streams_status():  # type: ignore[no-untyped-def]
    """Status de todos os workers Celery. Sem JWT — endpoint público."""
    try:
        redis_url = os.environ.get("REDIS_URL", "")
        if not redis_url:
            return jsonify({"workers": [], "status": "redis_unavailable"}), 200

        client = redis.from_url(redis_url, socket_timeout=3)

        # Inspect Celery workers via celery internals
        from app.infrastructure.queue.celery_app import celery as celery_app
        inspector = celery_app.control.inspect(timeout=2)
        active = inspector.active() or {}
        stats = inspector.stats() or {}

        workers = []
        for worker_name, worker_stats in stats.items():
            active_tasks = active.get(worker_name, [])
            workers.append({
                "worker_id": worker_name,
                "status": "online",
                "active_tasks": len(active_tasks),
                "pool": worker_stats.get("pool", {}).get("implementation", "unknown"),
            })

        return jsonify({"workers": workers, "status": "ok"}), 200
    except Exception as exc:
        logger.warning("streams_status_error: %s", exc)
        return jsonify({"workers": [], "status": "error"}), 200
