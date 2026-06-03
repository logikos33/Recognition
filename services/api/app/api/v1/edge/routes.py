"""Blueprint /api/v1/edge/ — endpoints do edge-sync-agent."""
import logging
from uuid import UUID

from flask import Blueprint, request
from pydantic import ValidationError
from recognition_shared.heartbeat import Heartbeat

from app.core.device_auth import extract_device_id_unverified, verify_device_token
from app.core.exceptions import AuthenticationError
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.edge_heartbeat_repository import (
    EdgeHeartbeatRepository,
)

edge_bp = Blueprint("edge", __name__, url_prefix="/api/v1/edge")
logger = logging.getLogger(__name__)


def _get_repo() -> EdgeHeartbeatRepository:
    pool = DatabasePool.get_instance()
    return EdgeHeartbeatRepository(pool)  # type: ignore[arg-type]


@edge_bp.route("/heartbeat", methods=["POST"])
def ingest_heartbeat() -> tuple:
    """Recebe telemetria periódica do edge-sync-agent (RS256 device auth)."""
    # 1. Extract bearer token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return error("Authorization header ausente ou inválido", 401)
    token = auth_header.removeprefix("Bearer ")

    # 2. Extract device_id without verifying (for DB lookup only)
    try:
        device_id = extract_device_id_unverified(token)
    except AuthenticationError as exc:
        logger.warning("edge_heartbeat: token decode failed")
        return error(str(exc), 401)

    # 3. Lookup device + public key
    repo = _get_repo()
    device = repo.get_device_by_device_id(device_id)
    if device is None:
        logger.warning("edge_heartbeat: unknown device_id")
        return error("Dispositivo não encontrado", 401)

    # 4. Check revoked before touching the signature
    if device.get("revoked"):
        logger.warning("edge_heartbeat: revoked device")
        return error("Dispositivo revogado", 403)

    # 5. Verify RS256 signature + expiry
    try:
        claims = verify_device_token(token, device["public_key_pem"])
    except AuthenticationError as exc:
        logger.warning("edge_heartbeat: token verification failed")
        return error(str(exc), 401)

    # 6. Defense-in-depth: claims tenant/site must match enrollment record
    #    Device auto-signs its own token — claims cannot be trusted for tenant attribution.
    enrollment_tenant = UUID(str(device["tenant_id"]))
    enrollment_site = UUID(str(device["site_id"]))
    if claims.tenant_id != enrollment_tenant or claims.site_id != enrollment_site:
        logger.warning(
            "edge_heartbeat: claims divergem do enrollment device=%s "
            "claims_tenant=%s enrollment_tenant=%s",
            device_id,
            str(claims.tenant_id)[:8],
            str(enrollment_tenant)[:8],
        )
        return error("Token adulterado: claims divergem do enrollment", 403)

    # 7. Validate body with Heartbeat (Pydantic v2)
    body = request.get_json(silent=True) or {}
    try:
        hb = Heartbeat(**body)
    except ValidationError:
        return error("Payload inválido", 422, error_code="INVALID_PAYLOAD")

    # 8. Persist heartbeat + update last_seen (tenant/site/device from enrollment, never claims)
    enrolled_device_id = device["device_id"]
    row = repo.insert_heartbeat(enrollment_tenant, enrollment_site, enrolled_device_id, hb)
    repo.update_last_seen(enrolled_device_id, enrollment_tenant)

    logger.info(
        "edge_heartbeat: device=%s tenant=%s status=%s",
        enrolled_device_id,
        str(enrollment_tenant)[:8],
        hb.status.value,
    )

    return success(
        {"id": row["id"], "received_at": str(row["received_at"])},
        status=201,
    )
