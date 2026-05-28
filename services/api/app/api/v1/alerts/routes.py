"""
Recognition — Alerts Routes.

Lista, filtra, exporta e reconhece alertas de violações de EPI.
"""
import csv
import io
import logging
from datetime import datetime
from uuid import UUID

from flask import Blueprint, Response, request
from flask_jwt_extended import jwt_required

from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository

logger = logging.getLogger(__name__)

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


def _get_repo() -> AlertRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AlertRepository(pool)


def _parse_date(s: str | None):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_bool(s: str | None) -> bool | None:
    if s is None:
        return None
    return s.lower() in ("true", "1", "yes")


@alerts_bp.route("", methods=["GET"])
@jwt_required()
def list_alerts():  # type: ignore[no-untyped-def]
    """Lista alertas com filtros e paginação."""
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(int(request.args.get("per_page", 20)), 100)
        offset = (page - 1) * per_page

        result = _get_repo().list_with_filters(
            limit=per_page,
            offset=offset,
            camera_id=request.args.get("camera_id"),
            start_date=_parse_date(request.args.get("start_date")),
            end_date=_parse_date(request.args.get("end_date")),
            violation_type=request.args.get("violation_type"),
            acknowledged=_parse_bool(request.args.get("acknowledged")),
        )

        total = result["total"]
        return success({
            "alerts": result["items"],
            "count": len(result["items"]),
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page),
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_alerts_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@alerts_bp.route("/export", methods=["GET"])
@jwt_required()
def export_alerts():  # type: ignore[no-untyped-def]
    """Exporta alertas para CSV."""
    try:
        result = _get_repo().list_with_filters(
            limit=10000,
            offset=0,
            camera_id=request.args.get("camera_id"),
            start_date=_parse_date(request.args.get("start_date")),
            end_date=_parse_date(request.args.get("end_date")),
            violation_type=request.args.get("violation_type"),
            acknowledged=_parse_bool(request.args.get("acknowledged")),
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Data", "Câmera", "Tipo de Violação", "Confiança", "Reconhecido"])

        for alert in result["items"]:
            violations = alert.get("violations") or []
            if not violations:
                violations = [{}]
            for v in violations:
                writer.writerow([
                    alert.get("created_at", ""),
                    alert.get("camera_name", ""),
                    v.get("class", ""),
                    f"{v.get('confidence', 0):.0%}" if v.get("confidence") else "",
                    "Sim" if alert.get("acknowledged") else "Não",
                ])

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=alertas.csv"},
        )
    except Exception as exc:
        logger.error("export_alerts_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@alerts_bp.route("/<alert_id>/acknowledge", methods=["POST"])
@jwt_required()
def acknowledge_alert(alert_id: str):  # type: ignore[no-untyped-def]
    """Marca alerta como reconhecido."""
    try:
        alert = _get_repo().acknowledge(UUID(alert_id))
        if alert is None:
            return error("Alerta não encontrado", 404)
        return success({"alert": alert})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("acknowledge_alert_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@alerts_bp.route("/<alert_id>/snapshot", methods=["GET"])
@jwt_required()
def alert_snapshot(alert_id: str):  # type: ignore[no-untyped-def]
    """Retorna presigned URL da imagem de evidência do alerta."""
    try:
        from app.infrastructure.storage.local_storage import get_storage
        from app.infrastructure.storage.r2_storage import R2Storage

        repo = _get_repo()
        # Buscar direto por ID
        alert = repo._execute_one(
            "SELECT evidence_key FROM alerts WHERE id = %s", (str(alert_id),)
        )
        if not alert or not alert.get("evidence_key"):
            return error("Snapshot não disponível", 404)

        storage = get_storage()
        if isinstance(storage, R2Storage):
            url = storage.generate_presigned_download_url(
                alert["evidence_key"], ttl=3600, response_content_type="image/jpeg"
            )
            return success({"snapshot_url": url})

        return error("Storage local não suporta presigned URLs", 400)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("alert_snapshot_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@alerts_bp.route("/stats", methods=["GET"])
@jwt_required()
def alert_stats():  # type: ignore[no-untyped-def]
    """Estatísticas de alertas."""
    try:
        camera_id = request.args.get("camera_id")
        repo = _get_repo()
        count = repo.count_by_camera(UUID(camera_id)) if camera_id else 0
        unack = len(repo.get_unacknowledged(
            camera_id=UUID(camera_id) if camera_id else None,
            limit=1000,
        ))
        return success({"total": count, "unacknowledged": unack})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("alert_stats_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
