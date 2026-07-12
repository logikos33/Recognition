"""Repository: EdgeEvent — ingest e query de eventos vindos do edge (migration 055)."""
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class EdgeEventRepository(BaseRepository):
    """SQL para public.edge_events."""

    def ingest(
        self,
        tenant_id: str,
        site_id: str,
        device_id: str | None,
        camera_id: str | None,
        module: str | None,
        event_type: str,
        payload: dict,
        evidence_r2_key: str | None,
        occurred_at: str | None,
        batch_id: str | None,
        dedup_key: str | None,
    ) -> dict[str, Any] | None:
        """Insere um evento; ON CONFLICT na dedup_key faz DO NOTHING (idempotência)."""
        return self._execute_mutation(
            """
            INSERT INTO public.edge_events (
                tenant_id, site_id, device_id, camera_id, module,
                event_type, payload, evidence_r2_key, occurred_at,
                batch_id, dedup_key
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, dedup_key) WHERE dedup_key IS NOT NULL DO NOTHING
            RETURNING id, received_at
            """,
            (
                tenant_id, site_id, device_id, camera_id, module,
                event_type, __import__("json").dumps(payload),
                evidence_r2_key, occurred_at, batch_id, dedup_key,
            ),
        )

    def list_by_site(
        self,
        tenant_id: str,
        site_id: str,
        limit: int = 100,
        before: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lista eventos de um site, paginado por cursor temporal."""
        limit = min(max(limit, 1), 500)
        conditions = ["tenant_id = %s", "site_id = %s"]
        params: list = [tenant_id, site_id]
        if before:
            conditions.append("received_at < %s")
            params.append(before)
        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type)
        where = " AND ".join(conditions)
        params.append(limit)
        return self._execute(
            f"SELECT id, device_id, camera_id, module, event_type, payload, "  # noqa: S608
            f"evidence_r2_key, occurred_at, received_at, dedup_key "
            f"FROM public.edge_events WHERE {where} "
            f"ORDER BY received_at DESC LIMIT %s",
            tuple(params),
        )
