"""
Recognition — Verification Queue API.

Routes:
  GET  /api/verification/queue          — alertas needs_human para revisão
  GET  /api/verification/queue/count    — contagem (badge na nav)
  POST /api/verification/<id>/review    — operador aprova ou rejeita
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.responses import success, error
from app.domain.services.verification_service import VerificationService

logger = logging.getLogger(__name__)
verification_bp = Blueprint("verification", __name__)

_svc = VerificationService()


@verification_bp.route("/api/verification/queue", methods=["GET"])
@jwt_required()
def get_queue():  # type: ignore[no-untyped-def]
    """Lista alertas aguardando revisão humana."""
    camera_id = request.args.get("camera_id")
    limit = min(int(request.args.get("limit", 50)), 100)
    try:
        items = _svc.get_human_queue(limit=limit, camera_id=camera_id)
        return success({"items": items, "count": len(items)})
    except Exception as exc:
        logger.error("get_queue_error: %s", exc)
        return error("Erro ao buscar fila", 500)


@verification_bp.route("/api/verification/queue/count", methods=["GET"])
@jwt_required()
def queue_count():  # type: ignore[no-untyped-def]
    """Contagem rápida para badge na navegação."""
    try:
        count = _svc.get_queue_count()
        return success({"count": count})
    except Exception as exc:
        logger.error("queue_count_error: %s", exc)
        return error("Erro", 500)


@verification_bp.route("/api/verification/<alert_id>/review", methods=["POST"])
@jwt_required()
def review_alert(alert_id: str):  # type: ignore[no-untyped-def]
    """Operador aprova ou rejeita alerta."""
    body = request.get_json(silent=True) or {}
    verdict = body.get("verdict")
    if verdict not in ("approve", "reject"):
        return error("verdict deve ser 'approve' ou 'reject'", 400)

    try:
        user_id = str(get_current_user_id())
        affected = _svc.human_review(alert_id=alert_id, verdict=verdict, user_id=user_id)
        if not affected:
            return error("Alerta não encontrado ou já revisado", 404)
        return success({"alert_id": alert_id, "verdict": verdict})
    except ValueError as exc:
        return error(str(exc), 400)
    except Exception as exc:
        logger.error("review_alert_error: alert=%s err=%s", alert_id, exc)
        return error("Erro ao revisar alerta", 500)
