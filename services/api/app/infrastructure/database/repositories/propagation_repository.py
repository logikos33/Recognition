"""Repository: Propagation Jobs (propagação semeada — migration 112).

public.propagation_jobs, mesmo padrão de TrainingRepository (public.* com
tenant_id, ADR-0016). `get_by_id_and_tenant` é o único ponto de leitura
usado pela API voltada ao usuário (cross-tenant → None → 404, C-01);
`get_by_id` (sem tenant) é INTERNAL USE ONLY, para o dispatch Celery e o
reconciler, que já resolvem o tenant a partir da própria linha.
"""
import json
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class PropagationRepository(BaseRepository):
    """Queries SQL para public.propagation_jobs."""

    # --- Create / Read ---

    def create_job(
        self,
        tenant_id: "UUID | str",
        pool_criteria: dict[str, Any],
        pool_frame_ids: list[str],
        pool_hash: str,
        seed_frame_ids: list[str],
        created_by: "UUID | str | None" = None,
    ) -> dict[str, Any]:
        """Cria o job já com a lista MATERIALIZADA (`pool_frame_ids`) e o
        `pool_hash` calculados pelo guard (`domain/services/
        propagation_pool.py`) ANTES do INSERT — a tabela nunca guarda um
        critério "solto" sem a lista concreta que ele resolveu."""
        return self._execute_mutation(
            """INSERT INTO propagation_jobs
               (tenant_id, pool_criteria, pool_frame_ids, pool_hash,
                seed_frame_ids, seed_count, created_by)
               VALUES (%s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s, %s)
               RETURNING *""",
            (
                str(tenant_id),
                json.dumps(pool_criteria),
                json.dumps(pool_frame_ids),
                pool_hash,
                json.dumps(seed_frame_ids),
                len(seed_frame_ids),
                str(created_by) if created_by else None,
            ),
        )  # type: ignore[return-value]

    def get_by_id_and_tenant(
        self, job_id: "UUID | str", tenant_id: "UUID | str"
    ) -> Optional[dict[str, Any]]:
        """Busca job validando posse por tenant — cross-tenant → None
        (C-01, o handler HTTP converte em 404, nunca 403)."""
        return self._execute_one(
            "SELECT * FROM propagation_jobs WHERE id = %s AND tenant_id = %s",
            (str(job_id), str(tenant_id)),
        )

    def get_by_id(self, job_id: "UUID | str") -> Optional[dict[str, Any]]:
        """Busca job por id sem verificação de posse — INTERNAL USE ONLY
        (dispatch Celery, callback receiver já autenticado via
        callback_token, reconciler). Nunca usar direto num handler HTTP
        autenticado por JWT — use `get_by_id_and_tenant`."""
        return self._execute_one(
            "SELECT * FROM propagation_jobs WHERE id = %s", (str(job_id),),
        )

    def list_for_tenant(self, tenant_id: "UUID | str") -> list[dict[str, Any]]:
        return self._execute(
            "SELECT * FROM propagation_jobs WHERE tenant_id = %s "
            "ORDER BY created_at DESC",
            (str(tenant_id),),
        )

    # --- Status transitions (dispatch) ---

    def mark_running(self, job_id: "UUID | str") -> None:
        """`AND status != 'stopped'` — mesmo guard de `training_jobs`
        (tasks/training.py::update_job): nunca reverte um stop concorrente
        de volta pra 'running'. Não há endpoint de stop nesta PR, mas a
        coluna/CHECK já suporta — este guard mantém o invariante intacto
        pra quando ele existir."""
        self._execute_mutation_no_return(
            "UPDATE propagation_jobs SET status = 'running', "
            "started_at = COALESCE(started_at, NOW()) "
            "WHERE id = %s AND status != 'stopped'",
            (str(job_id),),
        )

    def mark_failed(self, job_id: "UUID | str", reason: str) -> None:
        self._execute_mutation_no_return(
            "UPDATE propagation_jobs SET status = 'failed', error_reason = %s, "
            "finished_at = NOW() WHERE id = %s AND status != 'stopped'",
            (reason[:2000], str(job_id)),
        )

    def set_callback_token(self, job_id: "UUID | str", token: "str | None") -> None:
        self._execute_mutation_no_return(
            "UPDATE propagation_jobs SET callback_token = %s WHERE id = %s",
            (token, str(job_id)),
        )

    def set_gpu_instance_ref(self, job_id: "UUID | str", pod_id: str) -> None:
        self._execute_mutation_no_return(
            "UPDATE propagation_jobs SET gpu_instance_ref = %s WHERE id = %s",
            (pod_id, str(job_id)),
        )

    def merge_metrics(self, job_id: "UUID | str", metrics: dict[str, Any]) -> None:
        """Merge raso (`jsonb ||`) em `metrics` — nunca sobrescreve o dict
        inteiro. Usado tanto pelo progresso do callback ('running') quanto
        pelo `gpu_cost` que o runner devolve no fim (`run_runpod_job`,
        mesmo padrão de `metrics["gpu_cost"]` de `training_jobs`)."""
        self._execute_mutation_no_return(
            "UPDATE propagation_jobs SET metrics = metrics || %s::jsonb WHERE id = %s",
            (json.dumps(metrics), str(job_id)),
        )

    # --- Callback (GPU remota → backend) ---

    def apply_callback_completed(
        self, job_id: "UUID | str", proposals_count: int, metrics: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """`status != 'stopped'` no WHERE — mesmo guard de `mark_running`.
        Chamado SOMENTE depois que o handler já validou e persistiu as
        propostas em `training_frames.pre_annotations` (nunca 'completed'
        antes do payload estar íntegro — "nunca sucesso silencioso")."""
        return self._execute_mutation(
            "UPDATE propagation_jobs SET status = 'completed', "
            "proposals_count = %s, metrics = metrics || %s::jsonb, "
            "finished_at = NOW() "
            "WHERE id = %s AND status != 'stopped' RETURNING *",
            (proposals_count, json.dumps(metrics), str(job_id)),
        )

    def apply_callback_failed(
        self, job_id: "UUID | str", reason: str
    ) -> Optional[dict[str, Any]]:
        return self._execute_mutation(
            "UPDATE propagation_jobs SET status = 'failed', error_reason = %s, "
            "finished_at = NOW() "
            "WHERE id = %s AND status != 'stopped' RETURNING *",
            (reason[:2000], str(job_id)),
        )
