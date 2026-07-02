"""
Repository: integrations — credenciais cifradas por tenant.

Regras de segurança:
- secret_encrypted NUNCA é retornado em list/get públicos
- list_integrations e get_integration omitem a coluna secret_encrypted
- Apenas upsert_integration recebe/persiste o campo cifrado
- update_status é a única mutação sem secret
"""
import logging
from typing import Any
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

_SAFE_COLS = """
    id, tenant_id, integration_type, label, config,
    last4, status, last_tested_at, last_error, created_at, updated_at
"""


class IntegrationRepository(BaseRepository):
    """CRUD para public.integrations (sem vazamento de secret_encrypted)."""

    # ------------------------------------------------------------------ reads

    def list_integrations(self, tenant_id: UUID) -> list[dict[str, Any]]:
        """Lista integrações do tenant — sem secret_encrypted."""
        rows = self._execute(
            f"SELECT {_SAFE_COLS} FROM public.integrations "
            "WHERE tenant_id = %s ORDER BY integration_type, label",
            (str(tenant_id),),
        )
        return [dict(r) for r in rows]

    def get_integration(
        self, tenant_id: UUID, integration_type: str
    ) -> dict[str, Any] | None:
        """Retorna integração por tipo — sem secret_encrypted."""
        row = self._execute_one(
            f"SELECT {_SAFE_COLS} FROM public.integrations "
            "WHERE tenant_id = %s AND integration_type = %s",
            (str(tenant_id), integration_type),
        )
        return dict(row) if row else None

    def get_secret_encrypted(
        self, tenant_id: UUID, integration_type: str
    ) -> str | None:
        """Retorna APENAS secret_encrypted — uso interno do service."""
        row = self._execute_one(
            "SELECT secret_encrypted FROM public.integrations "
            "WHERE tenant_id = %s AND integration_type = %s",
            (str(tenant_id), integration_type),
        )
        if not row:
            return None
        return row.get("secret_encrypted")

    # ----------------------------------------------------------------- writes

    def upsert_integration(
        self,
        tenant_id: UUID,
        integration_type: str,
        label: str,
        config: dict[str, Any],
        secret_encrypted: str | None,
        last4: str | None,
    ) -> dict[str, Any]:
        """INSERT … ON CONFLICT DO UPDATE — retorna row sem secret."""
        import json

        row = self._execute_mutation(
            """
            INSERT INTO public.integrations
              (tenant_id, integration_type, label, config,
               secret_encrypted, last4, status, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'unconfigured', NOW())
            ON CONFLICT (tenant_id, integration_type, label)
            DO UPDATE SET
              label            = EXCLUDED.label,
              config           = EXCLUDED.config,
              secret_encrypted = COALESCE(EXCLUDED.secret_encrypted,
                                          public.integrations.secret_encrypted),
              last4            = COALESCE(EXCLUDED.last4,
                                          public.integrations.last4),
              updated_at       = NOW()
            RETURNING
              id, tenant_id, integration_type, label, config,
              last4, status, last_tested_at, last_error, created_at, updated_at
            """,
            (
                str(tenant_id),
                integration_type,
                label,
                json.dumps(config),
                secret_encrypted,
                last4,
            ),
        )
        return dict(row) if row else {}

    def update_status(
        self,
        integration_id: str,
        status: str,
        last_error: str | None = None,
    ) -> None:
        """Atualiza status e last_tested_at após teste de conectividade."""
        self._execute_mutation_no_return(
            """
            UPDATE public.integrations
            SET status        = %s,
                last_error    = %s,
                last_tested_at = NOW(),
                updated_at    = NOW()
            WHERE id = %s
            """,
            (status, last_error, integration_id),
        )

    def delete_integration(
        self, tenant_id: UUID, integration_type: str
    ) -> int:
        """Remove integração (apenas superadmin). Retorna rowcount."""
        return self._execute_mutation_no_return(
            "DELETE FROM public.integrations "
            "WHERE tenant_id = %s AND integration_type = %s",
            (str(tenant_id), integration_type),
        )
