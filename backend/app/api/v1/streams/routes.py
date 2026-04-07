"""
EPI Monitor V2 — Streams status (public, no JWT).
Compatible with V1 GET /api/streams/status.
"""
import logging

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

streams_bp = Blueprint("streams", __name__, url_prefix="/api/streams")


@streams_bp.route("/status", methods=["GET"])
def streams_status():  # type: ignore[no-untyped-def]
    """Status de todos os workers. Sem JWT — endpoint público."""
    try:
        import redis
        import os
        import json

        redis_url = os.environ.get("REDIS_URL", "")
        if not redis_url:
            return jsonify({"workers": [], "status": "redis_unavailable"}), 200

        client = redis.from_url(redis_url, socket_timeout=3)
        worker_ids = client.smembers("epi:workers")
        workers = []
        for wid in worker_ids:
            wid_str = wid.decode() if isinstance(wid, bytes) else wid
            health_key = f"epi:worker:{wid_str}:health"
            health_data = client.get(health_key)
            if health_data:
                workers.append(json.loads(health_data))
            else:
                workers.append({"worker_id": wid_str, "status": "unknown"})

        return jsonify({"workers": workers, "status": "ok"}), 200
    except Exception as exc:
        logger.warning("streams_status_error: %s", exc)
        return jsonify({"workers": [], "status": "error"}), 200
