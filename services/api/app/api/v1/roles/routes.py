"""
Recognition — Custom Roles Routes.

Endpoints de permissões customizáveis por tenant.
Role-gated: admin (vê seu tenant) e superadmin (vê todos).

GET    /api/admin/roles                  — listar roles do tenant
POST   /api/admin/roles                  — criar role
PUT    /api/admin/roles/<role_id>         — editar role
DELETE /api/admin/roles/<role_id>         — deletar role (sem usuários)
GET    /api/admin/users/<user_id>/role    — ver role customizada do usuário
PUT    /api/admin/users/<user_id>/role    — atribuir role customizada ao usuário
"""
import logging

from flask import Blueprint, request

from app.core.auth import get_role, get_tenant_id
from app.core.responses import error, success
from app.core.exceptions import EpiMonitorError
from app.core.tenant import require_admin
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.custom_role_repository import (
    CustomRoleRepository,
)

logger = logging.getLogger(__name__)

roles_bp = Blueprint("roles", __name__, url_prefix="/api/admin")


def _repo() -> CustomRoleRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return CustomRoleRepository(pool)


def _resolve_tenant_id() -> str:
    """
    Retorna o tenant_id correto para a operação.

    - superadmin: aceita ?tenant_id= na query string; fallback para o seu próprio
    - admin: sempre o seu próprio tenant (tenant isolation)
    """
    role = get_role()
    if role == "superadmin":
        override = request.args.get("tenant_id") or request.get_json(
            silent=True, force=True
        ) and request.get_json(silent=True, force=True).get("tenant_id")  # type: ignore[union-attr]
        if override:
            return str(override)
    return get_tenant_id()


# ── List roles ────────────────────────────────────────────────────────────────

@roles_bp.route("/roles", methods=["GET"])
@require_admin
def list_roles():  # type: ignore[no-untyped-def]
    """
    ---
    tags: [roles]
    summary: Listar roles customizadas do tenant
    security: [{Bearer: []}]
    parameters:
      - in: query
        name: tenant_id
        schema: {type: string}
        description: Superadmin only — tenant alvo
    responses:
      200:
        description: Lista de roles
    """
    try:
        tenant_id = _resolve_tenant_id()
        repo = _repo()
        roles = repo.list_by_tenant(tenant_id)
        return success({"roles": roles, "total": len(roles)})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_roles_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# ── Create role ───────────────────────────────────────────────────────────────

