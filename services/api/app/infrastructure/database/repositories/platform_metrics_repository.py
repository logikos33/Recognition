"""Repository: PlatformMetrics — série temporal genérica de observability.

Tabela public.platform_metrics (migration 088): scope/metric/value/labels,
tenant_id nullable (NULL = métrica global de plataforma). Append-only;
retenção em runtime via prune_older_than() (nunca via migration).
"""
import json
from datetime import datetime
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class PlatformMetricsRepository(BaseRepository):
    """SQL para public.platform_metrics."""

    def insert_points(self, points: list[dict[str, Any]]) -> int:
        """INSERT batch de pontos.

        Cada point: {"scope": str, "metric": str, "value": num,
                     "labels": dict opcional, "tenant_id": str opcional}.
        Retorna o total de linhas inseridas.
        """
        if not points:
            return 0
        params = [
            (
                p.get("tenant_id"),
                p["scope"],
                p["metric"],
                p["value"],
                json.dumps(p.get("labels") or {}),
            )
            for p in points
        ]
        return self._execute_many(
            "INSERT INTO public.platform_metrics "
            "(tenant_id, scope, metric, value, labels) "
            "VALUES (%s, %s, %s, %s, %s::jsonb)",
            params,
        )

    def timeseries(
        self,
        scope: str,
        metric: str,
        since: datetime,
        bucket_seconds: int,
        tenant_id: str | None = None,
        label_queue: str | None = None,
    ) -> list[dict[str, Any]]:
        """Série bucketizada (AVG/MAX por bucket) de uma métrica.

        bucket_seconds DEVE vir de whitelist na rota (nunca input livre);
        todos os valores entram via %s (zero interpolação de input).
        """
        conditions = ["scope = %s", "metric = %s", "recorded_at >= %s"]
        params: list[Any] = [bucket_seconds, bucket_seconds, scope, metric, since]
        if tenant_id:
            conditions.append("tenant_id = %s")
            params.append(tenant_id)
        if label_queue:
            conditions.append("labels->>'queue' = %s")
            params.append(label_queue)
        # Condições são constantes internas — nenhuma recebe input interpolado.
        query = (
            "SELECT to_timestamp(floor(extract(epoch FROM recorded_at) / %s) * %s) "
            "       AS bucket, "
            "       AVG(value) AS avg_value, "
            "       MAX(value) AS max_value, "
            "       COUNT(*)   AS samples "
            "FROM public.platform_metrics "
            "WHERE " + " AND ".join(conditions) + " "  # noqa: S608
            "GROUP BY bucket ORDER BY bucket"
        )
        return self._execute(query, tuple(params))

    def last_recorded_at(self) -> dict[str, Any] | None:
        """Timestamp do último ponto coletado ('coletado há Xs' no dashboard)."""
        return self._execute_one(
            "SELECT MAX(recorded_at) AS last_recorded_at FROM public.platform_metrics"
        )

    def prune_older_than(self, days: int) -> int:
        """Retenção em runtime: apaga pontos mais antigos que N dias.

        Chamado 1x/dia pelo coletor (lock Redis) — precedente
        tasks/retention_expiry.py. Retorna linhas removidas.
        """
        return self._execute_mutation_no_return(
            "DELETE FROM public.platform_metrics "
            "WHERE recorded_at < now() - (%s * interval '1 day')",
            (int(days),),
        )
