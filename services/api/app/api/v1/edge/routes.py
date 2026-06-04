"""Blueprint /api/v1/edge/ — endpoints do edge-sync-agent."""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import psycopg2.errors
from flask import Blueprint, request
from pydantic import ValidationError
from recognition_shared.device import EnrollmentRequest
from recognition_shared.enums import DeviceTokenScope
from recognition_shared.heartbeat import Heartbeat

from app.core.auth import get_role, get_tenant_id, jwt_required_custom
from app.core.device_auth import extract_device_id_unverified, verify_device_token
from app.core.exceptions import AuthenticationError
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.edge_heartbeat_repository import (
    EdgeHeartbeatRepository,
)
from app.infrastructure.database.repositories.edge_site_repository import (
    EdgeSiteRepository,
)

edge_bp = Blueprint("edge", __name__, url_prefix="/api/v1/edge")
logger = logging.getLogger(__name__)

_VALID_DEPLOYMENT_MODES = {"cloud", "edge", "hybrid"}
_ADMIN_ROLES = {"admin", "superadmin"}

# Threshold (seconds) beyond which a site with no recent heartbeat is 'offline'.
# Configurável via env EDGE_OFFLINE_THRESHOLD_SECONDS; default 120 s.
_OFFLINE_THRESHOLD_SECONDS = int(os.environ.get("EDGE_OFFLINE_THRESHOLD_SECONDS", "120"))


def _get_repo() -> EdgeHeartbeatRepository:
    pool = DatabasePool.get_instance()
    return EdgeHeartbeatRepository(pool)  # type: ignore[arg-type]


def _get_site_repo() -> EdgeSiteRepository:
    pool = DatabasePool.get_instance()
    return EdgeSiteRepository(pool)  # type: ignore[arg-type]


def _serialize_site(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "name": row["name"],
        "description": row.get("description"),
        "location": row.get("location"),
        "deployment_mode": row["deployment_mode"],
        "status": row["status"],
        "created_at": str(row["created_at"]) if row.get("created_at") else None,
        "created_by": str(row["created_by"]) if row.get("created_by") else None,
    }


def _derive_site_status(
    last_heartbeat_at: datetime | None,
    heartbeat_status: str | None,
    threshold_seconds: int = _OFFLINE_THRESHOLD_SECONDS,
) -> str:
    """Deriva status do site a partir do último heartbeat.

    - Sem heartbeat → 'offline'
    - Heartbeat mais antigo que threshold → 'offline'
    - Caso contrário → status do heartbeat (healthy/degraded/critical)
    """
    if last_heartbeat_at is None:
        return "offline"
    if last_heartbeat_at.tzinfo is None:
        last_heartbeat_at = last_heartbeat_at.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - last_heartbeat_at).total_seconds()
    if elapsed > threshold_seconds:
        return "offline"
    return heartbeat_status or "offline"


def _serialize_heartbeat_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "received_at": str(row["received_at"]) if row.get("received_at") else None,
        "status": row.get("status"),
        "inference_fps": float(row["inference_fps"]) if row.get("inference_fps") is not None else None,
        "cameras_online": row.get("cameras_online"),
        "cameras_total": row.get("cameras_total"),
        "cpu_pct": float(row["cpu_pct"]) if row.get("cpu_pct") is not None else None,
        "gpu_pct": float(row["gpu_pct"]) if row.get("gpu_pct") is not None else None,
        "queue_depth": row.get("queue_depth"),
        "edge_version": row.get("edge_version"),
    }


def _derive_token_status(token: dict) -> str:
    """Deriva status de um enrollment token: active | used | expired."""
    if token.get("used_at") is not None:
        return "used"
    expires_at = token.get("expires_at")
    if expires_at is None:
        return "expired"
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return "expired"
    return "active"


# ---------------------------------------------------------------------------
# Device heartbeat ingest (RS256 device auth — no JWT)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Observability: sites health (task-005)
# NOTE: must be registered before <site_id> dynamic routes to avoid ambiguity.
# ---------------------------------------------------------------------------

