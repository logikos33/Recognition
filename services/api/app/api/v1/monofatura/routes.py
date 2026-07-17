"""
Recognition — Integração Monofatura (task-108, ADR-0053).

Inbound (peça bipada) + consulta de sessões de inspeção. Tenant-scoped via
get_tenant_schema (ADR-0017: sem claim → falha; cross-tenant → 404 por
construção, o schema É o isolamento).

Routes:
  POST /api/v1/monofatura/pieces/<piece_id>/scan
       body {stage, camera_id?} → abre sessão (idempotente por peça×etapa)
  POST /api/v1/monofatura/pieces/<piece_id>/stages/<stage>/complete
       body {result, evidence_r2_key?, elapsed_s?} → fecha + outbound
  GET  /api/v1/monofatura/sessions?piece_id=&limit= → lista do tenant
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_schema
from app.core.responses import error, success
from app.domain.services.inspection_service import InspectionService
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.inspection_session_repository import (
    InspectionSessionRepository,
)

logger = logging.getLogger(__name__)
monofatura_bp = Blueprint("monofatura", __name__)


def _get_service() -> InspectionService:
    pool = DatabasePool.get_instance()
    return InspectionService(InspectionSessionRepository(pool))


@monofatura_bp.route("/api/v1/monofatura/pieces/<piece_id>/scan", methods=["POST"])
@jwt_required()
def scan_piece(piece_id: str):  # type: ignore[no-untyped-def]
    """Inbound 'peça bipada': abre sessão de inspeção idempotente."""
    schema = get_tenant_schema()
    body = request.get_json(silent=True) or {}
    stage = body.get("stage")
    if not stage:
        return error("stage é obrigatório", 400)
    session = _get_service().open_session(
        schema, piece_id, stage, body.get("camera_id")
    )
    return success({"session": session})


@monofatura_bp.route(
    "/api/v1/monofatura/pieces/<piece_id>/stages/<stage>/complete",
    methods=["POST"],
)
@jwt_required()
def complete_stage(piece_id: str, stage: str):  # type: ignore[no-untyped-def]
    """Outbound: fecha a etapa com resultado por atributo + evidência + tempo."""
    schema = get_tenant_schema()
    body = request.get_json(silent=True) or {}
    result = body.get("result")
    if not isinstance(result, dict):
        return error("result (objeto) é obrigatório", 400)
    session = _get_service().complete_stage(
        schema,
        piece_id,
        stage,
        result,
        body.get("evidence_r2_key"),
        body.get("elapsed_s"),
    )
    if session is None:
        return error("Sessão de inspeção não encontrada", 404)
    return success({"session": session})


@monofatura_bp.route("/api/v1/monofatura/sessions", methods=["GET"])
@jwt_required()
def list_sessions():  # type: ignore[no-untyped-def]
    """Lista sessões de inspeção do tenant (filtro opcional por piece_id)."""
    schema = get_tenant_schema()
    piece_id = request.args.get("piece_id")
    try:
        limit = min(int(request.args.get("limit", 100)), 500)
    except ValueError:
        return error("limit inválido", 400)
    sessions = _get_service().list_sessions(schema, piece_id, limit)
    return success({"sessions": sessions})
