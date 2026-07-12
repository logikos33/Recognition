"""
Admin Integration Routes — credenciais de integrações externas.

Blueprint: admin_integrations_bp
url_prefix: /api/v1/admin/integrations

Endpoints:
  GET    /                          → list (sem secrets)
  PUT    /<integration_type>        → upsert
  POST   /<integration_type>/test   → test_connection
  DELETE /<integration_type>        → remove

Segurança:
  - list: sempre jwt_required + role == 'superadmin' (inalterado).
  - upsert/test/delete: tipos de PLATAFORMA (r2, vast_ai, generic_gpu,
    notification) exigem role == 'superadmin', igual antes. O tipo
    ESCOPADO AO TENANT ('byo_db') também aceita role == 'admin', mas
    SOMENTE para o próprio tenant do JWT — ver `_authorize_integration`.
  - Secret NUNCA retornado; apenas ••••last4 via secret_display
  - Audit log em toda mutação (com o role real de quem executou)
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_role, get_tenant_id
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


def _resolve_tenant_id() -> str:
    """
    Tenant alvo da operação (WS6 — integrações POR tenant).

    - superadmin: aceita ?tenant_id= na query string para configurar
      integrações de qualquer tenant (ex.: R2 próprio do cliente)
    - sem override: tenant do JWT — comportamento do fix f6df666 preservado

    Padrão consagrado de roles/routes.py:_resolve_tenant_id, porém SOMENTE
    via query string (sem parse de body — evita precedência frágil).

    Usada apenas por `list_integrations` — as demais rotas (upsert/test/
    delete) usam `_authorize_integration`, que também cobre o caso do
    admin de tenant gerenciando `byo_db`.
    """
    if get_role() == "superadmin":
        override = (request.args.get("tenant_id") or "").strip()
        if override:
            return override
    return get_tenant_id()


# Tipos ESCOPADOS AO TENANT: além de superadmin, o admin do próprio tenant
# pode gerenciar. Todo o restante (r2, vast_ai, generic_gpu, notification)
# é de PLATAFORMA — superadmin apenas, sem exceção (task-058, spec original).
_TENANT_SCOPED_TYPES = frozenset({"byo_db"})


def _authorize_integration(integration_type: str) -> str:
    """
    Autoriza a operação sobre `integration_type` e resolve o tenant alvo.

    - superadmin: autorizado para qualquer integration_type. Aceita
      ?tenant_id= na query string para operar em qualquer tenant (ex.:
      configurar R2 próprio de um cliente) — comportamento preservado.
    - admin: autorizado SOMENTE para integration_type em
      `_TENANT_SCOPED_TYPES` (hoje: 'byo_db'), e SOMENTE para o próprio
      tenant do JWT. Se ?tenant_id= for informado e não bater com o
      tenant do JWT, a request é rejeitada com 403 explicitamente — nunca
      cai em silêncio para o tenant do JWT, pra deixar qualquer tentativa
      de cross-tenant auditável e óbvia em vez de mascarada como sucesso
      "no tenant errado".
    - qualquer outro role (ou admin tentando tipo de plataforma): 403.

    Raises AuthorizationError (403).
    """
    role = get_role()

    if role == "superadmin":
        override = (request.args.get("tenant_id") or "").strip()
        return override or get_tenant_id()

    if role == "admin" and integration_type in _TENANT_SCOPED_TYPES:
        jwt_tenant_id = get_tenant_id()
        override = (request.args.get("tenant_id") or "").strip()
        if override and override != jwt_tenant_id:
            raise AuthorizationError(
                "Admin só pode gerenciar integrações do próprio tenant"
            )
        return jwt_tenant_id

    raise AuthorizationError("Apenas superadmin pode gerenciar integrações")


# --------------------------------------------------------------------------- routes


@admin_integrations_bp.get("/", strict_slashes=False)
@jwt_required()
def list_integrations():
    """Lista todas as integrações do tenant (sem secrets).

    Apenas superadmin — inclusive para `byo_db` (a lista devolve todos os
    tipos de uma vez, incluindo os de plataforma; abrir isso pra admin de
    tenant exigiria filtrar a resposta por tipo, o que fica fora do escopo
    desta correção pontual — ver corpo do PR)."""
    try:
        _require_superadmin()
        tenant_id = _resolve_tenant_id()
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
        tenant_id = _authorize_integration(integration_type)
        actor_role = get_role()
        user_id = get_current_user_id()

        body = request.get_json(silent=True) or {}
        label = (body.get("label") or integration_type).strip()
        config = body.get("config") or {}
        plaintext_secret = body.get("secret")

        if not isinstance(config, dict):
            return error("config deve ser um objeto JSON", 400)

        svc = _get_service()
        row = svc.save_integration(
            tenant_id=tenant_id,
            integration_type=integration_type,
            label=label,
            config=config,
            plaintext_secret=plaintext_secret or None,
        )
        svc.audit_log(
            tenant_id=tenant_id,
            user_id=user_id,
            action=f"integration.upsert.{integration_type}",
            details={"label": label, "has_secret": bool(plaintext_secret)},
            actor_role=actor_role,
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
        tenant_id = _authorize_integration(integration_type)
        actor_role = get_role()
        user_id = get_current_user_id()
        svc = _get_service()

        if integration_type == "r2":
            result = svc.test_r2_connection(tenant_id)
        elif integration_type == "vast_ai":
            result = svc.test_vast_connection(tenant_id)
        else:
            result = svc.test_generic_connection(tenant_id, integration_type)

        svc.audit_log(
            tenant_id=tenant_id,
            user_id=user_id,
            action=f"integration.test.{integration_type}",
            details={"ok": result.get("ok"), "error": result.get("error")},
            actor_role=actor_role,
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
    """Remove integração. Superadmin (qualquer tipo) ou admin (só `byo_db`
    do próprio tenant) — ver `_authorize_integration`."""
    try:
        tenant_id = _authorize_integration(integration_type)
        actor_role = get_role()
        user_id = get_current_user_id()
        svc = _get_service()

        repo = IntegrationRepository(DatabasePool.get_instance())
        deleted = repo.delete_integration(tenant_id, integration_type)

        svc.audit_log(
            tenant_id=tenant_id,
            user_id=user_id,
            action=f"integration.delete.{integration_type}",
            details={"deleted_rows": deleted},
            actor_role=actor_role,
        )
        if deleted == 0:
            return error("Integração não encontrada", 404)
        return success({"deleted": True})
    except (AuthorizationError, ValidationError) as exc:
        return error(exc.message, exc.status_code)
    except Exception as exc:
        logger.exception("delete_integration_failed: type=%s err=%s", integration_type, exc)
        return error("Erro interno", 500)