@edge_bp.route("/sites/health", methods=["GET"])
@jwt_required_custom
def get_sites_health(current_user_id) -> tuple:
    """Lista saúde dos sites do tenant com status derivado (O1).

    Status derivado: 'offline' se sem heartbeat ou heartbeat stale (> OFFLINE_THRESHOLD);
    caso contrário, usa o status do heartbeat (healthy/degraded/critical).
    """
    try:
        role = get_role()
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if role not in _ADMIN_ROLES:
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_repo()
    rows = repo.get_last_heartbeat_per_site(tenant_id)

    sites_health = []
    for row in rows:
        last_hb_at = row.get("received_at")
        derived_status = _derive_site_status(last_hb_at, row.get("heartbeat_status"))
        sites_health.append({
            "site_id": str(row["site_id"]),
            "name": row["site_name"],
            "deployment_mode": row["deployment_mode"],
            "derived_status": derived_status,
            "last_heartbeat_at": str(last_hb_at) if last_hb_at else None,
            "inference_fps": float(row["inference_fps"]) if row.get("inference_fps") is not None else None,
            "cameras_online": row.get("cameras_online"),
            "cameras_total": row.get("cameras_total"),
            "cpu_pct": float(row["cpu_pct"]) if row.get("cpu_pct") is not None else None,
            "gpu_pct": float(row["gpu_pct"]) if row.get("gpu_pct") is not None else None,
            "queue_depth": row.get("queue_depth"),
            "edge_version": row.get("edge_version"),
        })

    return success({"sites": sites_health})


# ---------------------------------------------------------------------------
# Admin: edge sites + enrollment tokens (task-003)
# ---------------------------------------------------------------------------

@edge_bp.route("/sites", methods=["POST"])
@jwt_required_custom
def create_site(current_user_id) -> tuple:
    """Cria edge site para o tenant do JWT (admin/superadmin only)."""
    try:
        role = get_role()
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if role not in _ADMIN_ROLES:
        return error("Acesso negado: requer role admin ou superadmin", 403)

    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    location = (body.get("location") or "").strip() or None
    deployment_mode = (body.get("deployment_mode") or "").strip()

    if not name:
        return error("Campo 'name' obrigatório", 400)
    if deployment_mode not in _VALID_DEPLOYMENT_MODES:
        return error("deployment_mode deve ser 'cloud', 'edge' ou 'hybrid'", 400)

    repo = _get_site_repo()
    site = repo.create_site(tenant_id, name, location, deployment_mode, str(current_user_id))
    logger.info("edge_site_created: tenant=%s site=%s", tenant_id[:8], site["id"])
    return success({"site": _serialize_site(site)}, status=201)


@edge_bp.route("/sites", methods=["GET"])
@jwt_required_custom
def list_sites(current_user_id) -> tuple:
    """Lista sites do tenant do JWT (admin/superadmin only)."""
    try:
        role = get_role()
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if role not in _ADMIN_ROLES:
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_site_repo()
    sites = repo.list_sites(tenant_id)
    return success({"sites": [_serialize_site(s) for s in sites]})


@edge_bp.route("/sites/<site_id>/enrollment-tokens", methods=["POST"])
@jwt_required_custom
def create_enrollment_token(site_id, current_user_id) -> tuple:
    """Gera enrollment token one-time para o site (admin/superadmin only).

    Retorna plaintext UMA vez; no banco fica apenas o SHA-256 hash.
    """
    try:
        role = get_role()
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if role not in _ADMIN_ROLES:
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_site_repo()
    site = repo.get_site_by_id(site_id, tenant_id)
    if site is None:
        return error("Site não encontrado", 404)

    plaintext = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    record = repo.create_enrollment_token(
        site_id, tenant_id, token_hash, expires_at, str(current_user_id)
    )
    logger.info(
        "enrollment_token_created: tenant=%s site=%s token_id=%s",
        tenant_id[:8], site_id, record["id"],
    )
    return success(
        {
            "token": plaintext,
            "token_id": str(record["id"]),
            "site_id": site_id,
            "expires_at": str(record["expires_at"]),
            "used_at": None,
        },
        status=201,
    )


