"""Blueprint /api/v1/feedback — flywheel de feedback do operador (migration 059).

POST /api/v1/feedback           JWT — registrar feedback de detecção
GET  /api/v1/feedback           JWT — listar feedback (export p/ pipeline de treino)
GET  /api/v1/feedback/summary   JWT — resumo por módulo e verdict
"""
import logging

from flask import Blueprint, request

from app.core.auth import get_tenant_id, jwt_required_custom
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.detection_feedback_repository import (
    DetectionFeedbackRepository,
)

feedback_bp = Blueprint("feedback", __name__, url_prefix="/api/v1/feedback")
logger = logging.getLogger(__name__)

_VALID_VERDICTS = {"correct", "wrong", "uncertain"}


def _get_repo() -> DetectionFeedbackRepository:
    return DetectionFeedbackRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


@feedback_bp.route("", methods=["POST"])
@jwt_required_custom
def create_feedback(current_user_id: str) -> tuple:
    """Registra feedback do operador sobre uma detecção."""
    try:
        tenant_id = get_tenant_id()
        body = request.get_json(silent=True) or {}
        verdict = body.get("verdict")
        if verdict not in _VALID_VERDICTS:
            return error(f"verdict deve ser um de: {sorted(_VALID_VERDICTS)}", 422)
        row = _get_repo().create(
            tenant_id=tenant_id,
            module=body.get("module"),
            camera_id=body.get("camera_id"),
            detection_ref=body.get("detection_ref"),
            frame_r2_key=body.get("frame_r2_key"),
            verdict=verdict,
            corrected_class=body.get("corrected_class"),
            created_by=current_user_id,
        )
        return success({"feedback": row}), 201
    except Exception:
        logger.exception("create_feedback_error")
        return error("Erro ao registrar feedback", 500)


@feedback_bp.route("", methods=["GET"])
@jwt_required_custom
def list_feedback(current_user_id: str) -> tuple:
    """Lista feedback para exportação ao pipeline de active learning."""
    try:
        tenant_id = get_tenant_id()
        module = request.args.get("module")
        verdict = request.args.get("verdict")
        if verdict and verdict not in _VALID_VERDICTS:
            return error(f"verdict deve ser um de: {sorted(_VALID_VERDICTS)}", 422)
        limit = min(int(request.args.get("limit", 100)), 500)
        rows = _get_repo().list_by_module(
            tenant_id=tenant_id,
            module=module or None,
            limit=limit,
            verdict=verdict or None,
        )
        return success({"feedback": rows, "count": len(rows)})
    except Exception:
        logger.exception("list_feedback_error")
        return error("Erro ao listar feedback", 500)


@feedback_bp.route("/summary", methods=["GET"])
@jwt_required_custom
def feedback_summary(current_user_id: str) -> tuple:
    """Resumo de feedback por módulo e verdict (dashboard de qualidade de modelo)."""
    try:
        tenant_id = get_tenant_id()
        rows = _get_repo().summary_by_module(tenant_id)
        return success({"summary": rows})
    except Exception:
        logger.exception("feedback_summary_error")
        return error("Erro ao sumarizar feedback", 500)
