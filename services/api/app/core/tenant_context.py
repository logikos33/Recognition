"""
CORE tenant_context.py — "Assumir contexto de tenant" (superadmin).

Layer: core
Pattern: Decorator, Flask after_request hook

Distinto do WS6 impersonation (app/api/v1/admin/impersonation_routes.py):
  - WS6 "ver como": identity do JWT vira o usuário-ALVO (perde a identidade
    do superadmin); usado para reproduzir exatamente o que um usuário vê.
  - Este módulo "assumir contexto": identity do JWT continua sendo o
    superadmin (get_current_user_id() não muda); só tenant_id/tenant_schema/
    modules trocam para os do tenant alvo. Usado para o superadmin navegar
    o produto administrando/depurando um tenant, com os PRÓPRIOS
    privilégios (bypass de permissão de superadmin continua valendo — ver
    has_permission() em app/core/tenant.py).

Por que isso funciona sem tocar nenhum repository/service/rota downstream:
  get_tenant_id()/get_tenant_schema() (app/core/auth.py, INTOCADOS por
  este módulo) leem só os claims do JWT. Com o schema certo no token, todo
  código que já confia nesses helpers passa a operar no tenant certo —
  de graça.

Segurança:
  - Gate: @require_superadmin_or_404 — não-superadmin recebe 404 (não 403),
    decisão deliberada para não revelar a existência do recurso
    (equivalente ao 404 cross-tenant de C-01).
  - TTL curto (30min) — fração do normal (JWT_EXPIRY_HOURS, default 24h) —
    assumir contexto não é estado permanente.
  - Claim 'tenant_ctx': True marca o token como contexto assumido; usado
    pelo hook de auditoria abaixo e pelo guard de aninhamento no endpoint
    de start (app/api/v1/admin/tenant_context_routes.py).
  - Auditoria por requisição: register_tenant_context_audit() registra
    TODA requisição feita sob um token com claim 'tenant_ctx' — quem
    (impersonator_user_id), quando, qual tenant, qual endpoint/método,
    status (migration 108, public.tenant_context_audit).

Trade-off de custo (registrado conforme pedido): o INSERT de auditoria é
síncrono, um round-trip extra por requisição — mas SÓ para requisições
feitas sob contexto assumido (claim ausente = early-return sem tocar o
banco). Como "assumir contexto" é uma ação rara e de curta duração
(TTL 30min, uso pontual de suporte/depuração), o volume esperado é baixo
o suficiente para não justificar bufferização; se isso mudar (ex.: virar
fluxo de uso constante), bufferizar em fila assíncrona.

Related: app/core/auth.py (get_tenant_id/get_tenant_schema/get_role,
INTOCADOS), app/api/v1/admin/tenant_context_routes.py, migration 108.
"""
import functools
import logging
import os
from typing import Any, Callable

from flask import Flask, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from app.core.auth import get_role
from app.core.exceptions import NotFoundError
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.tenant_context_audit_repository import (
    TenantContextAuditRepository,
)

logger = logging.getLogger(__name__)

# Fração do TTL normal (JWT_EXPIRY_HOURS, default 24h/1440min) — mesma ordem
# de grandeza do TTL de impersonation WS6 (30min), por consistência.
# Env-overridável SÓ para encurtar em harness de soak (cruzar a fronteira de
# expiração em minutos, não meia hora) — produção fica no default 30.
TENANT_CONTEXT_TTL_MINUTES = int(os.environ.get("TENANT_CONTEXT_TTL_MINUTES", "30"))

# Claims do token de contexto assumido
TENANT_CTX_CLAIM = "tenant_ctx"
IMPERSONATED_BY_CLAIM = "impersonated_by"


def require_superadmin_or_404(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: JWT obrigatório + role == 'superadmin'.

    Não-superadmin recebe 404 (NÃO 403) — decisão deliberada do produto:
    a existência do recurso "trocar de tenant" não é revelada a quem não
    tem acesso, mesmo papel de outros gates 404 (C-01 cross-tenant).
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        verify_jwt_in_request()
        role = get_role()
        if role != "superadmin":
            raise NotFoundError("Recurso")
        return fn(*args, **kwargs)

    return wrapper


def register_tenant_context_audit(app: Flask) -> None:
    """Registra after_request que audita toda requisição sob contexto
    assumido (claim 'tenant_ctx' no JWT — migration 108).

    Best-effort: qualquer falha (JWT não verificado nesta requisição, pool
    indisponível, erro de insert) é logada e IGNORADA — auditoria nunca pode
    derrubar uma requisição de produto.
    """

    @app.after_request
    def audit_tenant_context_request(response):  # type: ignore[no-untyped-def]
        try:
            claims = get_jwt()
        except Exception:
            # Nenhum JWT verificado nesta requisição (rota pública, 401 antes
            # do decorator rodar, etc.) — nada a auditar.
            return response

        if not claims.get(TENANT_CTX_CLAIM):
            return response

        try:
            tenant_id = claims.get("tenant_id")
            impersonator_id = claims.get(IMPERSONATED_BY_CLAIM)
            if not tenant_id or not impersonator_id:
                return response

            pool = DatabasePool.get_instance()
            if pool is None:
                return response

            TenantContextAuditRepository(pool).record(
                tenant_id=str(tenant_id),
                impersonator_user_id=str(impersonator_id),
                method=request.method,
                path=request.path,
                status_code=response.status_code,
            )
        except Exception as exc:
            logger.error(
                "tenant_context_audit_failed: path=%s err=%s",
                getattr(request, "path", "?"),
                exc,
            )
        return response
