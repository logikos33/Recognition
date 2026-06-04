"""Repository: EdgeSite + EnrollmentToken + DeviceToken — admin side of edge onboarding."""
import logging
from datetime import datetime
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

_TOKEN_INVALID = "enrollment_token_invalid"

# Frozenset de colunas editáveis — geração dinâmica de SET cláusula é segura
# porque os nomes vêm daqui, nunca do input do usuário.
_UPDATABLE_SITE_FIELDS: frozenset[str] = frozenset(
    {"name", "location", "status", "deployment_mode"}
)


class EdgeSiteRepository(BaseRepository):
    """SQL para public.edge_sites, public.enrollment_tokens e public.device_tokens."""

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

    def get_site_detail(self, site_id: str, tenant_id: str) -> dict[str, Any] | None:
        """Retorna site com contagem de devices e último heartbeat para derivar saúde.

        Retorna None se site não pertencer ao tenant (C-01).
        """
        return self._execute_one(
            """
            SELECT
                s.id, s.tenant_id, s.name, s.description, s.location,
                s.deployment_mode, s.status, s.created_at, s.updated_at, s.created_by,
                COALESCE(dc.device_count, 0) AS device_count,
                lh.received_at              AS last_heartbeat_at,
                lh.heartbeat_status
            FROM public.edge_sites s
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS device_count
                FROM public.device_tokens
                WHERE site_id = s.id AND tenant_id = s.tenant_id
            ) dc ON true
            LEFT JOIN LATERAL (
                SELECT received_at, status AS heartbeat_status
                FROM public.edge_heartbeats
                WHERE site_id = s.id AND tenant_id = s.tenant_id
                ORDER BY received_at DESC
                LIMIT 1
            ) lh ON true
            WHERE s.id = %s AND s.tenant_id = %s
            """,
            (site_id, tenant_id),
        )

    def update_site(
        self,
        site_id: str,
        tenant_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Atualização parcial do site. Retorna None se cross-tenant (C-01).

        Campos editáveis: name, location, status, deployment_mode.
        tenant_id é imutável — nunca presente em updates (regra da route).
        Se updates estiver vazio, retorna o site sem alterar.
        """
        filtered = {k: v for k, v in updates.items() if k in _UPDATABLE_SITE_FIELDS}
        if not filtered:
            return self.get_site_by_id(site_id, tenant_id)

        # Nomes de colunas vêm exclusivamente de _UPDATABLE_SITE_FIELDS — seguro.
        set_clauses = ", ".join(f"{col} = %s" for col in filtered)
        params = tuple(filtered.values()) + (site_id, tenant_id)

        return self._execute_mutation(
            f"UPDATE public.edge_sites "
            f"SET {set_clauses} "
            f"WHERE id = %s AND tenant_id = %s "
            f"RETURNING id, tenant_id, name, description, location, "
            f"deployment_mode, status, created_at, updated_at, created_by",
            params,
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

    def list_enrollment_tokens(
        self, tenant_id: str, site_id: str
    ) -> list[dict[str, Any]]:
        """Lista enrollment tokens do site — sem token_hash/plaintext (C-05)."""
        return self._execute(
            """
            SELECT id, created_at, expires_at, used_at, used_by_device_id
            FROM public.enrollment_tokens
            WHERE tenant_id = %s AND site_id = %s
            ORDER BY created_at DESC
            """,
            (tenant_id, site_id),
        )

    def get_enrollment_token_by_id(
        self, token_id: str, tenant_id: str
    ) -> dict[str, Any] | None:
        """Busca token por id e tenant_id — para checar estado antes de revogar."""
        return self._execute_one(
            """
            SELECT id, tenant_id, site_id, expires_at, used_at, created_at
            FROM public.enrollment_tokens
            WHERE id = %s AND tenant_id = %s
            """,
            (token_id, tenant_id),
        )

    def revoke_enrollment_token_if_unused(
        self, token_id: str, tenant_id: str
    ) -> dict[str, Any] | None:
        """Invalida token não utilizado — SET expires_at = now().

        Retorna None se token já foi usado (caller distingue de 404 consultando
        get_enrollment_token_by_id antes).
        Idempotente para token já expirado: SET expires_at = now() é no-op semântico.
        """
        return self._execute_mutation(
            """
            UPDATE public.enrollment_tokens
            SET expires_at = now()
            WHERE id = %s AND tenant_id = %s AND used_at IS NULL
            RETURNING id, tenant_id, site_id, expires_at, used_at, created_at
            """,
            (token_id, tenant_id),
        )

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

    # ------------------------------------------------------------------
    # Fleet overview counts (task-016)
    # ------------------------------------------------------------------

    def get_site_status_counts(self, tenant_id: str) -> list[dict[str, Any]]:
        """Retorna [{status, count}] de todos os sites do tenant agrupados por status."""
        return self._execute(
            """
            SELECT status, COUNT(*) AS count
            FROM public.edge_sites
            WHERE tenant_id = %s
            GROUP BY status
            """,
            (tenant_id,),
        )

    def get_device_fleet_counts(
        self, tenant_id: str, online_threshold_seconds: int
    ) -> dict[str, int]:
        """Contagens de devices para o tenant: total, online, revoked.

        online = last_seen_at dentro dos últimos online_threshold_seconds
        (mesmo limiar de EDGE_OFFLINE_THRESHOLD_SECONDS usado para sites).
        """
        row = self._execute_one(
            """
            SELECT
                COUNT(*)                                                   AS total,
                COUNT(*) FILTER (WHERE revoked = true)                     AS revoked,
                COUNT(*) FILTER (
                    WHERE revoked = false
                      AND last_seen_at >= now() - (%s * interval '1 second')
                )                                                          AS online
            FROM public.device_tokens
            WHERE tenant_id = %s
            """,
            (online_threshold_seconds, tenant_id),
        )
        if row is None:
            return {"total": 0, "online": 0, "revoked": 0}
        return {
            "total": int(row["total"]),
            "online": int(row["online"]),
            "revoked": int(row["revoked"]),
        }

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    def list_devices(self, tenant_id: str, site_id: str) -> list[dict[str, Any]]:
        """Lista devices de um site — sem public_key_pem nem fingerprint (C-05)."""
        return self._execute(
            """
            SELECT id, device_id, device_name, revoked, last_seen_at, enrolled_at
            FROM public.device_tokens
            WHERE tenant_id = %s AND site_id = %s
            ORDER BY enrolled_at DESC
            """,
            (tenant_id, site_id),
        )

    def revoke_device(
        self,
        device_pk: str,
        tenant_id: str,
        revoked_by: str,
        reason: str | None = None,
    ) -> dict[str, Any] | None:
        """Revoga device — idempotente (já revogado preserva revoked_at/by originais).

        Retorna None se device_pk não pertencer ao tenant (C-01 — não vaza existência).
        """
        return self._execute_mutation(
            """
            UPDATE public.device_tokens
            SET revoked            = true,
                revoked_at         = COALESCE(revoked_at, now()),
                revoked_by         = COALESCE(revoked_by, %s::uuid),
                revocation_reason  = COALESCE(revocation_reason, %s)
            WHERE id = %s AND tenant_id = %s
            RETURNING id, device_id, revoked, revoked_at, revoked_by, revocation_reason
            """,
            (revoked_by, reason, device_pk, tenant_id),
        )
