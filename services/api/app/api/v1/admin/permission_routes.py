"""
Admin Permission Routes (WS7) — registry canônico + permissões por usuário.

Blueprints:
  admin_permissions_bp  url_prefix=/api/v1/admin
    GET /permissions/registry        → registry completo (superadmin)
    GET /users/<id>/permissions      → role + custom_role + overrides + efetivas
    PUT /users/<id>/permissions      → upsert/remove overrides granulares

  my_permissions_bp     url_prefix=/api/v1/permissions
    GET /mine                        → permissões efetivas do usuário logado
                                       (qualquer role — p/ gating de UI)

Segurança:
  - Endpoints admin: @require_superadmin (painel admin é superadmin-only)
  - Toda mutação: log_audit action='user.permissions.updated' (old/new)
  - Chaves validadas contra o registry — desconhecidas → 422
  - Aviso de staleness: permissões valem no PRÓXIMO login (claim no JWT)
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_role, get_tenant_id
from app.core.permissions import (
    ROLE_ORDER,
    normalize_key,
    permissions_for_role,
    registry_as_list,
)
from app.core.responses import error, success
from app.core.tenant import log_audit, require_superadmin
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.custom_role_repository import (
    CustomRoleRepository,
)
from app.infrastructure.database.repositories.permission_override_repository import (
    PermissionOverrideRepository,
)
from app.infrastructure.database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

admin_permissions_bp = Blueprint(
    "admin_permissions", __name__, url_prefix="/api/v1/admin"
)
my_permissions_bp = Blueprint(
    "my_permissions", __name__, url_prefix="/api/v1/permissions"
)


# --------------------------------------------------------------------------- helpers


def _pool() -> DatabasePool:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _permission_service():
    from app.domain.services.permission_service import PermissionService

    pool = _pool()
    return PermissionService(
        PermissionOverrideRepository(pool), CustomRoleRepository(pool)
    )


def _get_target_user(user_id: str) -> dict | None:
    """Busca usuário-alvo com tenant_id/custom_role_id (users é public)."""
    with _pool().get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, email, role, tenant_id, custom_role_id, is_active "
            "FROM public.users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------- routes


@admin_permissions_bp.route("/permissions/registry", methods=["GET"])
@require_superadmin
def get_permissions_registry():  # type: ignore[no-untyped-def]
    """Registry canônico completo — chave, label/descrição pt-BR, grupo, roles."""
    return success({
        "permissions": registry_as_list(),
        "roles": list(ROLE_ORDER),
    })


@admin_permissions_bp.route("/users/<user_id>/permissions", methods=["GET"])
@require_superadmin
def get_user_permissions(user_id: str):  # type: ignore[no-untyped-def]
    """Permissões de um usuário: role base, custom role, overrides e efetivas."""
    try:
        user = _get_target_user(user_id)
        if not user:
            return error("Usuário não encontrado", 404)
        detail = _permission_service().describe(user)
        detail["email"] = user.get("email")
        return success(detail)
    except Exception as exc:
        logger.error("get_user_permissions_error: %s", exc, exc_info=True)
        return error("Erro ao buscar permissões do usuário", 500)


@admin_permissions_bp.route("/users/<user_id>/permissions", methods=["PUT"])
@require_superadmin
def put_user_permissions(user_id: str):  # type: ignore[no-untyped-def]
    """Aplica overrides granulares (grant/deny) a um usuário.

    Body:
      overrides: [{"permission_key": str, "allow": bool}]  — upsert
      remove:    [str]                                     — volta a herdar
      reason:    str opcional                              — auditoria
    """
    try:
        user = _get_target_user(user_id)
        if not user:
            return error("Usuário não encontrado", 404)

        body = request.get_json(silent=True) or {}
        overrides = body.get("overrides") or []
        remove = body.get("remove") or []
        reason = (body.get("reason") or "").strip() or None

        if not isinstance(overrides, list) or not isinstance(remove, list):
            return error("overrides e remove devem ser listas", 422)

        # Validação de chaves contra o registry ANTES de qualquer escrita
        normalized_overrides: list[tuple[str, bool]] = []
        for item in overrides:
            if not isinstance(item, dict):
                return error("Cada override deve ser um objeto", 422)
            key = normalize_key(str(item.get("permission_key") or ""))
            if key is None:
                return error(
                    f"Permissão desconhecida: {item.get('permission_key')}", 422
                )
            normalized_overrides.append((key, bool(item.get("allow", True))))

        normalized_remove: list[str] = []
        for raw_key in remove:
            key = normalize_key(str(raw_key))
            if key is None:
                return error(f"Permissão desconhecida: {raw_key}", 422)
            normalized_remove.append(key)

        service = _permission_service()
        old_state = service.describe(user)

        repo = PermissionOverrideRepository(_pool())
        actor_id = get_current_user_id()
        tenant_id = str(user["tenant_id"]) if user.get("tenant_id") else None
        if tenant_id is None:
            return error("Usuário sem tenant — overrides não aplicáveis", 422)

        for key, allow in normalized_overrides:
            repo.upsert(
                tenant_id=tenant_id,
                user_id=user_id,
                permission_key=key,
                allow=allow,
                granted_by=str(actor_id),
                reason=reason,
            )
        if normalized_remove:
            repo.delete_keys(user_id, normalized_remove)

        new_state = service.describe(user)

        log_audit(
            actor_id=actor_id,
            actor_role=get_role(),
            tenant_id=tenant_id,
            target_type="user",
            target_id=user_id,
            action="user.permissions.updated",
            old_value={"overrides": old_state["overrides"]},
            new_value={
                "overrides": new_state["overrides"],
                "removed": normalized_remove,
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )

        return success(new_state)
    except Exception as exc:
        logger.error("put_user_permissions_error: %s", exc, exc_info=True)
        return error("Erro ao atualizar permissões do usuário", 500)


@my_permissions_bp.route("/mine", methods=["GET"])
@jwt_required()
def get_my_permissions():  # type: ignore[no-untyped-def]
    """Permissões efetivas do usuário logado — recalculadas do banco.

    Disponível para QUALQUER role (gating de UI de não-admin).
    Fallback: default_roles da role do JWT se o banco estiver indisponível.
    """
    role = get_role()
    try:
        user_id = get_current_user_id()
        pool = DatabasePool.get_instance()
        if pool is not None:
            user = UserRepository(pool).get_by_id(user_id)
            if user:
                # tenant do JWT como fallback (get_by_id pode não ter tenant em
                # cenários de seed antigos)
                if not user.get("tenant_id"):
                    user["tenant_id"] = get_tenant_id()
                perms = _permission_service().resolve_effective(user)
                return success({"role": role, "permissions": perms})
    except Exception as exc:
        logger.warning("get_my_permissions_fallback: %s", exc)
    return success({"role": role, "permissions": permissions_for_role(role)})
