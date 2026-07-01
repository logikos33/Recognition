"""
Recognition — Events Routes (Busca Investigativa).

Endpoints de busca e agregação de eventos para investigação forense.
Todos os endpoints filtram por tenant_id extraído do JWT — isolamento garantido.

GET /api/events/search  — busca paginada com filtros combinados
GET /api/events/timeline — agregação por bucket de tempo (sem N+1)
"""
import logging
from datetime import datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository

logger = logging.getLogger(__name__)

events_bp = Blueprint("events", __name__, url_prefix="/api/events")


def _get_repo() -> AlertRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AlertRepository(pool)


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_float(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        v = float(s)
        return max(0.0, min(1.0, v))
    except ValueError:
        return None


def _parse_list(s: str | None) -> list[str] | None:
    """Parse comma-separated or repeated query param into a list."""
    if not s:
        return None
    return [v.strip() for v in s.split(",") if v.strip()]


@events_bp.route("/search", methods=["GET"])
@jwt_required()
def search_events():  # type: ignore[no-untyped-def]
    """Busca investigativa de eventos com filtros combinados.

    Query params:
      - from: ISO datetime (ex: 2026-06-30T14:00:00)
      - to: ISO datetime
      - camera_ids: comma-separated UUIDs
      - classes: comma-separated class names (ex: no_helmet,no_vest)
      - module_code: epi | fueling
      - min_confidence: 0.0–1.0
      - page: int (default 1)
      - per_page: int (default 20, max 100)
    """
    try:
        tenant_id = get_tenant_id()

        page = max(1, int(request.args.get("page", 1)))
        per_page = min(int(request.args.get("per_page", 20)), 100)
        offset = (page - 1) * per_page

        camera_ids = _parse_list(request.args.get("camera_ids"))
        class_names = _parse_list(request.args.get("classes"))
        module_code = request.args.get("module_code") or None
        from_ts = _parse_dt(request.args.get("from"))
        to_ts = _parse_dt(request.args.get("to"))
        min_confidence = _parse_float(request.args.get("min_confidence"))

        result = _get_repo().search_events(
            tenant_id=tenant_id,
            limit=per_page,
            offset=offset,
            camera_ids=camera_ids,
            class_names=class_names,
            module_code=module_code,
            from_ts=from_ts,
            to_ts=to_ts,
            min_confidence=min_confidence,
        )

        total = result["total"]
        return success({
            "events": result["items"],
            "count": len(result["items"]),
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page),
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("search_events_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@events_bp.route("/timeline", methods=["GET"])
@jwt_required()
def events_timeline():  # type: ignore[no-untyped-def]
    """Agrega contagem de eventos por bucket de tempo.

    Query params:
      - from: ISO datetime (obrigatório)
      - to: ISO datetime (obrigatório)
      - bucket: hour | day | minute (default: hour)
      - camera_ids: comma-separated UUIDs
      - classes: comma-separated class names
      - module_code: epi | fueling
    """
    try:
        tenant_id = get_tenant_id()

        from_ts = _parse_dt(request.args.get("from"))
        to_ts = _parse_dt(request.args.get("to"))
        if not from_ts or not to_ts:
            return error("Parâmetros 'from' e 'to' são obrigatórios", 400)

        bucket = request.args.get("bucket", "hour")
        camera_ids = _parse_list(request.args.get("camera_ids"))
        class_names = _parse_list(request.args.get("classes"))
        module_code = request.args.get("module_code") or None

        buckets = _get_repo().timeline_by_bucket(
            tenant_id=tenant_id,
            from_ts=from_ts,
            to_ts=to_ts,
            bucket=bucket,
            camera_ids=camera_ids,
            class_names=class_names,
            module_code=module_code,
        )

        # Serialise datetime buckets to ISO strings
        serialised = []
        for b in buckets:
            row = dict(b)
            if hasattr(row.get("bucket"), "isoformat"):
                row["bucket"] = row["bucket"].isoformat()
            serialised.append(row)

        return success({"timeline": serialised, "bucket": bucket})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("events_timeline_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
