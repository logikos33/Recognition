"""
Recognition — Reconciliador de pods RunPod órfãos (camada 3 de 3 de garantia
de morte, ver `infrastructure/gpu/runpod_runner.py`).

Celery-beat, ~5 min (`SAFE_BEAT_SCHEDULE` em `celery_app.py`). Estado 100%
do Postgres — sobrevive a restart da API/worker, diferente das camadas 1
(trap dentro do pod) e 2 (watchdog Celery, que depende do processo que
despachou o job continuar vivo até o fim).

Varre TODOS os pods da conta RunPod (`RunPodClient.list_pods`) cujo nome
começa com o prefixo usado por `runpod_runner.run_runpod_job`
("recognition-") e termina qualquer um que seja:
  (i)   de um job em estado TERMINAL no DB (completed/failed/stopped) —
        deveria ter sido terminado no fim do watch, mas o processo pode ter
        morrido antes do `finally` rodar;
  (ii)  mais velho que o deadline do tipo de carga (started_at + timeout) —
        watchdog perdido/travado (worker reiniciado no meio do poll);
  (iii) sem NENHUM job correspondente no DB (`gpu_instance_ref`) — pod
        órfão de verdade (ex.: criado manualmente fora do fluxo, ou job
        deletado).

Pods de outra origem na mesma conta (nome sem o prefixo "recognition-")
NUNCA são tocados — o reconciler só gerencia o que ele mesmo cria.

LIMITAÇÃO CONHECIDA: usa só a chave de PLATAFORMA (env RUNPOD_API_KEY) —
`resolve_runpod_api_key(None)`. Se/quando uma chave RunPod POR TENANT for
configurada via integration store (hoje só um ponto de extensão pronto, sem
UI — ver `runpod_client.resolve_runpod_api_key`), os pods dessa conta
separada não são visíveis por este reconciler; extensão futura precisaria
varrer uma conta por tenant com chave própria.

Reconcilia as DUAS cargas RunPod (`_load_runpod_jobs` faz a união):
'train' (`training_jobs`, filtrado por `gpu_provider = 'runpod'`) e
'propagate' (`propagation_jobs`, migration 112 — RunPod é o único
provider dessa carga, sem coluna `gpu_provider` própria). Cada job
carregado ganha `_kind`/`_table` pra `_is_expired` (deadline por tipo de
carga) e `_mark_job_failed` (UPDATE na tabela certa) saberem tratar as
duas igual sem duplicar a lógica de decisão de terminação.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.gpu.runpod_client import (
    RunPodClient,
    RunPodError,
    resolve_runpod_api_key,
)
from app.infrastructure.gpu.runpod_runner import JobKind, timeout_seconds_for_kind
from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = frozenset({"completed", "failed", "stopped"})
_POD_NAME_PREFIX = "recognition-"


def _load_runpod_jobs(pool: Any) -> dict[str, dict[str, Any]]:
    """União de `training_jobs` (gpu_provider='runpod') e
    `propagation_jobs` (migration 112 — RunPod é o único provider da carga
    'propagate', sem coluna gpu_provider própria) com gpu_instance_ref
    setado, indexado por pod_id. Cada linha ganha `_kind` (JobKind.TRAIN /
    JobKind.PROPAGATE) e `_table` — usados por `_is_expired` (deadline por
    tipo de carga) e `_mark_job_failed` (UPDATE na tabela certa)."""
    from app.infrastructure.database.repositories.propagation_repository import (  # noqa: PLC0415,E501
        PropagationRepository,
    )
    from app.infrastructure.database.repositories.training_repository import (  # noqa: PLC0415
        TrainingRepository,
    )

    training_rows = TrainingRepository(pool)._execute(
        """SELECT id, status, started_at, gpu_instance_ref, tenant_id
           FROM training_jobs
           WHERE gpu_provider = 'runpod' AND gpu_instance_ref IS NOT NULL"""
    )
    propagation_rows = PropagationRepository(pool)._execute(
        """SELECT id, status, started_at, gpu_instance_ref, tenant_id
           FROM propagation_jobs
           WHERE gpu_instance_ref IS NOT NULL"""
    )

    jobs_by_pod: dict[str, dict[str, Any]] = {}
    for row in training_rows:
        jobs_by_pod[str(row["gpu_instance_ref"])] = {
            **row, "_kind": JobKind.TRAIN, "_table": "training_jobs",
        }
    for row in propagation_rows:
        jobs_by_pod[str(row["gpu_instance_ref"])] = {
            **row, "_kind": JobKind.PROPAGATE, "_table": "propagation_jobs",
        }
    return jobs_by_pod


def _is_expired(job: dict[str, Any], now: datetime) -> bool:
    started_at = job.get("started_at")
    if started_at is None:
        return False
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    deadline_seconds = timeout_seconds_for_kind(job.get("_kind", JobKind.TRAIN))
    return now > started_at + timedelta(seconds=deadline_seconds)


def _mark_job_failed(pool: Any, job_id: Any, reason: str, table: str = "training_jobs") -> None:
    """Marca o job como 'failed' na tabela certa (`training_jobs` ou
    `propagation_jobs`, migration 112) — `table` vem de `job["_table"]`
    (`_load_runpod_jobs`), default `training_jobs` preserva o
    comportamento/assinatura anteriores (compatível com os testes
    existentes que chamam sem esse argumento)."""
    from app.infrastructure.database.repositories.propagation_repository import (  # noqa: PLC0415,E501
        PropagationRepository,
    )
    from app.infrastructure.database.repositories.training_repository import (  # noqa: PLC0415
        TrainingRepository,
    )

    message = f"Reconciler RunPod: {reason}"[:500]
    try:
        if table == "propagation_jobs":
            PropagationRepository(pool).mark_failed(job_id, message)
        else:
            TrainingRepository(pool).update_job_status(
                job_id, "failed", error_message=message,
            )
    except Exception as exc:  # noqa: BLE001 — reconciler nunca quebra por isso
        logger.warning("runpod_reconciler_mark_failed_error: job=%s err=%s", job_id, exc)


def reconcile_runpod_pods_impl(client: RunPodClient, pool: Any) -> dict[str, list[str]]:
    """Lógica pura (testável sem Celery real). Retorna
    `{"terminated": [pod_id, ...], "kept": [pod_id, ...]}`."""
    jobs_by_pod = _load_runpod_jobs(pool)
    now = datetime.now(timezone.utc)

    terminated: list[str] = []
    kept: list[str] = []

    for pod in client.list_pods():
        pod_id = str(pod.get("id") or "")
        if not pod_id:
            continue
        name = str(pod.get("name") or "")
        if not name.startswith(_POD_NAME_PREFIX):
            # Não é um pod do Recognition — nunca mexer em pods de outra
            # origem na mesma conta RunPod.
            kept.append(pod_id)
            continue

        job = jobs_by_pod.get(pod_id)
        reason: str | None = None
        if job is None:
            reason = "sem job correspondente no DB (órfão)"
        elif job.get("status") in _TERMINAL_STATUSES:
            reason = f"job em estado terminal ({job.get('status')})"
        elif _is_expired(job, now):
            reason = "job mais velho que o deadline do tipo de carga"

        if reason is None:
            kept.append(pod_id)
            continue

        logger.warning("runpod_reconciler_terminating: pod=%s reason=%s", pod_id, reason)
        client.terminate_pod(pod_id)
        terminated.append(pod_id)

        if job is not None and job.get("status") not in _TERMINAL_STATUSES:
            _mark_job_failed(pool, job["id"], reason, job.get("_table", "training_jobs"))

    return {"terminated": terminated, "kept": kept}


@celery.task(
    bind=True, max_retries=0, queue="training",
    name="tasks.gpu_reconciler.reconcile_runpod_pods",
)
def reconcile_runpod_pods(self) -> dict[str, list[str]]:  # noqa: ARG001
    """Task celery-beat — camada 3 de garantia de morte. Best-effort: erro
    de rede/config nunca derruba o beat (loga e retorna vazio)."""
    pool = DatabasePool.get_instance()
    if pool is None:
        logger.warning("runpod_reconciler_skip: pool indisponível")
        return {"terminated": [], "kept": []}

    api_key = resolve_runpod_api_key(None)
    if not api_key:
        logger.info("runpod_reconciler_skip: RUNPOD_API_KEY não configurada")
        return {"terminated": [], "kept": []}

    try:
        client = RunPodClient(api_key)
        return reconcile_runpod_pods_impl(client, pool)
    except RunPodError as exc:
        logger.error("runpod_reconciler_failed: err=%s", exc)
        return {"terminated": [], "kept": []}
