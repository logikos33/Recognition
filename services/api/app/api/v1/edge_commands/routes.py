"""Blueprint /api/v1/edge/commands — fila de comandos remotos pro edge (migration 056).

POST  /api/v1/edge/commands                   JWT admin — cria comando
GET   /api/v1/edge/commands/pending           device auth — edge polling
PATCH /api/v1/edge/commands/<command_id>      device auth — atualiza status
GET   /api/v1/edge/commands                   JWT — lista comandos do site
"""
import logging

from flask import Blueprint, request

from app.core.auth import get_role, get_tenant_id, jwt_required_custom
from app.core.device_auth import extract_device_id_unverified, verify_device_token
from app.core.exceptions import AuthenticationError
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.edge_command_repository import (
    EdgeCommandRepository,
)

edge_commands_bp = Blueprint("edge_commands", __name__, url_prefix="/api/v1/edge/commands")
logger = logging.getLogger(__name__)

_VALID_STATUSES = {"done", "failed", "expired"}
_ADMIN_ROLES = {"admin", "superadmin"}


def _get_repo() -> EdgeCommandRepository:
    return EdgeCommandRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


def _get_device_context() -> tuple[str, str, str] | None:
    """Autentica device e retorna (tenant_id, site_id, device_id) ou None."""
    from app.infrastructure.database.repositories.edge_heartbeat_repository import (
        EdgeHeartbeatRepository,
    )
    raw_id = extract_device_id_unverified(request)
    if not raw_id:
        return None
    hb_repo = EdgeHeartbeatRepository(DatabasePool.get_instance())  # type: ignore[arg-type]
    device = hb_repo.get_device_by_device_id(raw_id)
    if not device or device.get("revoked"):
        return None
    try:
        verify_device_token(request, device["public_key_pem"])
    except AuthenticationError:
        return None
    return str(device["tenant_id"]), str(device["site_id"]), raw_id


@edge_commands_bp.route("", methods=["POST"])
@jwt_required_custom
def create_command(current_user_id: str) -> tuple:
    """Cria comando remoto para o edge (admin only)."""
    try:
        if get_role() not in _ADMIN_ROLES:
            return error("Acesso restrito a admins", 403)
        tenant_id = get_tenant_id()
        body = request.get_json(silent=True) or {}
        site_id = body.get("site_id")
        command_type = body.get("command_type")
        if not site_id or not command_type:
            return error("site_id e command_type são obrigatórios", 422)
        import secrets
        command_id = body.get("command_id") or secrets.token_hex(16)
        row = _get_repo().create(
            tenant_id=tenant_id,
            site_id=site_id,
            command_type=command_type,
            payload=body.get("payload") or {},
            command_id=command_id,
            created_by=current_user_id,
        )
        if row is None:
            return success({"command_id": command_id, "created": False, "reason": "duplicate"})
        return success({"command": row, "command_id": command_id, "created": True}), 201
    except Exception:
        logger.exception("create_command_error")
        return error("Erro ao criar comando", 500)


@edge_commands_bp.route("/pending", methods=["GET"])
def poll_pending_commands() -> tuple:
    """Edge polling: lista comandos pendentes (device auth)."""
    ctx = _get_device_context()
    if not ctx:
        return error("device não autorizado", 401)
    _, site_id, _ = ctx
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        rows = _get_repo().list_pending(site_id=site_id, limit=limit)
        return success({"commands": rows, "count": len(rows)})
    except Exception:
        logger.exception("poll_pending_commands_error")
        return error("Erro ao consultar comandos", 500)


@edge_commands_bp.route("/<command_id>", methods=["PATCH"])
def update_command_status(command_id: str) -> tuple:
    """Edge atualiza status de comando após execução (device auth)."""
    ctx = _get_device_context()
    if not ctx:
        return error("device não autorizado", 401)
    tenant_id, _, _ = ctx
    try:
        body = request.get_json(silent=True) or {}
        status = body.get("status")
        if status not in _VALID_STATUSES:
            return error(f"status deve ser um de: {sorted(_VALID_STATUSES)}", 422)
        row = _get_repo().update_status(
            command_id_str=command_id,
            tenant_id=tenant_id,
            status=status,
            result=body.get("result"),
        )
        if not row:
            return error("Comando não encontrado", 404)
        return success({"command": row})
    except Exception:
        logger.exception("update_command_status_error")
        return error("Erro ao atualizar comando", 500)


@edge_commands_bp.route("", methods=["GET"])
@jwt_required_custom
def list_commands(current_user_id: str) -> tuple:
    """Lista comandos de um site (admin view)."""
    try:
        tenant_id = get_tenant_id()
        site_id = request.args.get("site_id")
        if not site_id:
            return error("site_id é obrigatório", 422)
        status = request.args.get("status")
        limit = min(int(request.args.get("limit", 50)), 200)
        rows = _get_repo().list_by_site(
            tenant_id=tenant_id,
            site_id=site_id,
            status=status or None,
            limit=limit,
        )
        return success({"commands": rows, "count": len(rows)})
    except Exception:
        logger.exception("list_commands_error")
        return error("Erro ao listar comandos", 500)
