"""Blueprint /api/v1/notifications — canais de notificação externos (migration 058).

GET    /api/v1/notifications/channels          JWT — listar canais do tenant
POST   /api/v1/notifications/channels          JWT admin — criar canal
PATCH  /api/v1/notifications/channels/<id>     JWT admin — atualizar canal
DELETE /api/v1/notifications/channels/<id>     JWT admin — deletar canal
"""
import logging

from flask import Blueprint, request

from app.core.auth import get_role, get_tenant_id, jwt_required_custom
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.notification_repository import (
    NotificationRepository,
)

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/v1/notifications")
logger = logging.getLogger(__name__)

_VALID_TYPES = {"whatsapp", "telegram", "email", "webhook"}
_ADMIN_ROLES = {"admin", "superadmin"}


def _get_repo() -> NotificationRepository:
    return NotificationRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


@notifications_bp.route("/channels", methods=["GET"])
@jwt_required_custom
def list_channels(current_user_id: str) -> tuple:
    try:
        tenant_id = get_tenant_id()
        rows = _get_repo().list_channels(tenant_id)
        return success({"channels": rows, "count": len(rows)})
    except Exception:
        logger.exception("list_channels_error")
        return error("Erro ao listar canais", 500)


@notifications_bp.route("/channels", methods=["POST"])
@jwt_required_custom
def create_channel(current_user_id: str) -> tuple:
    try:
        if get_role() not in _ADMIN_ROLES:
            return error("Acesso restrito a admins", 403)
        tenant_id = get_tenant_id()
        body = request.get_json(silent=True) or {}
        channel_type = body.get("type")
        if channel_type not in _VALID_TYPES:
            return error(f"type deve ser um de: {sorted(_VALID_TYPES)}", 422)
        config = body.get("config") or {}
        recipients = body.get("recipients") or []
        if not isinstance(recipients, list):
            return error("recipients deve ser lista", 422)
        row = _get_repo().create_channel(
            tenant_id=tenant_id,
            channel_type=channel_type,
            config=config,
            recipients=recipients,
        )
        return success({"channel": row}), 201
    except Exception:
        logger.exception("create_channel_error")
        return error("Erro ao criar canal", 500)


@notifications_bp.route("/channels/<channel_id>", methods=["PATCH"])
@jwt_required_custom
def update_channel(channel_id: str, current_user_id: str) -> tuple:
    try:
        if get_role() not in _ADMIN_ROLES:
            return error("Acesso restrito a admins", 403)
        tenant_id = get_tenant_id()
        body = request.get_json(silent=True) or {}
        row = _get_repo().update_channel(
            tenant_id=tenant_id,
            channel_id=channel_id,
            enabled=body.get("enabled"),
            recipients=body.get("recipients"),
            config=body.get("config"),
        )
        if not row:
            return error("Canal não encontrado", 404)
        return success({"channel": row})
    except Exception:
        logger.exception("update_channel_error")
        return error("Erro ao atualizar canal", 500)


@notifications_bp.route("/channels/<channel_id>", methods=["DELETE"])
@jwt_required_custom
def delete_channel(channel_id: str, current_user_id: str) -> tuple:
    try:
        if get_role() not in _ADMIN_ROLES:
            return error("Acesso restrito a admins", 403)
        tenant_id = get_tenant_id()
        deleted = _get_repo().delete_channel(tenant_id, channel_id)
        if not deleted:
            return error("Canal não encontrado", 404)
        return success({"deleted": True})
    except Exception:
        logger.exception("delete_channel_error")
        return error("Erro ao deletar canal", 500)
