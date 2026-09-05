"""
Recognition — Runner genérico de job GPU no RunPod (substitui o fluxo
Vast.ai REST real de `tasks/training.py::_run_vast_remote_training` /
`_watch_vast_job`, generalizado pra qualquer tipo de carga).

O ciclo de vida (preço → teto de custo → criar pod → acompanhar → recolher
→ matar) é escrito UMA VEZ aqui e reusado por TRÊS tipos de carga
(`JobKind`):
  - "train"     — executor `training/vast/remote_train.py`, usado por
                   `tasks/training.py::_run_runpod_train_job`.
  - "propagate" — executor `training/propagate_seeded.py`, usado por
                   `tasks/propagation.py::dispatch_propagation`.
  - "search"    — busca por conteúdo (open-vocabulary, OWLv2), executor
                   `training/search_content.py`, usado por
                   `tasks/search.py::dispatch_search`. O ponto de injeção
                   (executor_source + env livres, callbacks de
                   status/persistência via parâmetro) é o mesmo dos dois
                   anteriores — testado com um executor dummy (ver
                   `tests/unit/infrastructure/test_runpod_runner.py`).

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
    SEARCH = "search"


class JobStoppedError(RuntimeError):
    """Job foi parado explicitamente (ex.: stop_job_handler) durante o
    dispatch/watch — distinto de falha genérica. O caller NUNCA deve
    reagendar (self.retry) nem sobrescrever o status 'stopped' já gravado."""


class CostCapExceededError(RuntimeError):
    """Custo estimado do job excede o teto configurado — pod NÃO foi criado."""


class SaldoInsuficienteError(RuntimeError):
    """A conta não tem saldo para terminar o job — pod NÃO foi criado.

    Distinto de `CostCapExceededError`: o teto é uma decisão nossa sobre quanto
    QUEREMOS gastar; o saldo é um fato sobre quanto PODEMOS. Um job dentro do
    teto e fora do saldo começa, roda, e morre na metade levando junto tudo o
    que já foi pago."""


# --------------------------------------------------------------------- config

_DEFAULT_TIMEOUT_SECONDS: dict[JobKind, int] = {
    JobKind.TRAIN: 3600,
    JobKind.PROPAGATE: 3600,
    JobKind.SEARCH: 1800,
}
_TIMEOUT_ENV_VARS: dict[JobKind, str] = {
    JobKind.TRAIN: "RUNPOD_TIMEOUT_SECONDS_TRAIN",
    JobKind.PROPAGATE: "RUNPOD_TIMEOUT_SECONDS_PROPAGATE",
    JobKind.SEARCH: "RUNPOD_TIMEOUT_SECONDS_SEARCH",
}
_MAX_USD_ENV_VARS: dict[JobKind, str] = {
    JobKind.TRAIN: "RUNPOD_MAX_USD_TRAIN",
    JobKind.PROPAGATE: "RUNPOD_MAX_USD_PROPAGATE",
    JobKind.SEARCH: "RUNPOD_MAX_USD_SEARCH",
}
_DEFAULT_MAX_USD = 2.00
_DEFAULT_GPU_TYPE = "NVIDIA GeForce RTX 4090"
_DEFAULT_POLL_INTERVAL_SECONDS = 60
_DEFAULT_CONTAINER_DISK_GB = 40
_DEFAULT_CLOUD_TYPE = "COMMUNITY"
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


def container_disk_gb_default() -> int:
    """Hosts COMMUNITY frequentemente não têm 40GB de disco de container
    livres — "This machine does not have the resources to deploy your pod"
    (visto 3× em e2e no DEV, independente do gpu_type). Tunável por env
    sem mudar o default de produção."""
    return _env_int("RUNPOD_CONTAINER_DISK_GB", _DEFAULT_CONTAINER_DISK_GB)


def cloud_type_default() -> str:
    """COMMUNITY (barato) por default; RUNPOD_CLOUD_TYPE=SECURE quando a
    community estiver sem capacidade pro spec pedido."""
    return os.environ.get("RUNPOD_CLOUD_TYPE", _DEFAULT_CLOUD_TYPE)


def estimate_cost_usd(price_usd_h: float, timeout_seconds: int) -> float:
    return round(price_usd_h * (timeout_seconds / 3600.0), 4)


def margem_de_saldo() -> float:
    """Quanto de folga o saldo precisa ter sobre o custo projetado (default 1,25).

    Não é conservadorismo gratuito: a projeção sai do timeout, e um job que
    demora mais que o previsto (a placa sorteada é mais lenta, o dataset é
    maior) gasta acima da estimativa. 25% cobre o desvio comum sem travar
    disparo legítimo."""
    return _env_float("RUNPOD_SALDO_MARGEM", 1.25)


def check_saldo(client: Any, estimated_cost: float, *, kind: JobKind | str) -> float:
    """Confere se a conta aguenta o job ANTES de criar o pod. Devolve o saldo.

    Complementa `check_cost_cap`, não substitui: o teto diz quanto queremos
    gastar, o saldo diz quanto a conta pode. Foram necessários os dois porque
    em 02/09 o teto autorizado (US$ 40) era o DOBRO do saldo real (US$ 20,30),
    e três pods concorrentes teriam esgotado a conta em ~9h contra ~8h de
    treino — todos morrendo juntos, perdendo o que já fora pago.

    Saldo ilegível NÃO bloqueia: avisa alto e deixa passar. Uma falha de leitura
    da API de billing não pode impedir um treino autorizado — o teto de custo
    continua guardando o orçamento nesse caso.
    """
    try:
        saldo = float(client.get_saldo())
    except Exception as exc:  # noqa: BLE001 — billing fora do ar não trava treino autorizado
        logger.warning(
            "check_saldo: saldo ilegível (%s) — seguindo só com o teto de custo", exc
        )
        return float("nan")

    preciso = estimated_cost * margem_de_saldo()
    if saldo < preciso:
        raise SaldoInsuficienteError(
            f"Saldo da conta RunPod (${saldo:.2f}) não cobre o job kind={JobKind(kind).value} "
            f"(projetado ${estimated_cost:.2f} × margem {margem_de_saldo():.2f} = ${preciso:.2f}) "
            "— pod NÃO criado. Recarregue a conta ou reduza o timeout do job."
        )
    # Alerta antes do bloqueio: dá tempo de recarregar sem interromper nada.
    if saldo < preciso * 2:
        logger.warning(
            "runpod_saldo_baixo: $%.2f na conta, projetado $%.2f para este job — "
            "resta folga para ~%.1f job(s) deste tamanho. Considere recarregar.",
            saldo, estimated_cost, saldo / estimated_cost if estimated_cost else 0.0,
        )
    return saldo


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
    # RETREINO EM LOOP (21/08, jobs 3091cfc9 e ce4e1969): quando o onstart
    # TERMINA, a RunPod reinicia o container e roda o onstart de novo — o
    # treino recomeça do zero e, ao fim, SOBRESCREVE os artefatos bons no
    # mesmo key. O trap em `curl` falhava em silêncio (`|| true`; a imagem
    # nvidia/cuda não traz curl), e a camada 2 (watchdog) perdia o
    # `completed` para o callback de progresso do retreino. Duas defesas,
    # ambas independentes da imagem:
    #  (1b) DELETE do próprio pod em Python (urllib existe em toda imagem);
    #  (1c) `sleep infinity` — o onstart NUNCA termina por conta própria.
    #       Se toda autodestruição falhar, o pod fica OCIOSO (não retreina)
    #       até o watchdog/reconciler matá-lo. Ocioso custa centavos;
    #       retreino custa o artefato.
    # `|| true` depois do `timeout`: com `set -e`, um exit != 0 do executor
    # abortaria o script antes da autodestruição — e o container reiniciaria
    # em loop de erro.
    self_destruct_py = (
        "import os, urllib.request\n"
        'pid = os.environ.get("RUNPOD_POD_ID"); key = os.environ.get("RUNPOD_API_KEY")\n'
        "if pid and key:\n"
        "    req = urllib.request.Request(\n"
        '        f"https://rest.runpod.io/v1/pods/{pid}", method="DELETE",\n'
        '        headers={"Authorization": f"Bearer {key}"},\n'
        "    )\n"
        "    try:\n"
        "        urllib.request.urlopen(req, timeout=30)\n"
        "    except Exception:\n"
        "        pass\n"
    )
    py_marker = "RECOGNITION_SELF_DESTRUCT_EOF"
    return (
        "#!/bin/bash\n"
        "set -e\n"
        "cd /root\n"
        f"cat > /root/{executor_filename} <<'{marker}'\n"
        f"{executor_source}\n"
        f"{marker}\n"
        f"trap '{self_destruct}' EXIT\n"
        f"timeout {int(timeout_seconds)} python3 /root/{executor_filename} || true\n"
        f"python3 - <<'{py_marker}'\n"
        f"{self_destruct_py}"
        f"{py_marker}\n"
        "sleep infinity\n"
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
            # Causa REAL, não "Job runpod failed" pelado. Diagnosticar uma
            # falha de época 0 sem isto é adivinhar — e os logs do pod
            # expiram junto com o pod (D-155).
            detalhe = (
                state.get("error")
                or state.get("error_message")
                or (state.get("metrics") or {}).get("error")
                or state.get("stderr")
                or ""
            )
            exit_code = state.get("exit_code")
            partes = [f"Job runpod failed: job={job_id}"]
            if exit_code is not None:
                partes.append(f"exit={exit_code}")
            if detalhe:
                partes.append(f"causa={str(detalhe)[:400]}")
            else:
                partes.append(
                    "causa=NAO REPORTADA pelo runner (state sem error/stderr) "
                    f"— chaves recebidas: {sorted(state)}"
                )
            raise RuntimeError(" | ".join(partes))

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
    on_dispatched_fn: Callable[[dict[str, Any]], None] | None = None,
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

    `on_dispatched_fn` (opcional): chamado logo APÓS `persist_instance_ref_fn`
    (pod já criado, `gpu_instance_ref` já persistido), com
    `{"pod_id", "gpu_type", "price_usd_h", "estimated_usd"}` — o caller
    (`tasks/propagation.py`) usa isso pra marcar `metrics.stage="gpu_starting"`
    no job ANTES do primeiro callback do executor (cold start do pod dura
    minutos sem nenhum callback — sem isso a UI fica sem sinal nenhum nesse
    intervalo). Ausência de `on_dispatched_fn` = comportamento idêntico ao
    anterior (nenhuma chamada extra).

    Retorna `{"status": "completed", "metrics": {...+"gpu_cost": {...}},
    "pod_id": str}`. Levanta `CostCapExceededError` (teto estourado, ANTES
    de criar o pod), `JobStoppedError`, ou `RuntimeError`/`RunPodError`
    conforme o caso — SEMPRE termina o pod (finally) uma vez criado.
    """
    kind = JobKind(kind)
    gpu_type = gpu_type or gpu_type_default()
    timeout_seconds = timeout_seconds or timeout_seconds_for_kind(kind)
    poll_interval = poll_interval or poll_interval_seconds()

    # O tier tem de ser o MESMO na cotação e no create_pod (linha do cloud_type
    # abaixo): a API devolve o preço da COMMUNITY quando ninguém pergunta, e
    # cotar COMMUNITY para rodar em SECURE valida o teto contra menos da metade
    # da conta (4090 medida em 02/09: $0,34 vs $0,74).
    cloud_type = cloud_type_default()
    price = client.get_gpu_price(gpu_type, secure_cloud=cloud_type.upper() == "SECURE")
    estimated_cost = estimate_cost_usd(price, timeout_seconds)
    check_cost_cap(kind, estimated_cost)
    check_saldo(client, estimated_cost, kind=kind)

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
        container_disk_gb=container_disk_gb_default(),
        cloud_type=cloud_type,
    )
    pod_id = str(pod["id"])
    persist_instance_ref_fn(pod_id)
    if on_dispatched_fn is not None:
        on_dispatched_fn({
            "pod_id": pod_id,
            "gpu_type": gpu_type,
            "price_usd_h": price,
            "estimated_usd": estimated_cost,
        })
    logger.info(
        "runpod_job_dispatched: kind=%s job=%s pod=%s gpu=%s price_usd_h=%.4f "
        "estimated_usd=%.4f timeout=%ds",
        kind.value, job_id, pod_id, gpu_type, price, estimated_cost, timeout_seconds,
    )

    def _custo() -> dict:
        return {
            "provider": "runpod",
            "gpu_type": gpu_type,
            "price_usd_h": price,
            "estimated_usd": estimated_cost,
            "actual_usd": _best_effort_actual_cost(client, pod_id),
        }

    try:
        watch_result = _watch(
            client, pod_id, job_id, poll_status_fn, verify_completed_fn,
            timeout_seconds, poll_interval,
        )
    except BaseException as exc:
        # D2 — ORDEM: capturar log → anexar → SÓ ENTÃO terminar.
        #
        # `terminate_pod` no `finally` destruía a evidência de TODA falha de
        # pod: o log morria junto e o diagnóstico virava adivinhação (custou
        # 9 pods e duas paradas nesta missão). Se a captura falhar, o pod é
        # terminado do mesmo jeito — dinheiro vale mais que evidência — mas a
        # falha da captura é dita, nunca engolida.
        log_pod = ""
        try:
            log_pod = client.get_pod_logs(pod_id) or ""
        except Exception as log_exc:  # noqa: BLE001
            logger.warning("runpod_log_capture_falhou: pod=%s err=%s", pod_id, log_exc)
            log_pod = f"(captura do log falhou: {log_exc})"
        if log_pod:
            logger.error(
                "runpod_pod_log job=%s pod=%s (últimas linhas):\n%s",
                job_id, pod_id, "\n".join(log_pod.splitlines()[-50:]),
            )
        try:
            exc.pod_log = log_pod  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass

        # Custo real ANTES de propagar: no TREINO 2 o job falhou na época 0 e
        # `actual_usd` ficou NULL porque o cálculo vivia depois do `_watch`.
        # Falha custa dinheiro igual — a conta tem que fechar mesmo assim.
        # Anexado à exceção para o caller persistir (dispatch_training).
        client.terminate_pod(pod_id)
        try:
            exc.gpu_cost = _custo()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 — exceção exótica sem __dict__
            logger.warning("runpod_cost_anexo_falhou: job=%s", job_id)
        raise
    else:
        client.terminate_pod(pod_id)

    metrics = dict(watch_result.get("metrics") or {})
    metrics["gpu_cost"] = _custo()
    return {"status": watch_result["status"], "metrics": metrics, "pod_id": pod_id}
