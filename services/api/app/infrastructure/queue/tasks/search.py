"""
Recognition — Search Dispatch Task (busca por conteúdo, RunPod/OWLv2).

`dispatch_search(job_id)` despacha um `search_jobs` JÁ CRIADO (seleção
materializada e validada na criação — ver
`api/v1/training/search_handlers.py::create_search_job_handler`) pro runner
genérico RunPod (`infrastructure/gpu/runpod_runner.py::run_runpod_job`,
`kind=JobKind.SEARCH`), mesmo padrão de `tasks/propagation.py::
dispatch_propagation`.

Cadeia de guardas ANTES de qualquer chamada de rede/GPU (nesta ordem —
qualquer falha marca o job 'failed' com motivo legível, NUNCA silenciosa,
NUNCA prossegue parcialmente):
  1. `_third_party_cloud_training_enabled` (mesmo gate ADR-0047/0060 do
     treino/propagação, reusado de `tasks/training.py` — busca por
     conteúdo TAMBÉM é nuvem de terceiro);
  2. API key RunPod resolvível pro tenant;
  3. 🔴 REVALIDAÇÃO da seleção (`domain/services/search_cloud_guard.py`) —
     refetch dos frames POR ID + TENANT (`FrameRepository.
     get_by_ids_and_tenant`, nunca por critério) e RELEITURA de
     `SEARCH_CLOUD_ALLOWED_DATES` NA HORA do dispatch — nunca confia no que
     foi checado na criação do job (a env pode ter mudado; um frame pode
     ter sido reatribuído a outro tenant ou perdido o r2_key nesse meio
     tempo). Este é o guard mais importante da task: sem ele, um frame que
     passou a violar a janela permitida entre a criação e o dispatch
     chegaria até a GPU de terceiro sem ninguém notar.

OWLv2 (checkpoint `google/owlv2-base-patch16-ensemble`, Apache 2.0, HF) NÃO
tem peso hospedado no nosso R2 — o pod baixa via `transformers` (revisão
pinada dentro do próprio executor, `training/search_content.py`), mesmo
espírito do DINOv2 da propagação semeada (URL/pin oficial de terceiro,
nunca um checkpoint resolvido às cegas), mas sem a etapa de download+sha256
manual (não há um arquivo único pra hashear — `from_pretrained` resolve
vários arquivos do repositório HF; a integridade vem do commit pinado, que
é imutável). Ver `docs/WEIGHTS_LICENSES.md`.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import secrets
from typing import Any

from app.domain.services.search_cloud_guard import (
    classify_selected_frames,
    cloud_search_allowed_dates,
)
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.database.repositories.search_repository import SearchRepository
from app.infrastructure.gpu.runpod_client import RunPodClient, resolve_runpod_api_key
from app.infrastructure.gpu.runpod_runner import (
    CostCapExceededError,
    JobKind,
    JobStoppedError,
    run_runpod_job,
)
from app.infrastructure.gpu.runpod_runner import (
    _best_effort_actual_cost,  # noqa: PLC2701 — best-effort billing, mesmo padrão do runner
)
from app.infrastructure.queue.celery_app import celery
from app.infrastructure.queue.tasks.training import _third_party_cloud_training_enabled
from app.infrastructure.storage.local_storage import get_storage

logger = logging.getLogger(__name__)

_PRESIGNED_GET_TTL = 21600  # 6h — mesmo TTL da propagação (tempo do pod processar tudo)
_DEFAULT_PUBLIC_API_URL = "https://api-v3-production-2b22.up.railway.app"

_DEFAULT_CONFIDENCE_THRESHOLD = 0.15  # OWLv2 dá scores baixos — ver training/search_content.py
_CONFIDENCE_THRESHOLD_ENV = "SEARCH_CONFIDENCE_THRESHOLD"
_PROGRESS_EVERY_N = 20


def _read_search_executor_source() -> str:
    """Lê o runner self-contained embarcado no onstart (heredoc) — mesmo
    padrão de `tasks/propagation.py::_read_propagate_executor_source`. O
    pod RunPod NÃO tem acesso ao repositório — o script inteiro é embutido
    no onstart."""
    from app.infrastructure.queue.tasks.repo_files import find_repo_file  # noqa: PLC0415

    return find_repo_file("training", "search_content.py").read_text(encoding="utf-8")


def _as_str_list(value: Any) -> list[str]:
    """Normaliza uma coluna JSONB (list) que o driver pode devolver como
    str dependendo de configuração (mesmo achado defensivo de
    `tasks/propagation.py::_as_str_list`)."""
    if isinstance(value, str):
        with contextlib.suppress(ValueError):
            value = json.loads(value)
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, str):
        with contextlib.suppress(ValueError):
            value = json.loads(value)
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        with contextlib.suppress(ValueError):
            value = json.loads(value)
    return value if isinstance(value, dict) else {}


def _confidence_threshold() -> float:
    raw = os.environ.get(_CONFIDENCE_THRESHOLD_ENV, "")
    try:
        return float(raw) if raw else _DEFAULT_CONFIDENCE_THRESHOLD
    except ValueError:
        logger.warning(
            "search_confidence_threshold_env_invalido: %s=%r — usando default %.2f",
            _CONFIDENCE_THRESHOLD_ENV, raw, _DEFAULT_CONFIDENCE_THRESHOLD,
        )
        return _DEFAULT_CONFIDENCE_THRESHOLD


def _build_manifest(
    job_id: str, terms: list[dict[str, Any]], frames_by_id: dict[str, dict[str, Any]],
    selected_frame_ids: list[str], storage: Any,
) -> dict[str, Any]:
    """Manifesto JSON que o executor baixa (MANIFEST_URL): termos (label +
    query em inglês) e frames (frame_id + imagem presigned) — SEM sementes/
    pool, ao contrário da propagação (busca por conteúdo não tem exemplar
    humano, é open-vocabulary direto pelo texto do termo)."""
    frames = [
        {
            "frame_id": frame_id,
            "image_url": storage.generate_presigned_download_url(
                frames_by_id[frame_id]["r2_key"], ttl=_PRESIGNED_GET_TTL,
            ),
        }
        for frame_id in selected_frame_ids
        if frame_id in frames_by_id
    ]
    return {"job_id": job_id, "terms": terms, "frames": frames}


def _classify_failure_kind(exc: Exception) -> str:
    """Mesmo mapeamento de `tasks/propagation.py::_classify_failure_kind`
    — `CostCapExceededError` é `RuntimeError` mas SEMPRE significa que o
    pod nunca foi criado, checado antes do bucket genérico."""
    if isinstance(exc, CostCapExceededError):
        return "cost_cap"
    if isinstance(exc, JobStoppedError):
        return "stopped"
    if isinstance(exc, RuntimeError):
        message = str(exc)
        if "Timeout runpod" in message:
            return "timeout"
        if "terminou sem callback final" in message:
            return "pod_died"
    return "executor_error"


def _record_failure_metrics(repo: SearchRepository, job_id: str, exc: Exception) -> None:
    """Grava `metrics.failure_kind` + (best-effort) custo real já gasto —
    mesmo padrão de `tasks/propagation.py::_record_failure_metrics`.
    Billing é best-effort: qualquer erro na consulta nunca mascara a falha
    original."""
    metrics: dict[str, Any] = {"failure_kind": _classify_failure_kind(exc)}
    try:
        current_job = repo.get_by_id(job_id) or {}
        gpu_instance_ref = current_job.get("gpu_instance_ref")
        if gpu_instance_ref:
            tenant_id = str(current_job.get("tenant_id") or "")
            api_key = resolve_runpod_api_key(tenant_id)
            if api_key:
                client = RunPodClient(api_key)
                actual_usd = _best_effort_actual_cost(client, str(gpu_instance_ref))
                if actual_usd is not None:
                    existing_gpu_cost = _as_dict(current_job.get("metrics")).get("gpu_cost")
                    existing_gpu_cost = (
                        existing_gpu_cost if isinstance(existing_gpu_cost, dict) else {}
                    )
                    metrics["gpu_cost"] = {**existing_gpu_cost, "actual_usd": actual_usd}
    except Exception as billing_exc:  # noqa: BLE001 — billing nunca mascara a falha original
        logger.warning(
            "search_failure_billing_lookup_failed: job=%s err=%s", job_id, billing_exc,
        )
    with contextlib.suppress(Exception):
        repo.merge_metrics(job_id, metrics)


@celery.task(
    bind=True, max_retries=0, queue="training",
    name="tasks.search.dispatch_search",
)
def dispatch_search(self, job_id: str) -> dict:  # noqa: ARG001
    """Despacha um `search_jobs` já criado pro RunPod.

    `max_retries=0` (mesma razão de `dispatch_propagation`): um retry
    automático reprovisionaria GPU paga sobre um job que JÁ falhou uma
    checagem de segurança/integridade — melhor exigir um novo
    `POST /search/jobs` explícito (que revalida tudo do zero).
    """
    pool = DatabasePool.get_instance()
    repo = SearchRepository(pool)
    frame_repo = FrameRepository(pool)

    job = repo.get_by_id(job_id)
    if job is None:
        logger.error("search_dispatch_job_missing: job=%s", job_id)
        return {"job_id": job_id, "status": "missing"}

    tenant_id = str(job["tenant_id"])
    repo.mark_running(job_id)
    # Marco de fase ANTES de qualquer guard — o cold start do pod dura
    # minutos sem nenhum callback do executor; a UI reconstrói a barra de
    # progresso só olhando `search_jobs.metrics`.
    repo.merge_metrics(job_id, {"stage": "preparing"})

    def _fail(reason: str) -> dict:
        logger.warning(
            "search_dispatch_failed: job=%s tenant=%s reason=%s", job_id, tenant_id, reason,
        )
        repo.mark_failed(job_id, reason)
        return {"job_id": job_id, "status": "failed", "reason": reason}

    if not _third_party_cloud_training_enabled(tenant_id):
        return _fail(
            "Busca em nuvem de terceiro desabilitada para este tenant "
            "(training_third_party_cloud_enabled=false)"
        )

    api_key = resolve_runpod_api_key(tenant_id)
    if not api_key:
        return _fail("Nenhuma chave RunPod resolvível para o tenant")

    # 🔴 Guard fail-closed relido NA HORA — nunca confia no que foi checado
    # na criação do job (env pode ter mudado desde então).
    allowed_ranges = cloud_search_allowed_dates()
    if allowed_ranges is None:
        return _fail(
            "Busca em nuvem desabilitada — SEARCH_CLOUD_ALLOWED_DATES não "
            "configurada (revalidado no dispatch)"
        )

    selected_frame_ids = _as_str_list(job.get("selected_frame_ids"))
    terms = _as_list(job.get("terms"))
    if not selected_frame_ids:
        return _fail("job sem frames selecionados — nada pra buscar")
    if not terms:
        return _fail("job sem termos de busca — nada pra buscar")

    frames = frame_repo.get_by_ids_and_tenant(selected_frame_ids, tenant_id)
    frames_by_id = {str(f["id"]): f for f in frames}

    fetched_ids = set(frames_by_id.keys())
    expected_ids = set(selected_frame_ids)
    if fetched_ids != expected_ids:
        missing = sorted(expected_ids - fetched_ids)
        return _fail(
            f"seleção mudou desde a criação do job — frames ausentes/fora do "
            f"tenant: {missing}"
        )

    ineligible = classify_selected_frames(selected_frame_ids, frames_by_id, allowed_ranges)
    if ineligible:
        reasons = [{"frame_id": item.frame_id, "reason": item.reason} for item in ineligible]
        return _fail(f"guard de nuvem falhou na revalidação do dispatch: {reasons}")

    storage = get_storage(tenant_id)
    manifest = _build_manifest(job_id, terms, frames_by_id, selected_frame_ids, storage)

    manifest_key = f"search/{tenant_id}/{job_id}/manifest.json"
    storage.upload_bytes(
        manifest_key, json.dumps(manifest).encode("utf-8"), "application/json",
    )
    manifest_url = storage.generate_presigned_download_url(
        manifest_key, ttl=_PRESIGNED_GET_TTL,
    )

    callback_token = secrets.token_urlsafe(48)
    repo.set_callback_token(job_id, callback_token)

    base_url = os.environ.get("PUBLIC_API_URL", _DEFAULT_PUBLIC_API_URL).rstrip("/")
    callback_url = f"{base_url}/api/v1/training/search/jobs/{job_id}/callback"

    remote_env = {
        "MANIFEST_URL": manifest_url,
        "CALLBACK_URL": callback_url,
        "CALLBACK_TOKEN": callback_token,
        "CONFIDENCE_THRESHOLD": str(_confidence_threshold()),
        "PROGRESS_EVERY_N": str(_PROGRESS_EVERY_N),
    }

    client = RunPodClient(api_key)

    # Recheca status ANTES de provisionar — fecha a janela de corrida entre
    # o início do dispatch e este ponto (mesmo padrão de
    # tasks/propagation.py::dispatch_propagation).
    current = repo.get_by_id(job_id)
    if (current or {}).get("status") == "stopped":
        with contextlib.suppress(Exception):
            repo.revoke_callback_token(job_id)
        return {"job_id": job_id, "status": "stopped"}

    def _poll_status() -> dict[str, Any]:
        current_job = repo.get_by_id(job_id)
        return {
            "status": (current_job or {}).get("status"),
            "metrics": _as_dict((current_job or {}).get("metrics")),
        }

    def _persist_instance_ref(pod_id: str) -> None:
        repo.set_gpu_instance_ref(job_id, pod_id)

    def _verify_completed(_state: dict[str, Any]) -> bool:
        """"Nunca sucesso silencioso": confirma que o CALLBACK já persistiu
        `findings_count` (sempre setado por `apply_callback_completed`,
        mesmo que 0 — "completed sem achado = completed honesto") antes de
        reportar sucesso pro watchdog."""
        current_job = repo.get_by_id(job_id)
        return (
            (current_job or {}).get("status") == "completed"
            and (current_job or {}).get("findings_count") is not None
        )

    def _on_dispatched(info: dict[str, Any]) -> None:
        """Pod criado, gpu_instance_ref já persistido — sobrevive até o
        primeiro callback do executor sobrescrever `stage`."""
        repo.merge_metrics(job_id, {
            "stage": "gpu_starting",
            "gpu_cost": {
                "provider": "runpod",
                "gpu_type": info.get("gpu_type"),
                "price_usd_h": info.get("price_usd_h"),
                "estimated_usd": info.get("estimated_usd"),
                "actual_usd": None,
            },
        })

    # Marco de fase — seleção revalidada, manifesto resolvido, prestes a
    # chamar a RunPod (preço → teto de custo → create_pod, dentro de
    # run_runpod_job).
    repo.merge_metrics(job_id, {"stage": "creating_pod"})

    try:
        result = run_runpod_job(
            kind=JobKind.SEARCH,
            job_id=job_id,
            client=client,
            executor_source=_read_search_executor_source(),
            executor_filename="search_content.py",
            env=remote_env,
            poll_status_fn=_poll_status,
            persist_instance_ref_fn=_persist_instance_ref,
            verify_completed_fn=_verify_completed,
            on_dispatched_fn=_on_dispatched,
        )
    except JobStoppedError as exc:
        logger.info("search_dispatch_stopped: job=%s", job_id)
        _record_failure_metrics(repo, job_id, exc)
        with contextlib.suppress(Exception):
            repo.revoke_callback_token(job_id)
        return {"job_id": job_id, "status": "stopped"}
    except Exception as exc:  # noqa: BLE001 — qualquer falha vira job 'failed' legível
        _record_failure_metrics(repo, job_id, exc)
        with contextlib.suppress(Exception):
            repo.revoke_callback_token(job_id)
        return _fail(str(exc)[:2000])

    # SEMPRE: revogar o token de callback (o pod já foi terminado dentro de
    # run_runpod_job — camada 2 de garantia de morte).
    with contextlib.suppress(Exception):
        repo.revoke_callback_token(job_id)

    metrics = result.get("metrics") or {}
    if metrics:
        repo.merge_metrics(job_id, metrics)

    return {"job_id": job_id, "status": result["status"], "metrics": metrics}
