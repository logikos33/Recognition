"""Repository: model_training_metrics — curvas de treino por época por modelo.

Tabela public.model_training_metrics (migration 105): série de métricas de
treino (mAP@0.5:0.95, mAP_small/medium/large, losses, LR) por época por modelo,
escopada por tenant (C-01 — coluna tenant_id filtra tudo; cross-tenant nunca
aparece). Alimenta a seção "Observabilidade de Modelos" do dashboard (task-112).

Padrão-casa: BaseRepository (psycopg2/RealDictCursor), zero f-string com input,
todo valor via %s. Upsert por (tenant_id, model_name, epoch) — reingestão da
mesma época atualiza a curva, nunca duplica.
"""
import json
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class ModelTrainingMetricsRepository(BaseRepository):
    """SQL para public.model_training_metrics (tenant-scoped)."""

    def upsert_epochs(
        self,
        tenant_id: str,
        model_name: str,
        framework: str | None,
        epochs: list[dict[str, Any]],
    ) -> int:
        """Upsert batch de épocas de um modelo.

        Cada item de `epochs`: {"epoch": int, "metrics": dict}. Retorna o total
        de linhas afetadas. ON CONFLICT (tenant_id, model_name, epoch) atualiza
        metrics/framework — reingestão idempotente.
        """
        if not epochs:
            return 0
        params = [
            (
                tenant_id,
                model_name,
                framework,
                int(e["epoch"]),
                json.dumps(e.get("metrics") or {}),
            )
            for e in epochs
        ]
        return self._execute_many(
            "INSERT INTO public.model_training_metrics "
            "(tenant_id, model_name, framework, epoch, metrics) "
            "VALUES (%s, %s, %s, %s, %s::jsonb) "
            "ON CONFLICT (tenant_id, model_name, epoch) DO UPDATE SET "
            "  metrics = EXCLUDED.metrics, "
            "  framework = COALESCE(EXCLUDED.framework, "
            "                       public.model_training_metrics.framework)",
            params,
        )

    def curves(
        self, tenant_id: str, models: list[str]
    ) -> list[dict[str, Any]]:
        """Curvas (todas as épocas) dos modelos pedidos, do tenant.

        `models` vazio → todos os modelos do tenant. Ordenado por modelo e
        época para o frontend montar as linhas direto.
        """
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if models:
            placeholders = ", ".join(["%s"] * len(models))
            conditions.append(f"model_name IN ({placeholders})")  # noqa: S608
            params.extend(models)
        query = (
            "SELECT model_name, framework, epoch, metrics "
            "FROM public.model_training_metrics "
            "WHERE " + " AND ".join(conditions) + " "  # noqa: S608
            "ORDER BY model_name, epoch"
        )
        return self._execute(query, tuple(params))

    def models_summary(self, tenant_id: str) -> list[dict[str, Any]]:
        """Lista de modelos do tenant + resumo da última época.

        Resumo = ap5095/ap_small da maior época (DISTINCT ON) + total de épocas.
        Alimenta o dropdown multi-seleção e os cards de comparação.
        """
        query = (
            "SELECT DISTINCT ON (model_name) "
            "  model_name, framework, epoch AS last_epoch, "
            "  metrics->>'ap5095'   AS ap5095, "
            "  metrics->>'ap_small' AS ap_small, "
            "  (SELECT COUNT(*) FROM public.model_training_metrics m2 "
            "     WHERE m2.tenant_id = m.tenant_id "
            "       AND m2.model_name = m.model_name) AS epoch_count "
            "FROM public.model_training_metrics m "
            "WHERE tenant_id = %s "
            "ORDER BY model_name, epoch DESC"
        )
        return self._execute(query, (tenant_id,))
