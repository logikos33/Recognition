"""Repository: Search Jobs (busca por conteúdo — migration 115).

public.search_jobs, mesmo padrão de PropagationRepository/TrainingRepository
(public.* com tenant_id, ADR-0016). `get_by_id_and_tenant` é o único ponto
de leitura usado pela API voltada ao usuário (cross-tenant → None → 404,
C-01); `get_by_id` (sem tenant) é INTERNAL USE ONLY, para o dispatch Celery
e o callback (já autenticado via callback_token) e o reconciler.
"""
import json
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class SearchRepository(BaseRepository):
    """Queries SQL para public.search_jobs."""

    # --- Create / Read ---

    def create_job(
        self,
        tenant_id: "UUID | str",
        selected_frame_ids: list[str],
        frames_hash: str,
        terms: list[dict[str, Any]],
        created_by: "UUID | str | None" = None,
    ) -> dict[str, Any]:
        """Cria o job já com a lista MATERIALIZADA (`selected_frame_ids`) e
        o `frames_hash` calculados pelo handler ANTES do INSERT — a tabela
        nunca guarda uma seleção "solta" sem a lista concreta que ela
        resolveu (mesmo desenho de `PropagationRepository.create_job`)."""
        return self._execute_mutation(
            """INSERT INTO search_jobs
               (tenant_id, selected_frame_ids, frames_hash, terms, created_by)
               VALUES (%s, %s::jsonb, %s, %s::jsonb, %s)
               RETURNING *""",
            (
                str(tenant_id),
                json.dumps(selected_frame_ids),
                frames_hash,
                json.dumps(terms),
                str(created_by) if created_by else None,
            ),
        )  # type: ignore[return-value]

    def get_by_id_and_tenant(
        self, job_id: "UUID | str", tenant_id: "UUID | str"
    ) -> Optional[dict[str, Any]]:
        """Busca job validando posse por tenant — cross-tenant → None
        (C-01, o handler HTTP converte em 404, nunca 403)."""
        return self._execute_one(
            "SELECT * FROM search_jobs WHERE id = %s AND tenant_id = %s",
            (str(job_id), str(tenant_id)),
        )

    def get_by_id(self, job_id: "UUID | str") -> Optional[dict[str, Any]]:
        """Busca job por id sem verificação de posse — INTERNAL USE ONLY
        (dispatch Celery, callback receiver já autenticado via
        callback_token, reconciler). Nunca usar direto num handler HTTP
        autenticado por JWT — use `get_by_id_and_tenant`."""
        return self._execute_one(
            "SELECT * FROM search_jobs WHERE id = %s", (str(job_id),),
        )

    def list_for_tenant(self, tenant_id: "UUID | str") -> list[dict[str, Any]]:
        return self._execute(
            "SELECT * FROM search_jobs WHERE tenant_id = %s ORDER BY created_at DESC",
            (str(tenant_id),),
        )

    # --- Status transitions (dispatch) ---

    def mark_running(self, job_id: "UUID | str") -> None:
        """`AND status != 'stopped'` — mesmo guard de `propagation_jobs`/
        `training_jobs`: nunca reverte um stop concorrente de volta pra
        'running'. Não há endpoint de stop nesta PR, mas a coluna/CHECK já
        suporta — este guard mantém o invariante intacto pra quando ele
        existir."""
        self._execute_mutation_no_return(
            "UPDATE search_jobs SET status = 'running', "
            "started_at = COALESCE(started_at, NOW()) "
            "WHERE id = %s AND status != 'stopped'",
            (str(job_id),),
        )

    def mark_failed(self, job_id: "UUID | str", reason: str) -> None:
        self._execute_mutation_no_return(
            "UPDATE search_jobs SET status = 'failed', error_reason = %s, "
            "finished_at = NOW() WHERE id = %s AND status != 'stopped'",
            (reason[:2000], str(job_id)),
        )

    def set_callback_token(self, job_id: "UUID | str", token: "str | None") -> None:
        self._execute_mutation_no_return(
            "UPDATE search_jobs SET callback_token = %s WHERE id = %s",
            (token, str(job_id)),
        )

    def revoke_callback_token(self, job_id: "UUID | str") -> None:
        """Alias legível pra `set_callback_token(job_id, None)` — mesmo
        efeito, usado no `finally` do dispatch (`tasks/search.py`) depois
        que `run_runpod_job` já terminou o pod (camada 2 de garantia de
        morte)."""
        self.set_callback_token(job_id, None)

    def set_gpu_instance_ref(self, job_id: "UUID | str", pod_id: str) -> None:
        self._execute_mutation_no_return(
            "UPDATE search_jobs SET gpu_instance_ref = %s WHERE id = %s",
            (pod_id, str(job_id)),
        )

    def merge_metrics(self, job_id: "UUID | str", metrics: dict[str, Any]) -> None:
        """Merge raso (`jsonb ||`) em `metrics` — nunca sobrescreve o dict
        inteiro. Usado tanto pelo progresso do callback ('running') quanto
        pelo `gpu_cost` que o runner devolve no fim (`run_runpod_job`,
        mesmo padrão de `metrics["gpu_cost"]` de `propagation_jobs`)."""
        self._execute_mutation_no_return(
            "UPDATE search_jobs SET metrics = metrics || %s::jsonb WHERE id = %s",
            (json.dumps(metrics), str(job_id)),
        )

    # --- Callback (GPU remota → backend) ---

    def apply_callback_completed(
        self, job_id: "UUID | str", findings_count: int,
        results: list[dict[str, Any]], metrics: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """`status != 'stopped'` no WHERE — mesmo guard de `mark_running`.
        Chamado SOMENTE depois que o handler já validou o payload de
        achados inteiro (nunca 'completed' antes do payload estar íntegro —
        "nunca sucesso silencioso")."""
        return self._execute_mutation(
            "UPDATE search_jobs SET status = 'completed', "
            "findings_count = %s, results = %s::jsonb, metrics = metrics || %s::jsonb, "
            "finished_at = NOW() "
            "WHERE id = %s AND status != 'stopped' RETURNING *",
            (findings_count, json.dumps(results), json.dumps(metrics), str(job_id)),
        )

    def apply_callback_failed(
        self, job_id: "UUID | str", reason: str
    ) -> Optional[dict[str, Any]]:
        return self._execute_mutation(
            "UPDATE search_jobs SET status = 'failed', error_reason = %s, "
            "finished_at = NOW() "
            "WHERE id = %s AND status != 'stopped' RETURNING *",
            (reason[:2000], str(job_id)),
        )
