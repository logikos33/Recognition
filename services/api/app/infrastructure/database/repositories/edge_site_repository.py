"""Repository: EdgeSite + EnrollmentToken — admin side of edge onboarding."""
import logging
from datetime import datetime
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class EdgeSiteRepository(BaseRepository):
    """SQL para public.edge_sites e public.enrollment_tokens."""

    def create_site(
        self,
        tenant_id: str,
        name: str,
        location: str | None,
        deployment_mode: str,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Cria site em public.edge_sites. Retorna row completa."""
        row = self._execute_mutation(
            """
            INSERT INTO public.edge_sites
                (tenant_id, name, location, deployment_mode, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, tenant_id, name, description, location,
                      deployment_mode, status, created_at, updated_at, created_by
            """,
            (tenant_id, name, location, deployment_mode, created_by),
        )
        return row  # type: ignore[return-value]

    def list_sites(self, tenant_id: str) -> list[dict[str, Any]]:
        """Lista sites do tenant, ordenados por criação desc."""
        return self._execute(
            """
            SELECT id, tenant_id, name, description, location,
                   deployment_mode, status, created_at, updated_at, created_by
            FROM public.edge_sites
            WHERE tenant_id = %s
            ORDER BY created_at DESC
            """,
            (tenant_id,),
        )

    def get_site_by_id(self, site_id: str, tenant_id: str) -> dict[str, Any] | None:
        """Retorna None se site_id não pertencer ao tenant — bloqueia cross-tenant (C-01)."""
        return self._execute_one(
            "SELECT id, tenant_id, name, location, deployment_mode, status "
            "FROM public.edge_sites "
            "WHERE id = %s AND tenant_id = %s",
            (site_id, tenant_id),
        )

    def create_enrollment_token(
        self,
        site_id: str,
        tenant_id: str,
        token_hash: str,
        expires_at: datetime,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Insere enrollment token — apenas hash armazenado, nunca plaintext."""
        row = self._execute_mutation(
            """
            INSERT INTO public.enrollment_tokens
                (tenant_id, site_id, token_hash, expires_at, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, tenant_id, site_id, expires_at, used_at, created_at
            """,
            (tenant_id, site_id, token_hash, expires_at, created_by),
        )
        return row  # type: ignore[return-value]
