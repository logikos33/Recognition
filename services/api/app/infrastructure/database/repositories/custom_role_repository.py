"""Repository: CustomRoles — permissões customizáveis por tenant."""
from typing import Any, Optional

from app.infrastructure.database.repositories.base import BaseRepository


class CustomRoleRepository(BaseRepository):
    """Queries SQL para tabela public.custom_roles."""

    # ── List ──────────────────────────────────────────────────────────────────

    def list_by_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        """Lista todas as roles do tenant."""
        return self._execute(
            """
            SELECT
                cr.id,
                cr.tenant_id,
                cr.name,
                cr.permissions,
                cr.created_at,
                cr.updated_at,
                COUNT(u.id)::int AS user_count
            FROM public.custom_roles cr
            LEFT JOIN public.users u
                ON u.custom_role_id = cr.id
                AND u.is_active = true
            WHERE cr.tenant_id = %s
            GROUP BY cr.id
            ORDER BY cr.name
            """,
            (tenant_id,),
        )

    # ── Get ───────────────────────────────────────────────────────────────────

    def get_by_id(self, role_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        """Busca role por ID — garante tenant isolation."""
        return self._execute_one(
            """
            SELECT id, tenant_id, name, permissions, created_at, updated_at
            FROM public.custom_roles
            WHERE id = %s AND tenant_id = %s
            """,
            (role_id, tenant_id),
        )

    def get_by_id_superadmin(self, role_id: str) -> Optional[dict[str, Any]]:
        """Busca role por ID sem filtro de tenant (superadmin only)."""
        return self._execute_one(
            """
            SELECT id, tenant_id, name, permissions, created_at, updated_at
            FROM public.custom_roles
            WHERE id = %s
            """,
            (role_id,),
        )

    # ── Create ────────────────────────────────────────────────────────────────

    def create(
        self,
        tenant_id: str,
        name: str,
        permissions: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """Cria nova role customizada."""
        import json
        return self._execute_mutation(
            """
            INSERT INTO public.custom_roles (tenant_id, name, permissions)
            VALUES (%s, %s, %s)
            RETURNING id, tenant_id, name, permissions, created_at, updated_at
            """,
            (tenant_id, name.strip(), json.dumps(permissions)),
        )

    # ── Update ────────────────────────────────────────────────────────────────

    def update(
        self,
        role_id: str,
        tenant_id: str,
        name: Optional[str],
        permissions: Optional[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        """Atualiza nome e/ou permissões de uma role."""
        import json
        return self._execute_mutation(
            """
            UPDATE public.custom_roles
            SET
                name        = COALESCE(%s, name),
                permissions = COALESCE(%s::jsonb, permissions),
                updated_at  = now()
            WHERE id = %s AND tenant_id = %s
            RETURNING id, tenant_id, name, permissions, created_at, updated_at
            """,
            (
                name.strip() if name else None,
                json.dumps(permissions) if permissions is not None else None,
                role_id,
                tenant_id,
            ),
        )

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete(self, role_id: str, tenant_id: str) -> bool:
        """Remove role — somente se sem usuários ativos vinculados."""
        rows = self._execute_mutation_no_return(
            """
            DELETE FROM public.custom_roles
            WHERE id = %s AND tenant_id = %s
            AND NOT EXISTS (
                SELECT 1 FROM public.users
                WHERE custom_role_id = %s
                  AND is_active = true
            )
            """,
            (role_id, tenant_id, role_id),
        )
        return rows > 0

    # ── User role assignment ──────────────────────────────────────────────────

    def get_user_custom_role(
        self, user_id: str, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Retorna role customizada do usuário."""
        return self._execute_one(
            """
            SELECT
                u.id AS user_id,
                u.email,
                u.role AS system_role,
                cr.id AS custom_role_id,
                cr.name AS custom_role_name,
                cr.permissions
            FROM public.users u
            LEFT JOIN public.custom_roles cr ON cr.id = u.custom_role_id
            WHERE u.id = %s AND u.tenant_id = %s
            """,
            (user_id, tenant_id),
        )

    def set_user_custom_role(
        self, user_id: str, tenant_id: str, custom_role_id: Optional[str]
    ) -> bool:
        """Atribui (ou remove, se None) role customizada a um usuário."""
        rows = self._execute_mutation_no_return(
            """
            UPDATE public.users
            SET custom_role_id = %s
            WHERE id = %s AND tenant_id = %s
            """,
            (custom_role_id, user_id, tenant_id),
        )
        return rows > 0

    def count_users_with_role(self, role_id: str) -> int:
        """Conta usuários ativos com essa role customizada."""
        result = self._execute_one(
            """
            SELECT COUNT(*)::int AS cnt
            FROM public.users
            WHERE custom_role_id = %s AND is_active = true
            """,
            (role_id,),
        )
        return result["cnt"] if result else 0
