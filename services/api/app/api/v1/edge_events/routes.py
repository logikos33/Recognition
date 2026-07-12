"""Blueprint /api/v1/edge/events — ingest e query de eventos do edge (migration 055).

POST /api/v1/edge/events/ingest   device auth — batch ingest com dedup
GET  /api/v1/edge/events          JWT — listar eventos do tenant
"""
import logging
from uuid import uuid4

from flask import Blueprint, request

from app.core.auth import get_tenant_id, jwt_required_custom
from app.core.device_auth import extract_device_id_unverified, verify_device_token
from app.core.exceptions import AuthenticationError
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.edge_event_repository import (
    EdgeEventRepository,
)

edge_events_bp = Blueprint("edge_events", __name__, url_prefix="/api/v1/edge/events")
logger = logging.getLogger(__name__)

_VALID_EVENT_TYPES = {
    "detection", "alert_triggered", "model_loaded", "stream_started",
    "stream_stopped", "camera_offline", "camera_online", "health_check",
}


def _get_repo() -> EdgeEventRepository:
    return EdgeEventRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


@edge_events_bp.route("/ingest", methods=["POST"])
def ingest_events() -> tuple:
    """Ingest de batch de eventos vindo do edge (device JWT / HMAC auth)."""
    from app.infrastructure.database.repositories.edge_heartbeat_repository import (
        EdgeHeartbeatRepository,
    )
    hb_repo = EdgeHeartbeatRepository(DatabasePool.get_instance())  # type: ignore[arg-type]

    raw_device_id = extract_device_id_unverified(request)
    if not raw_device_id:
        return error("device_id ausente no token", 401)

    try:
        device = hb_repo.get_device_by_device_id(raw_device_id)
        if not device or device.get("revoked"):
            return error("device não autorizado", 401)
        verify_device_token(request, device["public_key_pem"])
    except AuthenticationError as exc:
        return error(str(exc), 401)

    tenant_id = str(device["tenant_id"])
    site_id = str(device["site_id"])
    device_id = raw_device_id
    batch_id = request.headers.get("X-Batch-Id") or str(uuid4())

    body = request.get_json(silent=True) or {}
    events = body.get("events", [])
    if not isinstance(events, list) or len(events) > 500:
        return error("events deve ser lista com máximo 500 itens", 422)

    repo = _get_repo()
    ingested = 0
    for evt in events:
        if not isinstance(evt, dict):
            continue
        event_type = evt.get("event_type", "")
        if not event_type:
            continue
        import hashlib, json as _json
        raw = _json.dumps(evt, sort_keys=True, default=str)
        dedup_key = f"{batch_id}:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"
        row = repo.ingest(
            tenant_id=tenant_id,
            site_id=site_id,
            device_id=device_id,
            camera_id=evt.get("camera_id"),
            module=evt.get("module"),
            event_type=event_type,
            payload=evt.get("payload") or {},
            evidence_r2_key=evt.get("evidence_r2_key"),
            occurred_at=evt.get("occurred_at"),
            batch_id=batch_id,
            dedup_key=dedup_key,
        )
        if row:
            ingested += 1

    return success({"ingested": ingested, "submitted": len(events), "batch_id": batch_id})


@edge_events_bp.route("", methods=["GET"])
@jwt_required_custom
def list_events(current_user_id: str) -> tuple:
    """Lista eventos do tenant com filtros opcionais."""
    try:
        tenant_id = get_tenant_id()
        site_id = request.args.get("site_id")
        if not site_id:
            return error("site_id é obrigatório", 422)
        limit = min(int(request.args.get("limit", 100)), 500)
        before = request.args.get("before")
        event_type = request.args.get("event_type")
        rows = _get_repo().list_by_site(
            tenant_id=tenant_id,
            site_id=site_id,
            limit=limit,
            before=before,
            event_type=event_type,
        )
        return success({"events": rows, "count": len(rows)})
    except Exception:
        logger.exception("list_events_error")
        return error("Erro ao listar eventos", 500)
