"""
Admin Impersonation Routes (WS6) — "ver como" um usuário-alvo.

Blueprints:
  admin_impersonation_bp  url_prefix=/api/v1/admin
    POST /users/<id>/impersonate → token curto (30 min) com claims do alvo

  impersonation_bp        url_prefix=/api/v1/impersonation
    POST /stop → encerra a visualização (marca ended_at pelo jti)

Segurança:
  - Start: @require_superadmin; nega aninhamento (claim 'imp'), alvo inativo,
    alvo superadmin e alvo sem tenant
  - Token: identity do ALVO + claims idênticas ao login (tenant_id,
    tenant_schema, email, role, modules, perms) + {imp, impersonated_by,
    impersonator_email}; TTL fixo de 30 minutos
  - NUNCA toca credenciais do alvo; NÃO registra em active_sessions (não
    conta como sessão do alvo, não dispara single_session)
  - Audit: log_audit 'impersonation.start'/'impersonation.stop' + tabela
    public.impersonation_sessions (migration 086)
"""
import logging
from datetime import timedelta

from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    decode_token,
    get_jwt,
    jwt_required,
)

from app.core.auth import get_current_user_id
from app.core.responses import error, success
from app.core.tenant import log_audit, require_superadmin
from app.extensions import limiter
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.impersonation_repository import (
    ImpersonationRepository,
)
from app.infrastructure.database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

admin_impersonation_bp = Blueprint(
    "admin_impersonation", __name__, url_prefix="/api/v1/admin"
)
impersonation_bp = Blueprint(
    "impersonation", __name__, url_prefix="/api/v1/impersonation"
)

IMPERSONATION_TTL_MINUTES = 30


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
        import json as _json

        try:
            parsed = _json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            return []
    return []


def _resolve_perms(user: dict) -> list | None:
    """Claim 'perms' do alvo — best-effort, mesma semântica do login."""
    try:
        from app.domain.services.permission_service import PermissionService
        from app.infrastructure.database.repositories.custom_role_repository import (
            CustomRoleRepository,
        )
        from app.infrastructure.database.repositories.permission_override_repository import (
            PermissionOverrideRepository,
        )

        pool = DatabasePool.get_instance()
        if pool is None:
            return None
        service = PermissionService(
            PermissionOverrideRepository(pool), CustomRoleRepository(pool)
        )
        return service.resolve_effective(user)
    except Exception as exc:
        logger.warning("impersonation_perms_failed: %s", exc)
        return None


# --------------------------------------------------------------------------- routes


@admin_impersonation_bp.route("/users/<user_id>/impersonate", methods=["POST"])
@limiter.limit("10 per minute")
@require_superadmin
def impersonate_user(user_id: str):  # type: ignore[no-untyped-def]
    """Emite token de visualização (30 min) com as claims do usuário-alvo."""
    try:
        claims = get_jwt()
        if claims.get("imp"):
            return error(
                "Já está em modo de visualização — encerre a atual antes de iniciar outra",
                403,
            )

        target = UserRepository(_pool()).get_by_id_with_tenant(user_id)
        if not target:
            return error("Usuário não encontrado", 404)
        if str(target.get("role")) == "superadmin":
            return error("Não é possível ver como outro superadmin", 403)
        if not target.get("is_active"):
            return error("Usuário-alvo está inativo", 403)

        tenant_id = target.get("tenant_id")
        tenant_schema = target.get("tenant_schema")
        if not tenant_id or not tenant_schema:
            return error("Usuário-alvo sem tenant atribuído", 422)

        superadmin_id = get_current_user_id()
        modules = _parse_modules(target.get("modules_enabled"))

        additional_claims = {
            "tenant_id": str(tenant_id),
            "tenant_schema": tenant_schema,
            "email": target.get("email", ""),
            "role": target.get("role"),
            "modules": modules,
            # Marcadores de impersonation — banner no frontend + bloqueio de
            # aninhamento no backend
            "imp": True,
            "impersonated_by": str(superadmin_id),
            "impersonator_email": claims.get("email", ""),
        }
        perms = _resolve_perms(target)
        if perms is not None:
            additional_claims["perms"] = perms

        token = create_access_token(
            identity=str(target["id"]),
            additional_claims=additional_claims,
            expires_delta=timedelta(minutes=IMPERSONATION_TTL_MINUTES),
        )

        # Correlação forense — best-effort: falha no bookkeeping não impede a
        # visualização (audit_log abaixo ainda registra o evento)
        jti = None
        try:
            jti = decode_token(token).get("jti")
            ImpersonationRepository(_pool()).start(
                tenant_id=str(tenant_id),
                superadmin_id=str(superadmin_id),
                target_user_id=str(target["id"]),
                jti=jti,
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )
        except Exception as exc:
            logger.error("impersonation_session_insert_failed: %s", exc)

        log_audit(
            actor_id=superadmin_id,
            actor_role="superadmin",
            tenant_id=str(tenant_id),
            target_type="user",
            target_id=str(target["id"]),
            action="impersonation.start",
            new_value={"target_email": target.get("email"), "jti": jti},
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )

        # Mesmo shape do login — o frontend reusa o parsing de {token, user}
        user_response = {
            k: v
            for k, v in target.items()
            if k not in ("tenant_schema", "modules_enabled")
        }
        user_response["id"] = str(target["id"])
        if user_response.get("tenant_id"):
            user_response["tenant_id"] = str(user_response["tenant_id"])
        if user_response.get("custom_role_id"):
            user_response["custom_role_id"] = str(user_response["custom_role_id"])
        created_at = user_response.get("created_at")
        if hasattr(created_at, "isoformat"):
            user_response["created_at"] = created_at.isoformat()
        user_response["tenant_schema"] = tenant_schema
        user_response["modules"] = modules
        from app.core.permissions import permissions_for_role

        user_response["permissions"] = (
            perms if perms is not None
            else permissions_for_role(str(target.get("role") or ""))
        )

        return success({
            "token": token,
            "user": user_response,
            "expires_in_minutes": IMPERSONATION_TTL_MINUTES,
        })
    except Exception as exc:
        logger.error("impersonate_user_error: %s", exc, exc_info=True)
        return error("Erro ao iniciar visualização", 500)


@impersonation_bp.route("/stop", methods=["POST"])
@jwt_required()
def stop_impersonation():  # type: ignore[no-untyped-def]
    """Encerra a visualização atual — marca ended_at pelo jti. Best-effort."""
    claims = get_jwt()
    if not claims.get("imp"):
        return error("Não está em modo de visualização", 400)

    jti = claims.get("jti")
    ended = None
    try:
        if jti:
            ended = ImpersonationRepository(_pool()).end_by_jti(str(jti))
    except Exception as exc:
        logger.warning("impersonation_stop_bookkeeping_failed: %s", exc)

    log_audit(
        actor_id=claims.get("impersonated_by"),
        actor_role="superadmin",
        tenant_id=claims.get("tenant_id"),
        target_type="user",
        target_id=claims.get("sub"),
        action="impersonation.stop",
        new_value={"jti": jti, "session_closed": bool(ended)},
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    return success({"stopped": True})