# ---------------------------------------------------------------------------
# Enrollment token management: list + revoke (task-012)
# ---------------------------------------------------------------------------

@edge_bp.route("/sites/<site_id>/enrollment-tokens", methods=["GET"])
@jwt_required_custom
def list_enrollment_tokens(site_id, current_user_id) -> tuple:
    """Lista enrollment tokens do site com status derivado — sem hash/plaintext (C-05)."""
    try:
        role = get_role()
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if role not in _ADMIN_ROLES:
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_site_repo()
    site = repo.get_site_by_id(site_id, tenant_id)
    if site is None:
        return error("Site não encontrado", 404)

    tokens = repo.list_enrollment_tokens(tenant_id, site_id)
    result = []
    for t in tokens:
        result.append({
            "id": str(t["id"]),
            "created_at": str(t["created_at"]) if t.get("created_at") else None,
            "expires_at": str(t["expires_at"]) if t.get("expires_at") else None,
            "used_at": str(t["used_at"]) if t.get("used_at") else None,
            "used_by_device_id": t.get("used_by_device_id"),
            "status": _derive_token_status(t),
        })
    return success({"tokens": result})


@edge_bp.route("/enrollment-tokens/<token_id>/revoke", methods=["POST"])
@jwt_required_custom
def revoke_enrollment_token(token_id, current_user_id) -> tuple:
    """Revoga enrollment token não utilizado (invalida por expires_at = now()).

    - Token já usado → 409
    - Token inexistente/cross-tenant → 404
    - Token já expirado → 200 no-op (idempotente)
    """
    try:
        role = get_role()
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if role not in _ADMIN_ROLES:
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_site_repo()
    token = repo.get_enrollment_token_by_id(token_id, tenant_id)
    if token is None:
        return error("Token não encontrado", 404)

    if token.get("used_at") is not None:
        return error("Token já foi utilizado e não pode ser revogado", 409)

    repo.revoke_enrollment_token_if_unused(token_id, tenant_id)
    logger.info(
        "enrollment_token_revoked: tenant=%s token_id=%s user=%s",
        tenant_id[:8], token_id, str(current_user_id)[:8],
    )
    return success({"revoked": True, "token_id": token_id})


# ---------------------------------------------------------------------------
# Device enrollment (task-004)
# ---------------------------------------------------------------------------

_DEFAULT_SCOPES = [s.value for s in DeviceTokenScope]


@edge_bp.route("/enroll", methods=["POST"])
def enroll_device() -> tuple:
    """Device registration: consume one-time enrollment token, persist public key.

    tenant_id/site_id come exclusively from the enrollment_tokens row (C-01).
    """
    body = request.get_json(silent=True) or {}
    try:
        req = EnrollmentRequest(**body)
    except ValidationError:
        return error("Payload inválido", 422, error_code="INVALID_PAYLOAD")

    token_hash = hashlib.sha256(req.enrollment_token.encode()).hexdigest()
    fingerprint = hashlib.sha256(req.public_key_pem.encode()).hexdigest()

    repo = _get_site_repo()
    try:
        device = repo.enroll_device(
            token_hash=token_hash,
            device_id=req.device_id,
            device_name=req.device_name,
            public_key_pem=req.public_key_pem,
            fingerprint=fingerprint,
        )
    except ValueError:
        logger.warning("edge_enroll: invalid/used/expired token device=%s", req.device_id)
        return error("Enrollment token inválido, expirado ou já utilizado", 401)
    except psycopg2.errors.UniqueViolation:
        logger.warning("edge_enroll: duplicate device_id=%s", req.device_id)
        return error("Dispositivo já cadastrado neste tenant", 409)

    logger.info(
        "edge_enrolled: device=%s tenant=%s site=%s",
        req.device_id,
        str(device["tenant_id"])[:8],
        str(device["site_id"])[:8],
    )
    return success(
        {
            "tenant_id": str(device["tenant_id"]),
            "site_id": str(device["site_id"]),
            "device_id": device["device_id"],
            "scopes": _DEFAULT_SCOPES,
        },
        status=201,
    )


