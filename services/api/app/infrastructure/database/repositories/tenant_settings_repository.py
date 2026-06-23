"""Repository: leitura de configurações/feature flags do tenant.

Fonte: coluna tenants.feature_flags (JSONB, migration 030).
Usado pelo módulo fueling (CD-03) para decidir mock vs dados reais.
"""
from typing import Any
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class TenantSettingsRepository(BaseRepository):
    """Acesso read-only a tenants.feature_flags."""

    def get_feature_flags(self, tenant_id: UUID) -> dict[str, Any]:
        """Retorna o JSONB feature_flags do tenant ({} se ausente)."""
        row = self._execute_one(
            "SELECT feature_flags FROM tenants WHERE id = %s",
            (str(tenant_id),),
        )
        if not row:
            return {}
        flags = row.get("feature_flags")
        return flags if isinstance(flags, dict) else {}
