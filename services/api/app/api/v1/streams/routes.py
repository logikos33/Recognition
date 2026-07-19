"""
Recognition — Streams status (admin only).

Reports Celery worker status via Redis inspection.

S4: antes esta rota era PÚBLICA e expunha a topologia dos workers Celery
(nomes, pool, nº de tasks) sem qualquer auth, e sempre respondia 200
(mascarando erro). Não há consumidor no frontend (`grep` = zero). Passou a
exigir role admin/superadmin. Reversão de decisão anterior ("público permanece")
— por isso vai marcada para revisão humana (risk:security).
"""
import logging
import os

from flask import Blueprint, jsonify

from app.core.auth import get_role, jwt_required_custom
from app.core.exceptions import AuthenticationError
from app.core.responses import error


logger = logging.getLogger(__name__)

streams_bp = Blueprint("streams", __name__, url_prefix="/api/streams")

_ADMIN_ROLES = {"admin", "superadmin"}


@streams_bp.route("/status", methods=["GET"])
@jwt_required_custom
def streams_status(current_user_id: str):  # type: ignore[no-untyped-def]
    """Status de todos os workers Celery (admin only — S4)."""
    # Auth/role fora do try amplo — não pode ser mascarada como 200
    try:
        role = get_role()
    except AuthenticationError as exc:
        return error(str(exc), 401)
    if role not in _ADMIN_ROLES:
        return error("Acesso restrito a admins", 403)
    try:
        redis_url = os.environ.get("REDIS_URL", "")
        if not redis_url:
            return jsonify({"workers": [], "status": "redis_unavailable"}), 200

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
