"""Repository: Model Evaluations (migration 101 — campeão×desafiante)."""
import json
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class ModelEvaluationRepository(BaseRepository):
    """Queries SQL para tabela public.model_evaluations. Tenant-scoped (C-01)."""

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Registra avaliação (verdict default 'pending')."""
        return self._execute_mutation(
            "INSERT INTO model_evaluations "
            "(tenant_id, model_id, champion_model_id, dataset_version_id, "
            " metrics, confusion_matrix, verdict) "
            "VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, "
            "        COALESCE(%s, 'pending')) RETURNING *",
            (
                str(data["tenant_id"]),
                str(data["model_id"]) if data.get("model_id") else None,
                str(data["champion_model_id"]) if data.get("champion_model_id") else None,
                str(data["dataset_version_id"]) if data.get("dataset_version_id") else None,
                json.dumps(data.get("metrics", {})),
                (
                    json.dumps(data["confusion_matrix"])
                    if data.get("confusion_matrix") is not None
                    else None
                ),
                str(data["verdict"]) if data.get("verdict") else None,
            ),
        )  # type: ignore[return-value]

    def get_by_id(self, evaluation_id: UUID, tenant_id: str) -> Optional[dict[str, Any]]:
        """Busca avaliação por ID validando posse do tenant."""
        return self._execute_one(
            "SELECT * FROM model_evaluations WHERE id = %s AND tenant_id = %s",
            (str(evaluation_id), str(tenant_id)),
        )

    def get_latest_for_model(
        self, model_id: UUID, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Última avaliação de um modelo (gate do activate + GET /eval)."""
        return self._execute_one(
            "SELECT * FROM model_evaluations "
            "WHERE model_id = %s AND tenant_id = %s "
            "ORDER BY created_at DESC LIMIT 1",
            (str(model_id), str(tenant_id)),
        )

    def list_by_model(self, model_id: UUID, tenant_id: str) -> list[dict[str, Any]]:
        """Histórico de avaliações de um modelo."""
        return self._execute(
            "SELECT * FROM model_evaluations "
            "WHERE model_id = %s AND tenant_id = %s ORDER BY created_at DESC",
            (str(model_id), str(tenant_id)),
        )

    def update_verdict(
        self,
        evaluation_id: UUID,
        tenant_id: str,
        verdict: str,
        metrics: Optional[dict[str, Any]] = None,
        confusion_matrix: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """Atualiza verdict (pending→promote|reject) e métricas do resultado."""
        fields = ["verdict = %s"]
        values: list[Any] = [str(verdict)]
        if metrics is not None:
            fields.append("metrics = %s::jsonb")
            values.append(json.dumps(metrics))
        if confusion_matrix is not None:
            fields.append("confusion_matrix = %s::jsonb")
            values.append(json.dumps(confusion_matrix))
        values.extend([str(evaluation_id), str(tenant_id)])
        return self._execute_mutation(
            f"UPDATE model_evaluations SET {', '.join(fields)} "  # noqa: S608
            "WHERE id = %s AND tenant_id = %s RETURNING *",
            tuple(values),
        )
