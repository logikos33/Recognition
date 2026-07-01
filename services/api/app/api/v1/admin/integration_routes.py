"""
Admin Integration Routes — credenciais de integrações externas.

Blueprint: admin_integrations_bp
url_prefix: /api/v1/admin/integrations

Endpoints:
  GET    /                          → list (sem secrets)
  PUT    /<integration_type>        → upsert
  POST   /<integration_type>/test   → test_connection
  DELETE /<integration_type>        → remove (superadmin)

Segurança:
  - Todos: jwt_required + role == 'superadmin'
  - Secret NUNCA retornado; apenas ••••last4 via secret_display
  - Audit log em toda mutação
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_role
from app.core.exceptions import AuthorizationError, ValidationError
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.integration_repository import (
    IntegrationRepository,
)
from app.domain.services.integration_service import IntegrationService

logger = logging.getLogger(__name__)

admin_integrations_bp = Blueprint(
    "admin_integrations",
    __name__,
    url_prefix="/api/v1/admin/integrations",
)


# --------------------------------------------------------------------------- helpers


def _get_service() -> IntegrationService:
    pool = DatabasePool.get_instance()
    return IntegrationService(IntegrationRepository(pool))


def _require_superadmin() -> None:
    role = get_role()
    if role != "superadmin":
        raise AuthorizationError("Apenas superadmin pode gerenciar integrações")


# --------------------------------------------------------------------------- routes


@admin_integrations_bp.get("/")
@jwt_required()
def list_integrations():
    """Lista todas as integrações do tenant (sem secrets)."""
    try:
        _require_superadmin()
        tenant_id = get_current_user_id()
        svc = _get_service()
        items = svc.list_integrations(tenant_id)
        return success({"integrations": items})
    except (AuthorizationError, ValidationError) as exc:
        return error(exc.message, exc.status_code)
    except Exception as exc:
        logger.exception("list_integrations_failed: %s", exc)
        return error("Erro interno", 500)


@admin_integrations_bp.put("/<string:integration_type>")
@jwt_required()
def upsert_integration(integration_type: str):
    """Cria ou atualiza integração. Cifra o secret antes de persistir."""
    try:
        _require_superadmin()
        user_id = get_current_user_id()

        body = request.get_json(silent=True) or {}
        label = (body.get("label") or integration_type).strip()
        config = body.get("config") or {}
        plaintext_secret = body.get("secret")

        if not isinstance(config, dict):
            return error("config deve ser um objeto JSON", 400)

        svc = _get_service()
        row = svc.save_integration(
            tenant_id=user_id,
            integration_type=integration_type,
            label=label,
            config=config,
            plaintext_secret=plaintext_secret or None,
        )
        svc.audit_log(
            tenant_id=user_id,
            user_id=user_id,
            action=f"integration.upsert.{integration_type}",
            details={"label": label, "has_secret": bool(plaintext_secret)},
        )
        return success({"integration": row}, status=200)
    except (AuthorizationError, ValidationError) as exc:
        return error(exc.message, exc.status_code)
    except Exception as exc:
        logger.exception("upsert_integration_failed: type=%s err=%s", integration_type, exc)
        return error("Erro interno", 500)


@admin_integrations_bp.post("/<string:integration_type>/test")
@jwt_required()
def test_connection(integration_type: str):
    """Testa conectividade da integração e atualiza status no banco."""
    try:
        _require_superadmin()
        user_id = get_current_user_id()
        svc = _get_service()

        if integration_type == "r2":
            result = svc.test_r2_connection(user_id)
        elif integration_type == "vast_ai":
            result = svc.test_vast_connection(user_id)
        else:
            result = svc.test_generic_connection(user_id, integration_type)

        svc.audit_log(
            tenant_id=user_id,
            user_id=user_id,
            action=f"integration.test.{integration_type}",
            details={"ok": result.get("ok"), "error": result.get("error")},
        )
        return success(result)
    except (AuthorizationError, ValidationError) as exc:
        return error(exc.message, exc.status_code)
    except Exception as exc:
        logger.exception("test_connection_failed: type=%s err=%s", integration_type, exc)
        return error("Erro interno", 500)


@admin_integrations_bp.delete("/<string:integration_type>")
@jwt_required()
def delete_integration(integration_type: str):
    """Remove integração. Apenas superadmin."""
    try:
        _require_superadmin()
        user_id = get_current_user_id()
        svc = _get_service()

        repo = IntegrationRepository(DatabasePool.get_instance())
        deleted = repo.delete_integration(user_id, integration_type)

        svc.audit_log(
            tenant_id=user_id,
            user_id=user_id,
            action=f"integration.delete.{integration_type}",
            details={"deleted_rows": deleted},
        )
        if deleted == 0:
            return error("Integração não encontrada", 404)
        return success({"deleted": True})
    except (AuthorizationError, ValidationError) as exc:
        return error(exc.message, exc.status_code)
    except Exception as exc:
        logger.exception("delete_integration_failed: type=%s err=%s", integration_type, exc)
        return error("Erro interno", 500)
