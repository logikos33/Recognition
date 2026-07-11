"""Repository: Model Drift Metrics (migration 101 — monitoramento de drift)."""
import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class DriftMetricsRepository(BaseRepository):
    """Queries SQL para tabela public.model_drift_metrics. Tenant-scoped (C-01).

    Alimentada pelo Celery beat compute_drift_metrics (janela diária por
    câmera×modelo). drift_score = |avg_conf - baseline| + L1(distribuição).
    """

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Registra métricas de drift de uma janela temporal."""
        return self._execute_mutation(
            "INSERT INTO model_drift_metrics "
            "(tenant_id, model_id, camera_id, window_start, window_end, "
            " detections_count, avg_confidence, class_distribution, drift_score) "
            "VALUES (%s, %s, %s, %s, %s, COALESCE(%s, 0), %s, %s::jsonb, %s) "
            "RETURNING *",
            (
                str(data["tenant_id"]),
                str(data["model_id"]) if data.get("model_id") else None,
                str(data["camera_id"]) if data.get("camera_id") else None,
                data.get("window_start"),
                data.get("window_end"),
                data.get("detections_count"),
                data.get("avg_confidence"),
                (
                    json.dumps(data["class_distribution"])
                    if data.get("class_distribution") is not None
                    else None
                ),
                data.get("drift_score"),
            ),
        )  # type: ignore[return-value]

    def list_by_model(
        self, model_id: UUID, tenant_id: str, limit: int = 30
    ) -> list[dict[str, Any]]:
        """Janelas de drift de um modelo, mais recentes primeiro (GET /drift)."""
        return self._execute(
            "SELECT * FROM model_drift_metrics "
            "WHERE model_id = %s AND tenant_id = %s "
            "ORDER BY window_start DESC NULLS LAST LIMIT %s",
            (str(model_id), str(tenant_id), limit),
        )

    def get_baseline(
        self, model_id: UUID, camera_id: UUID, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Primeira janela do par modelo×câmera (baseline do drift_score)."""
        return self._execute_one(
            "SELECT * FROM model_drift_metrics "
            "WHERE model_id = %s AND camera_id = %s AND tenant_id = %s "
            "ORDER BY window_start ASC NULLS LAST LIMIT 1",
            (str(model_id), str(camera_id), str(tenant_id)),
        )

    def get_latest_window(
        self, model_id: UUID, camera_id: UUID, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Janela mais recente do par modelo×câmera (dedupe do beat diário)."""
        return self._execute_one(
            "SELECT * FROM model_drift_metrics "
            "WHERE model_id = %s AND camera_id = %s AND tenant_id = %s "
            "ORDER BY window_start DESC NULLS LAST LIMIT 1",
            (str(model_id), str(camera_id), str(tenant_id)),
        )

    def exists_for_window(
        self,
        model_id: UUID,
        camera_id: UUID,
        tenant_id: str,
        window_start: datetime,
    ) -> bool:
        """True se já há métricas para a janela (idempotência do beat)."""
        row = self._execute_one(
            "SELECT 1 AS found FROM model_drift_metrics "
            "WHERE model_id = %s AND camera_id = %s AND tenant_id = %s "
            "AND window_start = %s LIMIT 1",
            (str(model_id), str(camera_id), str(tenant_id), window_start),
        )
        return row is not None
