"""Repository: edge_telemetry_samples — telemetria do Jetson por site.

Tabela public.edge_telemetry_samples (migration 105): amostras de telemetria do
edge (GPU/temps/rails de potência/RAM/FPS) etiquetadas por fase, escopadas por
tenant (C-01) e opcionalmente por site. Alimenta a seção "Telemetria do Edge"
do dashboard (task-112) — histórico via read + ao vivo via Redis→SocketIO.

Padrão-casa: BaseRepository (psycopg2/RealDictCursor), zero f-string com input,
todo valor via %s. Append-only (série temporal).
"""
import json
from datetime import datetime
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class EdgeTelemetryRepository(BaseRepository):
    """SQL para public.edge_telemetry_samples (tenant-scoped)."""

    def insert_samples(
        self,
        tenant_id: str,
        site_id: str | None,
        samples: list[dict[str, Any]],
    ) -> int:
        """Insert batch de amostras. Retorna total de linhas inseridas.

        Cada item: {"sampled_at": iso8601, "label": str?, "payload": dict}.
        """
        if not samples:
            return 0
        params = [
            (
                tenant_id,
                site_id,
                s.get("label"),
                s["sampled_at"],
                json.dumps(s.get("payload") or {}),
            )
            for s in samples
        ]
        return self._execute_many(
            "INSERT INTO public.edge_telemetry_samples "
            "(tenant_id, site_id, label, sampled_at, payload) "
            "VALUES (%s, %s, %s, %s, %s::jsonb)",
            params,
        )

    def timeseries(
        self,
        tenant_id: str,
        since: datetime,
        site_id: str | None = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """Série temporal recente (>= since) do tenant, opcional por site.

        `limit` já vem saneado (int) da rota. Ordenado por sampled_at ASC para
        o frontend plotar direto; payload/label devolvidos como estão.
        """
        conditions = ["tenant_id = %s", "sampled_at >= %s"]
        params: list[Any] = [tenant_id, since]
        if site_id:
            conditions.append("site_id = %s")
            params.append(site_id)
        params.append(int(limit))
        query = (
            "SELECT site_id, label, sampled_at, payload "
            "FROM public.edge_telemetry_samples "
            "WHERE " + " AND ".join(conditions) + " "  # noqa: S608
            "ORDER BY sampled_at ASC "
            "LIMIT %s"
        )
        return self._execute(query, tuple(params))
