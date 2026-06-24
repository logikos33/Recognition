"""
Recognition — Device Routes (claim codes / enrollment plug-and-play).

POST /api/devices/claim-codes  (JWT admin)  — gera claim code curto (15 min, single-use)
POST /api/devices/claim        (público)    — troca claim code por enrollment token

O código plaintext aparece UMA única vez na response de criação.
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_role, get_tenant_id
from app.core.device_auth import (
    CLAIM_CODE_TTL_MINUTES,
    ENROLLMENT_TOKEN_TTL_HOURS,
    generate_claim_code,
    generate_enrollment_token,
    hash_claim_code,
)
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.extensions import limiter
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.device_claim_repository import (
    DeviceClaimRepository,
)

logger = logging.getLogger(__name__)

devices_bp = Blueprint("devices", __name__, url_prefix="/api/devices")

_ADMIN_ROLES = frozenset({"admin", "superadmin"})


def _get_claim_repo() -> DeviceClaimRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return DeviceClaimRepository(pool)


@devices_bp.route("/claim-codes", methods=["POST"])
@limiter.limit("10 per minute")
@jwt_required()
def create_claim_code():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - devices
    summary: Gerar claim code para enrollment de dispositivo (admin)
    security:
      - Bearer: []
    responses:
      201:
        description: Claim code gerado (plaintext exibido apenas uma vez)
      403:
        description: Requer role admin
    """
    try:
        role = get_role()
        if role not in _ADMIN_ROLES:
            return error("Apenas administradores podem gerar claim codes", 403)

        tenant_id = get_tenant_id()
        user_id = get_current_user_id()

        code = generate_claim_code()
        row = _get_claim_repo().create(
            tenant_id=tenant_id,
            code_hash=hash_claim_code(code),
            created_by=str(user_id),
            ttl_minutes=CLAIM_CODE_TTL_MINUTES,
        )

        logger.info(
            "claim_code_created: tenant=%s claim_id=%s by=%s",
            tenant_id, row.get("id"), user_id,
        )
        return success({
            "claim_code": code,
            "claim_id": str(row["id"]),
            "expires_at": row["expires_at"].isoformat()
            if hasattr(row.get("expires_at"), "isoformat") else row.get("expires_at"),
            "expires_in_minutes": CLAIM_CODE_TTL_MINUTES,
        }, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_claim_code_error: %s", exc, exc_info=True)
        return error("Erro ao gerar claim code", 500)


@devices_bp.route("/claim", methods=["POST"])
@limiter.limit("10 per minute")
def claim_device():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - devices
    summary: Trocar claim code válido por enrollment token (público, rate-limited)
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [code]
          properties:
            code: {type: string, example: ABCD2345}
            device_name: {type: string, example: edge-box-galpao-1}
    responses:
      200:
        description: Enrollment token emitido
      404:
        description: Código inválido, expirado ou já utilizado
    """
    try:
        data = request.get_json() or {}
        code = (data.get("code") or "").strip()
        device_name = (data.get("device_name") or "").strip()[:255] or None

        if not code:
            return error("code é obrigatório", 400)

        claim = _get_claim_repo().redeem(hash_claim_code(code), device_name)
        if not claim:
            # Mensagem única para inexistente/expirado/usado — evita enumeração
            return error("Claim code inválido, expirado ou já utilizado", 404)

        token = generate_enrollment_token(
            tenant_id=str(claim["tenant_id"]),
            claim_id=str(claim["id"]),
        )

        logger.info(
            "device_claimed: tenant=%s claim_id=%s device=%s",
            claim["tenant_id"], claim["id"], device_name,
        )
        return success({
            "enrollment_token": token,
            "tenant_id": str(claim["tenant_id"]),
            "expires_in_hours": ENROLLMENT_TOKEN_TTL_HOURS,
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("claim_device_error: %s", exc, exc_info=True)
        return error("Erro ao processar claim", 500)
