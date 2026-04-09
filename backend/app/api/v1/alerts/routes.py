"""
EPI Monitor V2 — Alerts Routes.

Lista, filtra e reconhece alertas de violações de EPI.
"""
import logging
from uuid import UUID

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository

logger = logging.getLogger(__name__)

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


def _get_alert_repo() -> AlertRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AlertRepository(pool)


@alerts_bp.route("", methods=["GET"])
@jwt_required()
def list_alerts():  # type: ignore[no-untyped-def]
    """Lista alertas com filtros opcionais."""
    try:
        camera_id = request.args.get("camera_id")
        limit = min(int(request.args.get("limit", 50)), 200)
        unack_only = request.args.get("unacknowledged", "").lower() == "true"

        repo = _get_alert_repo()

        if unack_only:
            cam_uuid = UUID(camera_id) if camera_id else None
            alerts = repo.get_unacknowledged(camera_id=cam_uuid, limit=limit)
        elif camera_id:
            alerts = repo.get_by_camera(UUID(camera_id), limit=limit)
        else:
            alerts = repo.get_unacknowledged(limit=limit)

        return success({"alerts": alerts, "count": len(alerts)})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_alerts_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@alerts_bp.route("/<alert_id>/acknowledge", methods=["POST"])
@jwt_required()
def acknowledge_alert(alert_id: str):  # type: ignore[no-untyped-def]
    """Marca alerta como reconhecido."""
    try:
        repo = _get_alert_repo()
        alert = repo.acknowledge(UUID(alert_id))
        if alert is None:
            return error("Alerta não encontrado", 404)
        return success({"alert": alert})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("acknowledge_alert_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@alerts_bp.route("/stats", methods=["GET"])
@jwt_required()
def alert_stats():  # type: ignore[no-untyped-def]
    """Estatísticas de alertas."""
    try:
        camera_id = request.args.get("camera_id")
        repo = _get_alert_repo()
        count = repo.count_by_camera(UUID(camera_id)) if camera_id else 0
        unacknowledged = len(repo.get_unacknowledged(
            camera_id=UUID(camera_id) if camera_id else None,
            limit=1000,
        ))
        return success({"total": count, "unacknowledged": unacknowledged})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("alert_stats_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
