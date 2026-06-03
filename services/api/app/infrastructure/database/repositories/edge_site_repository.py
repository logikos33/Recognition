"""Repository: EdgeSite + EnrollmentToken — admin side of edge onboarding."""
import logging
from datetime import datetime
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

_TOKEN_INVALID = "enrollment_token_invalid"


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

    def enroll_device(
        self,
        token_hash: str,
        device_id: str,
        device_name: str | None,
        public_key_pem: str,
        fingerprint: str,
    ) -> dict[str, Any]:
        """Atomically consumes enrollment token and registers device.

        tenant_id and site_id are taken from the enrollment_tokens row (server side),
        never from the caller — C-01 compliance.

        Raises ValueError(_TOKEN_INVALID) if token not found, expired, or already used.
        Raises psycopg2.errors.UniqueViolation if device_id already exists for the tenant.
        """
        def _txn(conn, cur) -> dict[str, Any]:
            cur.execute(
                "UPDATE public.enrollment_tokens "
                "SET used_at = now(), used_by_device_id = %s "
                "WHERE token_hash = %s AND used_at IS NULL AND expires_at > now() "
                "RETURNING tenant_id, site_id",
                (device_id, token_hash),
            )
            token_row = cur.fetchone()
            if token_row is None:
                raise ValueError(_TOKEN_INVALID)
            tenant_id = str(token_row["tenant_id"])
            site_id = str(token_row["site_id"])
            cur.execute(
                "INSERT INTO public.device_tokens "
                "(tenant_id, site_id, device_id, device_name, public_key_pem, fingerprint) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "RETURNING id, tenant_id, site_id, device_id, enrolled_at",
                (tenant_id, site_id, device_id, device_name, public_key_pem, fingerprint),
            )
            return dict(cur.fetchone())

        return self._execute_in_transaction(_txn)
