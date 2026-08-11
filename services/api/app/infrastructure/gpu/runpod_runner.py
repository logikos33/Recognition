"""
Recognition — Runner genérico de job GPU no RunPod (substitui o fluxo
Vast.ai REST real de `tasks/training.py::_run_vast_remote_training` /
`_watch_vast_job`, generalizado pra qualquer tipo de carga).

O ciclo de vida (preço → teto de custo → criar pod → acompanhar → recolher
→ matar) é escrito UMA VEZ aqui e reusado por dois tipos de carga
(`JobKind`):
  - "train"     — executor `training/vast/remote_train.py` (implementado,
                   usado por `tasks/training.py::_run_runpod_train_job`).
  - "propagate" — chega em PR futuro; o ponto de injeção (executor_source +
                   env livres, callbacks de status/persistência via
                   parâmetro) já está pronto e testado com um executor dummy
                   (ver `tests/unit/infrastructure/test_runpod_runner.py`).

Pods RunPod NÃO têm auto-terminate nativo — a garantia de morte (nunca
vazar GPU paga) é NOSSA responsabilidade, em TRÊS CAMADAS independentes:

  1. NO POD (`build_onstart`): o executor roda sob `timeout $N` e um
     `trap ... EXIT` que SEMPRE tenta se autodestruir (DELETE /v1/pods/$id)
     antes de sair — sucesso, erro ou timeout, tanto faz.
  2. WATCHDOG CELERY (`run_runpod_job` + `_watch`): poll com deadline (a
     mesma generalização do antigo `_watch_vast_job`) — deadline estourado,
     3 polls "mortos" seguidos, ou status terminal no DB → SEMPRE
     `client.terminate_pod(pod_id)` no `finally`, mesmo se o watchdog
     levantar.
  3. RECONCILIADOR CELERY-BEAT (`tasks/gpu_reconciler.py`, ~5 min): varre
     TODOS os pods da conta e mata qualquer um (i) cujo job esteja em
     estado terminal no DB, (ii) mais velho que o deadline do job, ou
     (iii) sem nenhum job correspondente (gpu_instance_ref) no DB — estado
     100% em Postgres, sobrevive a restart da API/worker (camada 1 e 2
     dependem do processo estar vivo; a 3 não).

Custo: `run_runpod_job` consulta o preço da GPU (GraphQL) ANTES de criar o
pod, estima `preço/h × timeout/h` e recusa o disparo (`CostCapExceededError`,
job nunca criado) se exceder o teto do tipo de carga
(RUNPOD_MAX_USD_TRAIN/RUNPOD_MAX_USD_PROPAGATE, default $2.00 cada). Depois
do término, consulta billing best-effort e devolve custo estimado + real +
gpu_type + preço dentro de `metrics["gpu_cost"]` — o caller persiste esse
dict junto das métricas de treino (mesmo padrão de "grava tudo junto em
metrics jsonb" de `training_repository.py`).
"""
from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from app.infrastructure.gpu.runpod_client import RunPodClient, RunPodError

logger = logging.getLogger(__name__)


class JobKind(StrEnum):
    """Tipo de carga despachada pro runner genérico."""

    TRAIN = "train"
    PROPAGATE = "propagate"


class JobStoppedError(RuntimeError):
    """Job foi parado explicitamente (ex.: stop_job_handler) durante o
    dispatch/watch — distinto de falha genérica. O caller NUNCA deve
    reagendar (self.retry) nem sobrescrever o status 'stopped' já gravado."""


class CostCapExceededError(RuntimeError):
    """Custo estimado do job excede o teto configurado — pod NÃO foi criado."""


# --------------------------------------------------------------------- config

