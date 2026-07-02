"""Repository: sessões de impersonation "ver como" (migration 086 — WS6).

Rastreio forense de entrada/saída de visualizações: superadmin vê a
plataforma como um usuário-alvo. NUNCA armazena credencial/token do alvo —
apenas o jti do token emitido, para correlação.
"""
from typing import Any, Optional

from app.infrastructure.database.repositories.base import BaseRepository


class ImpersonationRepository(BaseRepository):
    """CRUD mínimo de public.impersonation_sessions."""

    def start(
        self,
        tenant_id: str,
        superadmin_id: str,
        target_user_id: str,
        jti: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Optional[dict[str, Any]]:
        """Registra o início de uma visualização. Retorna {id, started_at}."""
        return self._execute_mutation(
            """
            INSERT INTO public.impersonation_sessions
              (tenant_id, superadmin_id, target_user_id, jti, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, started_at
            """,
            (
                str(tenant_id),
                str(superadmin_id),
                str(target_user_id),
                jti,
                ip_address,
                (user_agent or "")[:500] if user_agent else None,
            ),
        )

    def end_by_jti(self, jti: str) -> Optional[dict[str, Any]]:
        """Marca ended_at da sessão ativa correlacionada ao jti."""
        return self._execute_mutation(
            """
            UPDATE public.impersonation_sessions
            SET ended_at = now()
            WHERE jti = %s AND ended_at IS NULL
            RETURNING id, ended_at
            """,
            (jti,),
        )
