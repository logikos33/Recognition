"""
Events endpoints — busca investigativa e timeline (task-049).

Endpoints:
  GET /api/v1/events/search    JWT obrigatório; busca combinada de alertas por tenant
  GET /api/v1/events/timeline  JWT obrigatório; contagem de eventos por bucket de tempo

Filtros comuns:
  camera_id[]     UUID (repetível para múltiplas câmeras)
  class_name[]    string (repetível: "no_helmet", "plate", etc.)
  module_code     string ("epi", "fueling", ...)
  from            ISO datetime (ex.: "2025-01-15T14:00:00")
  to              ISO datetime
  min_confidence  float [0, 1]

Segurança:
  - SEMPRE filtra por tenant_id (extraído do JWT — nunca de input externo)
  - Valores de filtro passados como parâmetros SQL (%s), NUNCA interpolados em f-string
"""
import logging
from datetime import datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository
from app.infrastructure.storage.local_storage import get_storage

logger = logging.getLogger(__name__)

events_bp = Blueprint("events", __name__, url_prefix="/api/v1")

_ALLOWED_BUCKETS = frozenset({"hour", "day", "week"})
_MAX_ITEMS = 200


def _pool():
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _get_repo() -> AlertRepository:
    return AlertRepository(_pool())


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_list(key: str) -> list[str]:
    """Extrai lista de query params (suporta key[] e key repetido)."""
    values = request.args.getlist(f"{key}[]") or request.args.getlist(key)
    return [v.strip() for v in values if v.strip()][:50]


def _serialize_event(row: dict, storage) -> dict:
    ev = {
        "id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]) if row.get("tenant_id") else None,
        "camera_id": str(row["camera_id"]) if row.get("camera_id") else None,
        "camera_name": row.get("camera_name"),
        "module_code": row.get("module_code"),
        "confidence": row.get("confidence"),
        "violations": row.get("violations") or [],
        "evidence_key": row.get("evidence_key"),
        "acknowledged": row.get("acknowledged", False),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "frame_url": None,
    }
    if ev["evidence_key"]:
        try:
            ev["frame_url"] = storage.generate_presigned_download_url(
                ev["evidence_key"], ttl=3600
            )
        except Exception:
            pass
    return ev


# ---------------------------------------------------------------------------
# GET /api/v1/events/search
# ---------------------------------------------------------------------------
@events_bp.route("/events/search", methods=["GET"])
@jwt_required()
def search_events():
    try:
        tenant_id = get_tenant_id()
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(_MAX_ITEMS, max(1, int(request.args.get("per_page", 20))))
        offset = (page - 1) * per_page

        camera_ids = _safe_list("camera_id") or None
        class_names = _safe_list("class_name") or None
        module_code = (request.args.get("module_code") or "").strip() or None
        from_ts = _parse_iso(request.args.get("from"))
        to_ts = _parse_iso(request.args.get("to"))
        min_conf = _parse_float(request.args.get("min_confidence"))

        result = _get_repo().search_events(
            tenant_id=tenant_id,
            limit=per_page,
            offset=offset,
            camera_ids=camera_ids,
            class_names=class_names,
            module_code=module_code,
            from_ts=from_ts,
            to_ts=to_ts,
            min_confidence=min_conf,
        )

        storage = get_storage()
        events = [_serialize_event(dict(r), storage) for r in result["items"]]
        total = result["total"]

        return success(
            {
                "events": events,
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": max(1, (total + per_page - 1) // per_page),
            }
        )
    except Exception as exc:
        logger.error("search_events_error: %s", exc, exc_info=True)
        return error("Erro na busca de eventos", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/events/timeline
# ---------------------------------------------------------------------------
@events_bp.route("/events/timeline", methods=["GET"])
@jwt_required()
def events_timeline():
    try:
        tenant_id = get_tenant_id()
        bucket = request.args.get("bucket", "hour").strip().lower()
        if bucket not in _ALLOWED_BUCKETS:
            bucket = "hour"

        from_ts = _parse_iso(request.args.get("from"))
        to_ts = _parse_iso(request.args.get("to"))

        if not from_ts or not to_ts:
            return error("Parâmetros 'from' e 'to' são obrigatórios", 400)

        camera_ids = _safe_list("camera_id") or None
        class_names = _safe_list("class_name") or None
        module_code = (request.args.get("module_code") or "").strip() or None

        rows = _get_repo().timeline_by_bucket(
            tenant_id=tenant_id,
            from_ts=from_ts,
            to_ts=to_ts,
            bucket=bucket,
            camera_ids=camera_ids,
            class_names=class_names,
            module_code=module_code,
        )

        timeline = [
            {
                "bucket": r["bucket"].isoformat() if r.get("bucket") else None,
                "count": r["count"],
            }
            for r in rows
        ]

        return success({"timeline": timeline, "bucket": bucket})
    except Exception as exc:
        logger.error("events_timeline_error: %s", exc, exc_info=True)
        return error("Erro na timeline de eventos", 500)
