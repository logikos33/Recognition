"""
Admin Tenant Context Routes — "assumir contexto de tenant" (superadmin).

Blueprint: admin_tenant_context_bp  url_prefix=/api/v1/admin/tenant-context
  GET  /tenants             → tenants disponíveis para assumir contexto
  POST /tenants/<id>/assume → token curto com claims do tenant alvo,
                              identidade do superadmin preservada

Distinto do WS6 impersonation (app/api/v1/admin/impersonation_routes.py):
aqui o superadmin troca de TENANT (não de usuário) — o token de saída
carrega a PRÓPRIA identidade do superadmin (sub inalterado), apenas
tenant_id/tenant_schema/modules passam a ser os do tenant alvo. Ver
docstring completa do desenho em app/core/tenant_context.py.

Segurança:
  - Gate: @require_superadmin_or_404 — não-superadmin recebe 404, não 403
    (não revela a existência do recurso; mesmo espírito do 404 cross-tenant
    de C-01).
  - assume nega aninhamento: claim 'tenant_ctx' já presente (já está em
    contexto assumido) ou claim 'imp' presente (em visualização "ver como")
    → 409.
  - Alvo inexistente → 404; inativo ou sem schema_name configurado → 422
    (não pode virar search_path válido — get_schema_whitelist() também os
    exclui).
  - Token: identity do PRÓPRIO superadmin + tenant_id/tenant_schema/modules
    do ALVO + {tenant_ctx: True, impersonated_by: <superadmin id>}; TTL
    fixo TENANT_CONTEXT_TTL_MINUTES (app/core/tenant_context.py).
  - Auditoria: log_audit('tenant_context.assume') registra o INÍCIO em
    public.audit_log; TODA requisição feita depois com o token emitido aqui
    é registrada por register_tenant_context_audit (app/core/tenant_context.py,
    migration 108, public.tenant_context_audit) — before/after_request, não
    precisa de instrumentação por rota.
"""
import json
import logging
from datetime import timedelta

from flask import Blueprint, request
from flask_jwt_extended import create_access_token, get_jwt

from app.core.auth import get_current_user_id
from app.core.responses import error, success
from app.core.tenant import log_audit
from app.core.tenant_context import (
    IMPERSONATED_BY_CLAIM,
    TENANT_CONTEXT_TTL_MINUTES,
    TENANT_CTX_CLAIM,
    require_superadmin_or_404,
)
from app.extensions import limiter
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

admin_tenant_context_bp = Blueprint(
    "admin_tenant_context", __name__, url_prefix="/api/v1/admin/tenant-context"
)


# --------------------------------------------------------------------------- helpers


def _pool() -> DatabasePool:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _parse_modules(raw: object) -> list:
    """modules_enabled pode vir como list ou string JSON do psycopg2."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            return []
    return []


# --------------------------------------------------------------------------- routes


@admin_tenant_context_bp.route("/tenants", methods=["GET"])
@limiter.limit("30 per minute")
@require_superadmin_or_404
def list_available_tenants():  # type: ignore[no-untyped-def]
    """Tenants disponíveis p/ assumir contexto — ativos e com schema válido.

    Filtra fora tenants sem schema_name configurado (mesma condição de
    app.core.tenant.get_schema_whitelist()) — evitar oferecer um alvo cujo
    token resultante falharia depois em set_search_path().
    """
    try:
        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, slug
                FROM public.tenants
                WHERE is_active = true AND schema_name IS NOT NULL
                ORDER BY name
                """
            )
            rows = cur.fetchall()
            tenants = [
                {"id": str(r["id"]), "name": r["name"], "slug": r["slug"]}
                for r in rows
            ]
        return success({"tenants": tenants})
    except Exception as exc:
        logger.error("list_available_tenants_error: %s", exc, exc_info=True)
        return error("Erro ao listar tenants", 500)


@admin_tenant_context_bp.route("/tenants/<tenant_id>/assume", methods=["POST"])
@limiter.limit("20 per minute")
@require_superadmin_or_404
def assume_tenant_context(tenant_id: str):  # type: ignore[no-untyped-def]
    """Emite token de contexto assumido (TTL curto) com o schema do alvo."""
    try:
        claims = get_jwt()
        if claims.get(TENANT_CTX_CLAIM):
            return error(
                "Já está em contexto assumido — saia antes de assumir outro tenant",
                409,
            )
        if claims.get("imp"):
            return error(
                "Não é possível assumir contexto durante uma visualização 'ver como'",
                409,
            )

        pool = _pool()
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, slug, schema_name, is_active, modules_enabled
                FROM public.tenants
                WHERE id = %s
                """,
                (tenant_id,),
            )
            target = cur.fetchone()

        if not target:
            return error("Tenant não encontrado", 404)
        if not target["is_active"] or not target["schema_name"]:
            return error("Tenant inativo ou sem schema configurado", 422)

        superadmin_id = get_current_user_id()
        me = UserRepository(pool).get_by_id(superadmin_id)
        if not me:
            return error("Usuário autenticado não encontrado", 404)

        modules = _parse_modules(target["modules_enabled"])

        additional_claims = {
            "tenant_id": str(target["id"]),
            "tenant_schema": target["schema_name"],
            "email": claims.get("email", ""),
            "role": "superadmin",
            "modules": modules,
            TENANT_CTX_CLAIM: True,
            IMPERSONATED_BY_CLAIM: str(superadmin_id),
        }

        token = create_access_token(
            identity=str(superadmin_id),
            additional_claims=additional_claims,
            expires_delta=timedelta(minutes=TENANT_CONTEXT_TTL_MINUTES),
        )

        log_audit(
            actor_id=superadmin_id,
            actor_role="superadmin",
            tenant_id=str(target["id"]),
            target_type="tenant",
            target_id=str(target["id"]),
            action="tenant_context.assume",
            new_value={"tenant_name": target["name"], "tenant_slug": target["slug"]},
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )

        user_response = {
            "id": str(superadmin_id),
            "email": me.get("email", ""),
            "name": me.get("name", ""),
            "role": "superadmin",
            "tenant_id": str(target["id"]),
            "tenant_schema": target["schema_name"],
            "modules": modules,
        }

        return success({
            "token": token,
            "tenant": {
                "id": str(target["id"]),
                "name": target["name"],
                "slug": target["slug"],
            },
            "user": user_response,
            "expires_in_minutes": TENANT_CONTEXT_TTL_MINUTES,
        })
    except Exception as exc:
        logger.error("assume_tenant_context_error: %s", exc, exc_info=True)
        return error("Erro ao assumir contexto", 500)