@roles_bp.route("/roles", methods=["POST"])
@require_admin
def create_role():  # type: ignore[no-untyped-def]
    """
    ---
    tags: [roles]
    summary: Criar role customizada
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [name]
          properties:
            name: {type: string}
            permissions: {type: object}
            tenant_id: {type: string, description: "superadmin only"}
    responses:
      201:
        description: Role criada
      400:
        description: Dados inválidos ou nome duplicado
    """
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        if not name:
            return error("Campo 'name' é obrigatório", 400)

        permissions = data.get("permissions") or {}
        if not isinstance(permissions, dict):
            return error("Campo 'permissions' deve ser um objeto JSON", 400)

        tenant_id = _resolve_tenant_id()
        repo = _repo()
        role = repo.create(tenant_id=tenant_id, name=name, permissions=permissions)
        if not role:
            return error("Erro ao criar role", 500)

        return success({"role": role}, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        if "custom_roles_tenant_name" in str(exc):
            return error(f"Já existe uma role com o nome '{name}' neste tenant", 409)
        logger.error("create_role_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# ── Update role ───────────────────────────────────────────────────────────────

@roles_bp.route("/roles/<role_id>", methods=["PUT"])
@require_admin
def update_role(role_id: str):  # type: ignore[no-untyped-def]
    """
    ---
    tags: [roles]
    summary: Editar role customizada
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: role_id
        required: true
        schema: {type: string}
      - in: body
        name: body
        schema:
          properties:
            name: {type: string}
            permissions: {type: object}
    responses:
      200:
        description: Role atualizada
      404:
        description: Role não encontrada
    """
    try:
        data = request.get_json() or {}
        name = data.get("name")
        permissions = data.get("permissions")

        if name is not None and not str(name).strip():
            return error("Nome não pode ser vazio", 400)

        tenant_id = _resolve_tenant_id()
        repo = _repo()

        updated = repo.update(
            role_id=role_id,
            tenant_id=tenant_id,
            name=str(name).strip() if name else None,
            permissions=permissions,
        )
        if not updated:
            return error("Role não encontrada", 404)

        return success({"role": updated})
    except EpiMonitorError:
        raise
    except Exception as exc:
        if "custom_roles_tenant_name" in str(exc):
            return error("Já existe uma role com esse nome neste tenant", 409)
        logger.error("update_role_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# ── Delete role ───────────────────────────────────────────────────────────────

@roles_bp.route("/roles/<role_id>", methods=["DELETE"])
@require_admin
def delete_role(role_id: str):  # type: ignore[no-untyped-def]
    """
    ---
    tags: [roles]
    summary: Deletar role customizada (apenas se sem usuários)
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: role_id
        required: true
        schema: {type: string}
    responses:
      200:
        description: Role deletada
      409:
        description: Role possui usuários vinculados
      404:
        description: Role não encontrada
    """
    try:
        tenant_id = _resolve_tenant_id()
        repo = _repo()

        # Verificar usuários antes para mensagem clara
        user_count = repo.count_users_with_role(role_id)
        if user_count > 0:
            return error(
                f"Esta role possui {user_count} usuário(s) ativo(s) vinculado(s). "
                "Desatribua a role de todos os usuários antes de deletar.",
                409,
            )

        deleted = repo.delete(role_id=role_id, tenant_id=tenant_id)
        if not deleted:
            return error("Role não encontrada", 404)

        return success({"deleted": True, "role_id": role_id})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("delete_role_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# ── Get user custom role ──────────────────────────────────────────────────────

@roles_bp.route("/users/<user_id>/role", methods=["GET"])
@require_admin
def get_user_role(user_id: str):  # type: ignore[no-untyped-def]
    """
    ---
    tags: [roles]
    summary: Ver role customizada do usuário
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: user_id
        required: true
        schema: {type: string}
    responses:
      200:
        description: Role do usuário
      404:
        description: Usuário não encontrado
    """
    try:
        tenant_id = _resolve_tenant_id()
        repo = _repo()
        data = repo.get_user_custom_role(user_id=user_id, tenant_id=tenant_id)
        if not data:
            return error("Usuário não encontrado", 404)
        return success(data)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_user_role_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# ── Set user custom role ──────────────────────────────────────────────────────

@roles_bp.route("/users/<user_id>/role", methods=["PUT"])
@require_admin
def set_user_role(user_id: str):  # type: ignore[no-untyped-def]
    """
    ---
    tags: [roles]
    summary: Atribuir (ou remover) role customizada ao usuário
    security: [{Bearer: []}]
    parameters:
      - in: path
        name: user_id
        required: true
        schema: {type: string}
      - in: body
        name: body
        required: true
        schema:
          properties:
            custom_role_id: {type: string, description: "null para remover role"}
    responses:
      200:
        description: Role atualizada
      404:
        description: Usuário não encontrado
    """
    try:
        data = request.get_json() or {}
        custom_role_id: str | None = data.get("custom_role_id")  # None = remover

        tenant_id = _resolve_tenant_id()
        repo = _repo()

        # Validar se role pertence ao tenant (se não for remoção)
        if custom_role_id:
            role = repo.get_by_id(role_id=custom_role_id, tenant_id=tenant_id)
            if not role:
                return error("Role não encontrada neste tenant", 404)

        updated = repo.set_user_custom_role(
            user_id=user_id,
            tenant_id=tenant_id,
            custom_role_id=custom_role_id,
        )
        if not updated:
            return error("Usuário não encontrado", 404)

        return success({"updated": True, "user_id": user_id, "custom_role_id": custom_role_id})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("set_user_role_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