_DEFAULT_TIMEOUT_SECONDS: dict[JobKind, int] = {
    JobKind.TRAIN: 3600,
    JobKind.PROPAGATE: 3600,
}
_TIMEOUT_ENV_VARS: dict[JobKind, str] = {
    JobKind.TRAIN: "RUNPOD_TIMEOUT_SECONDS_TRAIN",
    JobKind.PROPAGATE: "RUNPOD_TIMEOUT_SECONDS_PROPAGATE",
}
_MAX_USD_ENV_VARS: dict[JobKind, str] = {
    JobKind.TRAIN: "RUNPOD_MAX_USD_TRAIN",
    JobKind.PROPAGATE: "RUNPOD_MAX_USD_PROPAGATE",
}
_DEFAULT_MAX_USD = 2.00
_DEFAULT_GPU_TYPE = "NVIDIA GeForce RTX 4090"
_DEFAULT_POLL_INTERVAL_SECONDS = 60
_DEFAULT_CONTAINER_DISK_GB = 40
_DEFAULT_IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    try:
        return int(raw) if raw else default
    except ValueError:
        logger.warning("runpod_env_int_invalido: %s=%r — usando default %d", name, raw, default)
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    try:
        return float(raw) if raw else default
    except ValueError:
        logger.warning("runpod_env_float_invalido: %s=%r — usando default %.2f", name, raw, default)
        return default


def timeout_seconds_for_kind(kind: JobKind | str) -> int:
    kind = JobKind(kind)
    return _env_int(_TIMEOUT_ENV_VARS[kind], _DEFAULT_TIMEOUT_SECONDS[kind])


def max_usd_for_kind(kind: JobKind | str) -> float:
    kind = JobKind(kind)
    return _env_float(_MAX_USD_ENV_VARS[kind], _DEFAULT_MAX_USD)


def gpu_type_default() -> str:
    return os.environ.get("RUNPOD_GPU_TYPE", _DEFAULT_GPU_TYPE)


def poll_interval_seconds() -> int:
    return _env_int("RUNPOD_POLL_INTERVAL_SECONDS", _DEFAULT_POLL_INTERVAL_SECONDS)


def estimate_cost_usd(price_usd_h: float, timeout_seconds: int) -> float:
    return round(price_usd_h * (timeout_seconds / 3600.0), 4)


def check_cost_cap(kind: JobKind | str, estimated_cost: float) -> None:
    """Levanta CostCapExceededError se `estimated_cost` exceder o teto do
    tipo de carga. Chamado ANTES de criar o pod — o job nunca chega a
    provisionar GPU se estourar o teto."""
    kind = JobKind(kind)
    cap = max_usd_for_kind(kind)
    if estimated_cost > cap:
        raise CostCapExceededError(
            f"Custo estimado (${estimated_cost:.2f}) para job kind={kind.value} "
            f"excede o teto {_MAX_USD_ENV_VARS[kind]}=${cap:.2f} — pod NÃO criado."
        )


# ------------------------------------------------------------------- onstart

def build_onstart(
    executor_source: str, timeout_seconds: int, executor_filename: str = "executor.py"
) -> str:
    """Onstart RunPod (camada 1 de 3 de garantia de morte, ver docstring do
    módulo): grava `executor_source` via heredoc, embrulha a execução com
    `timeout $timeout_seconds` e um `trap ... EXIT` que SEMPRE tenta
    `DELETE /v1/pods/$RUNPOD_POD_ID` antes de sair — sucesso, erro (mesmo
    sob `set -e`) ou timeout.

    Trade-off deliberado, documentado aqui: RUNPOD_API_KEY precisa estar no
    ambiente do próprio pod pro trap conseguir se autodestruir (a MESMA
    chave usada pra criar o pod — só permite gerenciar pods da conta
    RunPod, nunca dados do tenant/R2, que viajam via presigned URLs à
    parte). O pior cenário (a chave lida por um processo dentro de um pod
    que já está prestes a morrer, sob timeout ou trap) é aceito
    conscientemente: a alternativa (nenhuma chave no pod) removeria a
    camada 1 inteira e deixaria a garantia de morte só nas camadas 2
    (watchdog Celery) e 3 (reconciler celery-beat).

    `RUNPOD_POD_ID` é injetado automaticamente pela própria RunPod dentro
    do pod — nunca precisa ser exportado por nós.
    """
    marker = "RECOGNITION_RUNPOD_EXECUTOR_EOF"
    self_destruct = (
        'curl -fsS -X DELETE "https://rest.runpod.io/v1/pods/${RUNPOD_POD_ID}" '
        '-H "Authorization: Bearer ${RUNPOD_API_KEY}" >/dev/null 2>&1 || true'
    )
    return (
        "#!/bin/bash\n"
        "set -e\n"
        "cd /root\n"
        f"cat > /root/{executor_filename} <<'{marker}'\n"
        f"{executor_source}\n"
        f"{marker}\n"
        f"trap '{self_destruct}' EXIT\n"
        f"timeout {int(timeout_seconds)} python3 /root/{executor_filename}\n"
    )