# ---------------------------------------------------------------------------
# Observability: heartbeats history por site (task-009)
# ---------------------------------------------------------------------------

@edge_bp.route("/sites/<site_id>/heartbeats", methods=["GET"])
@jwt_required_custom
def list_site_heartbeats(site_id, current_user_id) -> tuple:
    """Série temporal de heartbeats de um site (paginada por cursor temporal).

    Query params:
      limit  — número de registros (default 100, máx 500)
      before — ISO timestamp exclusivo (cursor de paginação)
    """
    try:
        role = get_role()
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if role not in _ADMIN_ROLES:
        return error("Acesso negado: requer role admin ou superadmin", 403)

    # Validate site ownership (C-01 — 404 se site não pertencer ao tenant)
    site_repo = _get_site_repo()
    site = site_repo.get_site_by_id(site_id, tenant_id)
    if site is None:
        return error("Site não encontrado", 404)

    try:
        limit = int(request.args.get("limit", 100))
    except (ValueError, TypeError):
        limit = 100
    limit = min(limit, 500)
    before = request.args.get("before") or None

    repo = _get_repo()
    rows = repo.list_heartbeats(tenant_id, site_id, limit=limit, before=before)
    return success({"heartbeats": [_serialize_heartbeat_row(r) for r in rows]})


# ---------------------------------------------------------------------------
# Device management: list + revoke (task-010, task-011)
# ---------------------------------------------------------------------------

@edge_bp.route("/sites/<site_id>/devices", methods=["GET"])
@jwt_required_custom
def list_site_devices(site_id, current_user_id) -> tuple:
    """Lista devices enrollados no site — sem public_key_pem/fingerprint (C-05)."""
    try:
        role = get_role()
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if role not in _ADMIN_ROLES:
        return error("Acesso negado: requer role admin ou superadmin", 403)

    repo = _get_site_repo()
    site = repo.get_site_by_id(site_id, tenant_id)
    if site is None:
        return error("Site não encontrado", 404)

    devices = repo.list_devices(tenant_id, site_id)
    result = []
    for d in devices:
        result.append({
            "id": str(d["id"]),
            "device_id": d["device_id"],
            "device_name": d.get("device_name"),
            "revoked": d["revoked"],
            "last_seen_at": str(d["last_seen_at"]) if d.get("last_seen_at") else None,
            "enrolled_at": str(d["enrolled_at"]) if d.get("enrolled_at") else None,
        })
    return success({"devices": result})


@edge_bp.route("/devices/<device_pk>/revoke", methods=["POST"])
@jwt_required_custom
def revoke_device(device_pk, current_user_id) -> tuple:
    """Revoga dispositivo — corta acesso imediato (heartbeat passa a retornar 403).

    Idempotente: revogar device já revogado → 200 no-op.
    Cross-tenant → 404 (não vaza existência — C-01).
    """
    try:
        role = get_role()
        tenant_id = get_tenant_id()
    except AuthenticationError as exc:
        return error(str(exc), 401)

    if role not in _ADMIN_ROLES:
        return error("Acesso negado: requer role admin ou superadmin", 403)

    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip() or None

    repo = _get_site_repo()
    row = repo.revoke_device(device_pk, tenant_id, str(current_user_id), reason)
    if row is None:
        return error("Dispositivo não encontrado", 404)

    logger.info(
        "edge_device_revoked: tenant=%s device_pk=%s revoked_by=%s",
        tenant_id[:8], device_pk, str(current_user_id)[:8],
    )
    return success({
        "revoked": True,
        "device_id": row.get("device_id"),
        "revoked_at": str(row["revoked_at"]) if row.get("revoked_at") else None,
    })
