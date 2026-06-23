"""Repository: EdgeCommand — fila de comandos remotos para o edge (migration 056)."""
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class EdgeCommandRepository(BaseRepository):
    """SQL para public.edge_commands."""

    def create(
        self,
        tenant_id: str,
        site_id: str,
        command_type: str,
        payload: dict,
        command_id: str,
        created_by: str | None,
    ) -> dict[str, Any] | None:
        """Cria comando ou ignora se command_id já existe (idempotência)."""
        return self._execute_mutation(
            """
            INSERT INTO public.edge_commands (
                tenant_id, site_id, command_type, payload, command_id, created_by
            ) VALUES (%s, %s, %s, %s::jsonb, %s, %s)
            ON CONFLICT (tenant_id, command_id) DO NOTHING
            RETURNING id, status, created_at
            """,
            (
                tenant_id, site_id, command_type,
                __import__("json").dumps(payload), command_id, created_by,
            ),
        )

    def list_pending(self, site_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Lista comandos pendentes para um site (edge polling)."""
        limit = min(max(limit, 1), 200)
        return self._execute(
            """
            SELECT id, command_type, payload, command_id, created_at
            FROM public.edge_commands
            WHERE site_id = %s AND status = 'pending'
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (site_id, limit),
        )

    def update_status(
        self,
        command_id_str: str,
        tenant_id: str,
        status: str,
        result: dict | None = None,
    ) -> dict[str, Any] | None:
        """Atualiza status de um comando (done/failed/expired)."""
        import json
        from datetime import datetime, timezone
        completed_at = datetime.now(timezone.utc) if status in ("done", "failed") else None
        return self._execute_mutation(
            """
            UPDATE public.edge_commands
            SET status = %s,
                result = %s::jsonb,
                completed_at = %s,
                dispatched_at = COALESCE(dispatched_at, NOW())
            WHERE command_id = %s AND tenant_id = %s
            RETURNING id, status, completed_at
            """,
            (
                status,
                json.dumps(result) if result is not None else None,
                completed_at,
                command_id_str,
                tenant_id,
            ),
        )

    def list_by_site(
        self,
        tenant_id: str,
        site_id: str,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Lista comandos de um site (para admin/dashboard)."""
        limit = min(max(limit, 1), 200)
        conditions = ["tenant_id = %s", "site_id = %s"]
        params: list = [tenant_id, site_id]
        if status:
            conditions.append("status = %s")
            params.append(status)
        where = " AND ".join(conditions)
        params.append(limit)
        return self._execute(
            f"SELECT id, command_type, payload, status, command_id, "  # noqa: S608
            f"created_at, dispatched_at, completed_at "
            f"FROM public.edge_commands WHERE {where} "
            f"ORDER BY created_at DESC LIMIT %s",
            tuple(params),
        )
