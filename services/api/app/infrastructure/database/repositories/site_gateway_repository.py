"""Repository: SiteGateway — gateway MikroTik/WireGuard do site (migration 057)."""
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class SiteGatewayRepository(BaseRepository):
    """SQL para public.site_gateways."""

    def get_by_site(self, tenant_id: str, site_id: str) -> dict[str, Any] | None:
        return self._execute_one(
            """
            SELECT id, kind, model, wg_public_key, wg_endpoint, lan_subnet,
                   status, last_seen, config, created_at, updated_at
            FROM public.site_gateways
            WHERE tenant_id = %s AND site_id = %s
            """,
            (tenant_id, site_id),
        )

    def upsert(
        self,
        tenant_id: str,
        site_id: str,
        kind: str,
        model: str | None,
        wg_public_key: str | None,
        wg_endpoint: str | None,
        lan_subnet: str | None,
        config: dict,
    ) -> dict[str, Any] | None:
        """Cria ou atualiza gateway do site (máximo 1 por site)."""
        return self._execute_mutation(
            """
            INSERT INTO public.site_gateways (
                tenant_id, site_id, kind, model, wg_public_key,
                wg_endpoint, lan_subnet, config
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (site_id) DO UPDATE SET
                kind = EXCLUDED.kind,
                model = EXCLUDED.model,
                wg_public_key = EXCLUDED.wg_public_key,
                wg_endpoint = EXCLUDED.wg_endpoint,
                lan_subnet = EXCLUDED.lan_subnet,
                config = EXCLUDED.config,
                updated_at = NOW()
            RETURNING id, kind, status, created_at, updated_at
            """,
            (
                tenant_id, site_id, kind, model, wg_public_key,
                wg_endpoint, lan_subnet, __import__("json").dumps(config),
            ),
        )

    def update_status(
        self, tenant_id: str, site_id: str, status: str
    ) -> dict[str, Any] | None:
        return self._execute_mutation(
            """
            UPDATE public.site_gateways
            SET status = %s, last_seen = NOW(), updated_at = NOW()
            WHERE tenant_id = %s AND site_id = %s
            RETURNING id, status, last_seen
            """,
            (status, tenant_id, site_id),
        )