# --------------------------------------------------------------------- watch

_DEAD_POD_STATUSES = frozenset({"EXITED", "TERMINATED", "DEAD", "FAILED"})


def _pod_looks_dead(pod: dict[str, Any]) -> bool:
    status = str(pod.get("desiredStatus") or pod.get("status") or "").strip().upper()
    return status in _DEAD_POD_STATUSES


def _watch(
    client: RunPodClient,
    pod_id: str,
    job_id: str,
    poll_status_fn: Callable[[], dict[str, Any]],
    verify_completed_fn: Callable[[dict[str, Any]], bool] | None,
    timeout_seconds: int,
    poll_interval: int,
) -> dict[str, Any]:
    """Watchdog: poll de `poll_status_fn` (fonte de verdade — o status real
    do job no DB, atualizado por fora via callback) + poll de saúde do pod
    até status terminal ou timeout.

    NOTA (mesmo desenho do antigo `_watch_vast_job`): o loop bloqueia o
    worker Celery com `time.sleep` — aceitável porque a fila é dedicada
    (1 job por vez) e o custo real está na GPU remota, não nesta CPU.
    """
    deadline = time.monotonic() + timeout_seconds
    dead_polls = 0

    while time.monotonic() < deadline:
        time.sleep(poll_interval)

        state = poll_status_fn() or {}
        status = state.get("status")
        if status == "completed":
            if verify_completed_fn is not None and not verify_completed_fn(state):
                raise RuntimeError(
                    f"Job {job_id} marcado completed mas a verificação pós-execução "
                    "falhou — watchdog recusa reportar sucesso sem confirmação real."
                )
            return {"status": "completed", "metrics": state.get("metrics") or {}}
        if status == "stopped":
            raise JobStoppedError(f"Job {job_id} foi parado durante o watchdog")
        if status == "failed":
            raise RuntimeError(f"Job runpod failed: job={job_id}")

        try:
            pod = client.get_pod(pod_id)
        except RunPodError as exc:
            logger.warning(
                "runpod_watchdog_poll_failed: job=%s pod=%s err=%s", job_id, pod_id, exc,
            )
            continue

        if _pod_looks_dead(pod):
            dead_polls += 1
            if dead_polls >= 3:
                raise RuntimeError(
                    f"Pod RunPod terminou sem callback final: job={job_id} pod={pod_id}"
                )
        else:
            dead_polls = 0

    raise RuntimeError(f"Timeout runpod após {timeout_seconds}s: job={job_id}")


def _best_effort_actual_cost(client: RunPodClient, pod_id: str) -> float | None:
    """Custo real pós-término via billing. Best-effort: nunca falha o job
    por causa de uma consulta de billing (retorna None em erro)."""
    try:
        records = client.get_billing(pod_id=pod_id)
    except RunPodError as exc:
        logger.warning("runpod_billing_lookup_failed: pod=%s err=%s", pod_id, exc)
        return None
    if not records:
        return None
    return round(sum(float(r.get("amount") or 0.0) for r in records), 4)


