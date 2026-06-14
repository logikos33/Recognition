"""Repository: public.active_sessions (migration 029).

Registra sessões de login (jti do JWT) e revoga sessões anteriores
quando a política single_session do tenant está ativa.
"""
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class SessionRepository(BaseRepository):
    """Queries SQL para public.active_sessions."""

    def create_session(
        self,
        user_id: str,
        tenant_id: str,
        jti: str,
        ip_address: str | None,
        user_agent: str | None,
        expires_at: Any,
    ) -> dict[str, Any] | None:
        """Registra nova sessão ativa. Retorna a row criada."""
        return self._execute_mutation(
            """
            INSERT INTO public.active_sessions
              (user_id, tenant_id, jti, ip_address, user_agent, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (jti) DO NOTHING
            RETURNING id, user_id, jti, expires_at
            """,
            (str(user_id), str(tenant_id), jti, ip_address, user_agent, expires_at),
        )

    def revoke_other_sessions(self, user_id: str, keep_jti: str) -> list[dict[str, Any]]:
        """Revoga todas as sessões ativas do usuário, exceto keep_jti.

        Retorna as sessões revogadas (jti + expires_at) para que o caller
        propague a revogação ao blocklist (Redis).
        """
        return self._execute(
            """
            UPDATE public.active_sessions
            SET revoked_at = NOW(), revoked_by = %s
            WHERE user_id = %s AND revoked_at IS NULL AND jti != %s
            RETURNING jti, expires_at
            """,
            (str(user_id), str(user_id), keep_jti),
        )
