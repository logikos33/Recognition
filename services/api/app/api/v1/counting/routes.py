"""
Recognition — Counting Sessions API.

Sessões de contagem com anti-duplicata via DeepSORT track_ids.

Routes:
  POST   /api/counting/sessions              — iniciar sessão
  GET    /api/counting/sessions              — listar sessões ativas do tenant
  DELETE /api/counting/sessions/<id>         — encerrar sessão
  GET    /api/counting/sessions/<id>/stats   — contagens em tempo real
"""
import logging
from uuid import UUID

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.counting_repository import CountingRepository
from app.domain.services.counting_service import CountingService

logger = logging.getLogger(__name__)
counting_bp = Blueprint("counting", __name__)


def _get_service() -> CountingService:
    pool = DatabasePool.get_instance()
    return CountingService(CountingRepository(pool))


@counting_bp.route("/api/counting/sessions", methods=["POST"])
@jwt_required()
def start_session():  # type: ignore[no-untyped-def]
    """Inicia nova sessão de contagem para uma câmera."""
    body = request.get_json(silent=True) or {}
    camera_id = body.get("camera_id")
    module_code = body.get("module_code", "epi")

    if not camera_id:
        return error("camera_id é obrigatório", 400)

    try:
        tenant_id = get_tenant_id()
        svc = _get_service()
        session = svc.start_session(
            tenant_id=UUID(str(tenant_id)),
            camera_id=UUID(camera_id),
            module_code=module_code,
        )
        return success({"session": session}), 201
    except EpiMonitorError as exc:
        return error(str(exc), exc.status_code if hasattr(exc, "status_code") else 400)
    except Exception as exc:
        logger.error("start_session_error: %s", exc)
        return error("Erro ao iniciar sessão", 500)


@counting_bp.route("/api/counting/sessions", methods=["GET"])
@jwt_required()
def list_sessions():  # type: ignore[no-untyped-def]
    """Lista sessões ativas do tenant."""
    try:
        tenant_id = get_tenant_id()
        svc = _get_service()
        sessions = svc.list_active(UUID(str(tenant_id)))
        return success({"sessions": sessions})
    except Exception as exc:
        logger.error("list_sessions_error: %s", exc)
        return error("Erro ao listar sessões", 500)


@counting_bp.route("/api/counting/sessions/<session_id>", methods=["DELETE"])
@jwt_required()
def stop_session(session_id: str):  # type: ignore[no-untyped-def]
    """Encerra sessão e retorna totais finais."""
    try:
        tenant_id = get_tenant_id()
        svc = _get_service()
        session = svc.stop_session(
            session_id=UUID(session_id),
            tenant_id=UUID(str(tenant_id)),
        )
        return success({"session": session})
    except EpiMonitorError as exc:
        return error(str(exc), exc.status_code if hasattr(exc, "status_code") else 400)
    except Exception as exc:
        logger.error("stop_session_error: %s", exc)
        return error("Erro ao encerrar sessão", 500)


@counting_bp.route("/api/counting/sessions/<session_id>/stats", methods=["GET"])
@jwt_required()
def session_stats(session_id: str):  # type: ignore[no-untyped-def]
    """Retorna contagens ao vivo por classe."""
    try:
        tenant_id = get_tenant_id()
        svc = _get_service()
        stats = svc.get_live_stats(
            session_id=UUID(session_id),
            tenant_id=UUID(str(tenant_id)),
        )
        return success(stats)
    except EpiMonitorError as exc:
        return error(str(exc), exc.status_code if hasattr(exc, "status_code") else 400)
    except Exception as exc:
        logger.error("session_stats_error: %s", exc)
        return error("Erro ao buscar estatísticas", 500)
