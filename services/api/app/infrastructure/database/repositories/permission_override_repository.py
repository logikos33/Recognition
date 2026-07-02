"""Repository: UserPermissionOverrides — grant/deny granular por usuário (WS7).

Tabela: public.user_permission_overrides (migration 085).
Precedência aplicada no PermissionService: deny > allow > custom_role > role.
"""
from typing import Any, Optional

from app.infrastructure.database.repositories.base import BaseRepository


class PermissionOverrideRepository(BaseRepository):
    """Queries SQL para public.user_permission_overrides."""

    def list_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Lista overrides de um usuário."""
        return self._execute(
            """
            SELECT id, tenant_id, user_id, permission_key, allow,
                   granted_by, reason, created_at, updated_at
            FROM public.user_permission_overrides
            WHERE user_id = %s
            ORDER BY permission_key
            """,
            (user_id,),
        )

    def list_by_user_and_tenant(
        self, user_id: str, tenant_id: str
    ) -> list[dict[str, Any]]:
        """Lista overrides de um usuário com isolamento de tenant (C-01)."""
        return self._execute(
            """
            SELECT id, tenant_id, user_id, permission_key, allow,
                   granted_by, reason, created_at, updated_at
            FROM public.user_permission_overrides
            WHERE user_id = %s AND tenant_id = %s
            ORDER BY permission_key
            """,
            (user_id, tenant_id),
        )

    def upsert(
        self,
        tenant_id: str,
        user_id: str,
        permission_key: str,
        allow: bool,
        granted_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Cria ou atualiza um override (único por user_id + permission_key)."""
        return self._execute_mutation(
            """
            INSERT INTO public.user_permission_overrides
                (tenant_id, user_id, permission_key, allow, granted_by, reason)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, permission_key)
            DO UPDATE SET
                allow      = EXCLUDED.allow,
                granted_by = EXCLUDED.granted_by,
                reason     = EXCLUDED.reason,
                updated_at = now()
            RETURNING id, tenant_id, user_id, permission_key, allow,
                      granted_by, reason, created_at, updated_at
            """,
            (tenant_id, user_id, permission_key, allow, granted_by, reason),
        )

    def delete_keys(self, user_id: str, permission_keys: list[str]) -> int:
        """Remove overrides específicos de um usuário. Retorna nº removido."""
        if not permission_keys:
            return 0
        return self._execute_mutation_no_return(
            """
            DELETE FROM public.user_permission_overrides
            WHERE user_id = %s AND permission_key = ANY(%s)
            """,
            (user_id, permission_keys),
        )

    def count_by_users(self, user_ids: list[str]) -> dict[str, int]:
        """Conta overrides por usuário (para badge 'Customizado' na listagem)."""
        if not user_ids:
            return {}
        rows = self._execute(
            """
            SELECT user_id::text AS user_id, COUNT(*)::int AS cnt
            FROM public.user_permission_overrides
            WHERE user_id = ANY(%s::uuid[])
            GROUP BY user_id
            """,
            (user_ids,),
        )
        return {row["user_id"]: row["cnt"] for row in rows}
