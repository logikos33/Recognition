"""Repository: auditoria por requisição do contexto de tenant assumido
(migration 108 — "assumir contexto").

Distinto de ImpersonationRepository (migration 086, WS6): aquela rastreia
entrada/saída de uma visualização "ver como um usuário"; esta registra CADA
requisição feita sob um token de contexto de tenant assumido (identidade do
superadmin preservada, apenas tenant_id/tenant_schema trocados).
"""
from typing import Any, Optional

from app.infrastructure.database.repositories.base import BaseRepository


class TenantContextAuditRepository(BaseRepository):
    """Insert-only de public.tenant_context_audit."""

    def record(
        self,
        tenant_id: str,
        impersonator_user_id: str,
        method: str,
        path: str,
        status_code: int | None,
    ) -> Optional[dict[str, Any]]:
        """Registra uma requisição feita sob contexto de tenant assumido."""
        return self._execute_mutation(
            """
            INSERT INTO public.tenant_context_audit
              (tenant_id, impersonator_user_id, method, path, status_code)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (
                str(tenant_id),
                str(impersonator_user_id),
                method,
                path[:2048],
                status_code,
            ),
        )
