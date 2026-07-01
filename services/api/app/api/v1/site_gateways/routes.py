"""Blueprint /api/v1/site-gateways — gateway MikroTik/WireGuard do site (migration 057).

GET /api/v1/site-gateways/<site_id>    JWT — obter gateway do site
PUT /api/v1/site-gateways/<site_id>    JWT admin — criar/atualizar gateway
"""
import logging

from flask import Blueprint, request

from app.core.auth import get_role, get_tenant_id, jwt_required_custom
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.site_gateway_repository import (
    SiteGatewayRepository,
)

site_gateways_bp = Blueprint("site_gateways", __name__, url_prefix="/api/v1/site-gateways")
logger = logging.getLogger(__name__)

_ADMIN_ROLES = {"admin", "superadmin"}
_VALID_KINDS = {"mikrotik", "generic"}
_VALID_STATUSES = {"provisioning", "active", "inactive", "error"}


def _get_repo() -> SiteGatewayRepository:
    return SiteGatewayRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


@site_gateways_bp.route("/<site_id>", methods=["GET"])
@jwt_required_custom
def get_gateway(site_id: str, current_user_id: str) -> tuple:
    try:
        tenant_id = get_tenant_id()
        row = _get_repo().get_by_site(tenant_id=tenant_id, site_id=site_id)
        if not row:
            return error("Gateway não encontrado para este site", 404)
        return success({"gateway": row})
    except Exception:
        logger.exception("get_gateway_error")
        return error("Erro ao obter gateway", 500)


@site_gateways_bp.route("/<site_id>", methods=["PUT"])
@jwt_required_custom
def upsert_gateway(site_id: str, current_user_id: str) -> tuple:
    try:
        if get_role() not in _ADMIN_ROLES:
            return error("Acesso restrito a admins", 403)
        tenant_id = get_tenant_id()
        body = request.get_json(silent=True) or {}
        kind = body.get("kind", "mikrotik")
        if kind not in _VALID_KINDS:
            return error(f"kind deve ser um de: {sorted(_VALID_KINDS)}", 422)
        row = _get_repo().upsert(
            tenant_id=tenant_id,
            site_id=site_id,
            kind=kind,
            model=body.get("model"),
            wg_public_key=body.get("wg_public_key"),
            wg_endpoint=body.get("wg_endpoint"),
            lan_subnet=body.get("lan_subnet"),
            config=body.get("config") or {},
        )
        return success({"gateway": row})
    except Exception:
        logger.exception("upsert_gateway_error")
        return error("Erro ao salvar gateway", 500)


@site_gateways_bp.route("/<site_id>/status", methods=["PATCH"])
@jwt_required_custom
def update_gateway_status(site_id: str, current_user_id: str) -> tuple:
    """Atualiza status do gateway (usado pelo edge ao confirmar provisionamento)."""
    try:
        tenant_id = get_tenant_id()
        body = request.get_json(silent=True) or {}
        status = body.get("status")
        if status not in _VALID_STATUSES:
            return error(f"status deve ser um de: {sorted(_VALID_STATUSES)}", 422)
        row = _get_repo().update_status(
            tenant_id=tenant_id, site_id=site_id, status=status
        )
        if not row:
            return error("Gateway não encontrado", 404)
        return success({"gateway": row})
    except Exception:
        logger.exception("update_gateway_status_error")
        return error("Erro ao atualizar status", 500)