# ------------------------------------------------------------------ dispatch

def run_runpod_job(
    *,
    kind: JobKind | str,
    job_id: str,
    client: RunPodClient,
    executor_source: str,
    env: dict[str, str],
    poll_status_fn: Callable[[], dict[str, Any]],
    persist_instance_ref_fn: Callable[[str], None],
    verify_completed_fn: Callable[[dict[str, Any]], bool] | None = None,
    gpu_type: str | None = None,
    timeout_seconds: int | None = None,
    poll_interval: int | None = None,
    executor_filename: str = "executor.py",
    image: str = _DEFAULT_IMAGE,
) -> dict[str, Any]:
    """Ciclo de vida COMPLETO de um job GPU no RunPod, escrito uma única vez
    e reusado por qualquer `JobKind`: preço → teto de custo → onstart
    (camada 1 de morte) → create_pod → persistir gpu_instance_ref → watch
    (camada 2) → terminate SEMPRE (finally) → billing best-effort.

    `poll_status_fn`/`persist_instance_ref_fn`/`verify_completed_fn` são os
    pontos de injeção específicos de cada carga (train hoje; propagate no
    PR futuro reusa a mesma função com um `executor_source` e callbacks
    próprios — ver `tests/unit/infrastructure/test_runpod_runner.py` para
    o exercício com um executor dummy).

    Retorna `{"status": "completed", "metrics": {...+"gpu_cost": {...}},
    "pod_id": str}`. Levanta `CostCapExceededError` (teto estourado, ANTES
    de criar o pod), `JobStoppedError`, ou `RuntimeError`/`RunPodError`
    conforme o caso — SEMPRE termina o pod (finally) uma vez criado.
    """
    kind = JobKind(kind)
    gpu_type = gpu_type or gpu_type_default()
    timeout_seconds = timeout_seconds or timeout_seconds_for_kind(kind)
    poll_interval = poll_interval or poll_interval_seconds()

    price = client.get_gpu_price(gpu_type)
    estimated_cost = estimate_cost_usd(price, timeout_seconds)
    check_cost_cap(kind, estimated_cost)

    onstart = build_onstart(executor_source, timeout_seconds, executor_filename=executor_filename)
    pod_env = {
        **env,
        "RUNPOD_API_KEY": client.api_key,
        "RUNPOD_MAX_SECONDS": str(timeout_seconds),
    }
    pod = client.create_pod(
        name=f"recognition-{kind.value}-{job_id[:8]}",
        image=image,
        gpu_type_id=gpu_type,
        env=pod_env,
        docker_start_cmd=["/bin/bash", "-c", onstart],
        container_disk_gb=_DEFAULT_CONTAINER_DISK_GB,
    )
    pod_id = str(pod["id"])
    persist_instance_ref_fn(pod_id)
    logger.info(
        "runpod_job_dispatched: kind=%s job=%s pod=%s gpu=%s price_usd_h=%.4f "
        "estimated_usd=%.4f timeout=%ds",
        kind.value, job_id, pod_id, gpu_type, price, estimated_cost, timeout_seconds,
    )

    try:
        watch_result = _watch(
            client, pod_id, job_id, poll_status_fn, verify_completed_fn,
            timeout_seconds, poll_interval,
        )
    finally:
        # SEMPRE: nunca vazar GPU paga (camada 2 de garantia de morte).
        client.terminate_pod(pod_id)

    actual_cost = _best_effort_actual_cost(client, pod_id)
    metrics = dict(watch_result.get("metrics") or {})
    metrics["gpu_cost"] = {
        "provider": "runpod",
        "gpu_type": gpu_type,
        "price_usd_h": price,
        "estimated_usd": estimated_cost,
        "actual_usd": actual_cost,
    }
    return {"status": watch_result["status"], "metrics": metrics, "pod_id": pod_id}
