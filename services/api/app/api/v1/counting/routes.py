"""
Recognition — Counting Sessions API.

Sessões de contagem com anti-duplicata via DeepSORT track_ids.

Routes:
  POST   /api/counting/sessions                    — iniciar sessão
  GET    /api/counting/sessions                    — listar sessões ativas do tenant
  PATCH  /api/counting/sessions/<id>               — update parcial (placa, manual_count, aceite...)
  DELETE /api/counting/sessions/<id>               — encerrar sessão
  GET    /api/counting/sessions/<id>/stats         — contagens em tempo real
  GET    /api/counting/sessions/validation-report  — relatório de aceite (CD-07)
"""
import logging
from datetime import date, datetime, timedelta
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

    bay_id = body.get("bay_id")
    try:
        tenant_id = get_tenant_id()
        svc = _get_service()
        session = svc.start_session(
            tenant_id=UUID(str(tenant_id)),
            camera_id=UUID(camera_id),
            module_code=module_code,
            bay_id=UUID(bay_id) if bay_id else None,
            truck_plate=body.get("truck_plate"),
            direction=body.get("direction"),
            expected_count=body.get("expected_count"),
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


@counting_bp.route("/api/counting/sessions/<session_id>", methods=["PATCH"])
@jwt_required()
def update_session(session_id: str):  # type: ignore[no-untyped-def]
    """Update parcial da sessão (truck_plate, manual_count, acceptance_status...)."""
    body = request.get_json(silent=True) or {}
    try:
        tenant_id = get_tenant_id()
        svc = _get_service()
        session = svc.update_session(
            session_id=UUID(session_id),
            tenant_id=UUID(str(tenant_id)),
            fields=body,
        )
        return success({"session": session})
    except EpiMonitorError as exc:
        return error(str(exc), exc.status_code if hasattr(exc, "status_code") else 400)
    except ValueError:
        return error("session_id inválido", 400)
    except Exception as exc:
        logger.error("update_session_error: %s", exc)
        return error("Erro ao atualizar sessão", 500)


@counting_bp.route("/api/counting/sessions/validation-report", methods=["GET"])
@jwt_required()
def validation_report():  # type: ignore[no-untyped-def]
    """Relatório de validação/aceite (CD-07): system vs manual por sessão/dia.

    Query params:
      start      — data inicial YYYY-MM-DD (default: 7 dias atrás)
      end        — data final YYYY-MM-DD, exclusiva no dia seguinte (default: hoje)
      bay_id     — UUID da baia (opcional)
      threshold  — % de erro máximo aceito (default: 5)
    """
    try:
        tenant_id = get_tenant_id()

        today = date.today()
        start_raw = request.args.get("start")
        end_raw = request.args.get("end")
        try:
            start_date = date.fromisoformat(start_raw) if start_raw else today - timedelta(days=7)
            end_date = date.fromisoformat(end_raw) if end_raw else today
        except ValueError:
            return error("Datas inválidas — use o formato YYYY-MM-DD", 400)

        start_dt = datetime.combine(start_date, datetime.min.time())
        # end é inclusivo no dia → consulta até o início do dia seguinte
        end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

        bay_raw = request.args.get("bay_id")
        try:
            bay_id = UUID(bay_raw) if bay_raw else None
        except ValueError:
            return error("bay_id inválido", 400)

        try:
            threshold = float(request.args.get("threshold", 5))
        except (TypeError, ValueError):
            return error("threshold inválido", 400)

        svc = _get_service()
        report = svc.get_validation_report(
            tenant_id=UUID(str(tenant_id)),
            start=start_dt,
            end=end_dt,
            bay_id=bay_id,
            threshold_pct=threshold,
        )
        return success(report)
    except EpiMonitorError as exc:
        return error(str(exc), exc.status_code if hasattr(exc, "status_code") else 400)
    except Exception as exc:
        logger.error("validation_report_error: %s", exc)
        return error("Erro ao gerar relatório de validação", 500)


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
