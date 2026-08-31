"""
Service: Dashboard Integrado — observabilidade de modelos + telemetria edge.

task-112 / ADR-0053. Orquestra ingest e leitura das duas séries persistidas
(public.model_training_metrics e public.edge_telemetry_samples), sempre
tenant-scoped (C-01 — o tenant_id vem do JWT na rota, nunca do body).

Ingest de telemetria ALÉM de persistir publica cada amostra no Redis canal
`edge_telemetry:{tenant_id}` para o bridge Redis→SocketIO empurrar ao vivo pro
namespace /monitor (mesmo padrão best-effort dos publishers de quality/routes).
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from app.infrastructure.database.repositories.edge_telemetry_repository import (
    EdgeTelemetryRepository,
)
from app.infrastructure.database.repositories.model_training_metrics_repository import (
    ModelTrainingMetricsRepository,
)

logger = logging.getLogger(__name__)

# Whitelist janela → segundos (nunca input livre — precedente
# observability_service.WINDOW_BUCKETS).
WINDOW_SECONDS: dict[str, int] = {
    "15m": 900,
    "1h": 3_600,
    "6h": 21_600,
    "24h": 86_400,
}
DEFAULT_WINDOW = "1h"


class DashboardEdgeService:
    """Ingest + leitura das séries de observabilidade do dashboard integrado."""

    def __init__(
        self,
        training_repo: ModelTrainingMetricsRepository,
        telemetry_repo: EdgeTelemetryRepository,
    ) -> None:
        self._training = training_repo
        self._telemetry = telemetry_repo

    # ------------------------------------------------------------------ #
    # Ingest                                                             #
    # ------------------------------------------------------------------ #

    def ingest_training_metrics(
        self,
        tenant_id: str,
        model_name: str,
        framework: str | None,
        epochs: list[dict[str, Any]],
    ) -> int:
        """Upsert das épocas de um modelo. Retorna linhas afetadas."""
        affected = self._training.upsert_epochs(
            tenant_id, model_name, framework, epochs
        )
        logger.info(
            "dashboard_training_ingest: tenant=%s model=%s epochs=%d",
            tenant_id, model_name, len(epochs),
        )
        return affected

    def ingest_edge_telemetry(
        self,
        tenant_id: str,
        site_id: str | None,
        samples: list[dict[str, Any]],
    ) -> int:
        """Persiste as amostras e publica cada uma no Redis (ao vivo).

        A publicação é best-effort: falha de Redis nunca derruba o ingest
        (a amostra já está persistida e servida pelo endpoint de read).
        """
        inserted = self._telemetry.insert_samples(tenant_id, site_id, samples)
        self._publish_live(tenant_id, site_id, samples)
        logger.info(
            "dashboard_telemetry_ingest: tenant=%s site=%s samples=%d",
            tenant_id, site_id, len(samples),
        )
        return inserted

    def _publish_live(
        self,
        tenant_id: str,
        site_id: str | None,
        samples: list[dict[str, Any]],
    ) -> None:
        """Publica amostras no canal edge_telemetry:{tenant_id} (best-effort)."""
        if not samples:
            return
        try:
            import redis as _redis  # noqa: PLC0415

            redis_url = os.environ.get("REDIS_URL", "")
            if not redis_url:
                return
            r = _redis.from_url(redis_url, decode_responses=True, socket_timeout=3)
            channel = f"edge_telemetry:{tenant_id}"
            for s in samples:
                r.publish(
                    channel,
                    json.dumps(
                        {
                            "tenant_id": tenant_id,
                            "site_id": site_id,
                            "label": s.get("label"),
                            "sampled_at": s.get("sampled_at"),
                            "payload": s.get("payload") or {},
                        }
                    ),
                )
            r.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "dashboard_telemetry_publish_error: tenant=%s err=%s",
                tenant_id, exc,
            )

    # ------------------------------------------------------------------ #
    # Read                                                               #
    # ------------------------------------------------------------------ #

    def get_training_curves(
        self, tenant_id: str, models: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        """Curvas por época agrupadas por modelo (para comparação lado a lado)."""
        rows = self._training.curves(tenant_id, models)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["model_name"], []).append(
                {
                    "epoch": row["epoch"],
                    "framework": row.get("framework"),
                    "metrics": row.get("metrics") or {},
                }
            )
        return grouped

    def get_models_summary(self, tenant_id: str) -> list[dict[str, Any]]:
        """Lista de modelos disponíveis + resumo (última época, ap5095, ap_small)."""
        rows = self._training.models_summary(tenant_id)
        summary = []
        for row in rows:
            summary.append(
                {
                    "model_name": row["model_name"],
                    # display_name (task D3): alias voltado ao cliente — NULL
                    # quando ninguém atribuiu ainda / não há trained_models
                    # correspondente; o caller decide o fallback ("Logikos"),
                    # nunca `model_name` cru.
                    "display_name": row.get("display_name"),
                    "framework": row.get("framework"),
                    "last_epoch": row.get("last_epoch"),
                    "epoch_count": int(row.get("epoch_count") or 0),
                    "ap5095": _to_float(row.get("ap5095")),
                    "ap_small": _to_float(row.get("ap_small")),
                }
            )
        return summary

    def get_edge_timeseries(
        self, tenant_id: str, site_id: str | None, window: str
    ) -> dict[str, Any]:
        """Série temporal recente de telemetria do edge (janela na whitelist)."""
        window_seconds = WINDOW_SECONDS[window]
        since = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        rows = self._telemetry.timeseries(tenant_id, since, site_id)
        samples = [
            {
                "site_id": str(row["site_id"]) if row.get("site_id") else None,
                "label": row.get("label"),
                "sampled_at": str(row["sampled_at"]),
                "payload": row.get("payload") or {},
            }
            for row in rows
        ]
        return {"window": window, "samples": samples, "count": len(samples)}


def _to_float(value: Any) -> float | None:
    """Converte string/num → float; None/erro → None (JSONB->>'k' vem string)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
