"""
Recognition — Propagation Dispatch Task (propagação semeada, RunPod).

`dispatch_propagation(job_id)` despacha um `propagation_jobs` JÁ CRIADO
(pool materializado e validado na criação — ver
`api/v1/training/propagation_handlers.py::create_propagation_job_handler`)
pro runner genérico RunPod (`infrastructure/gpu/runpod_runner.py::
run_runpod_job`, `kind=JobKind.PROPAGATE`), mesmo padrão de
`tasks/training.py::_run_runpod_train_job`.

Cadeia de guardas ANTES de qualquer chamada de rede/GPU (nesta ordem —
qualquer falha marca o job 'failed' com motivo legível, NUNCA silenciosa,
NUNCA prossegue parcialmente):
  1. `training_third_party_cloud_enabled` (mesmo gate ADR-0047/0060 do
     treino, reusado de `tasks/training.py` — propagação TAMBÉM é nuvem de
     terceiro);
  2. API key RunPod resolvível pro tenant;
  3. 🔴 REVALIDAÇÃO do pool (`domain/services/propagation_pool.py::
     revalidate_pool`) — refetch dos frames POR ID (nunca por critério de
     novo) contra `pool_criteria`/`pool_hash` gravados na criação. Este é
     o guard mais importante do PR: sem ele, um frame que passou a violar
     o critério original entre a criação do job e o dispatch (câmera
     reatribuída, frame deletado, frame novo "coincidindo" com o mesmo
     critério) chegaria até a GPU de terceiro sem ninguém notar.

Pesos: SAM ViT-B vem do NOSSO R2 (bucket de plataforma, mesmo `models/`
que `pre-annotation-service` já usa — `get_storage()` sem tenant_id);
DINOv2 vem DIRETO da URL oficial da Meta (o próprio pod baixa —
`dl.fbaipublicfiles.com`, nunca passa pelo nosso storage). sha256 dos dois
pinados em `docs/WEIGHTS_LICENSES.md` e injetados no ambiente do pod — o
executor (`training/propagate_seeded.py::download_and_verify_weight`)
recusa carregar qualquer um sem o hash bater.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import secrets
from typing import Any

from app.domain.services.propagation_pool import (
    PoolGuardError,
    parse_pool_criteria,
    revalidate_pool,
)
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.database.repositories.propagation_repository import (
    PropagationRepository,
)
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

_PRESIGNED_GET_TTL = 21600  # 6h — dá tempo do pod processar 662 frames
_DEFAULT_PUBLIC_API_URL = "https://api-v3-production-2b22.up.railway.app"

# docs/WEIGHTS_LICENSES.md — pesos pinados, MANTER EM SINCRONIA.
# SAM ViT-B já vinha do PR #340 (pre-annotation-service); DINOv2 pinado
# nesta task (sha256 calculado baixando o arquivo DIRETO da URL oficial da
# Meta, mesma metodologia usada pro SAM/GroundingDINO — nunca copiado de
# um mirror de terceiro).
_SAM_WEIGHTS_R2_KEY = "models/sam_vit_b_01ec64.pth"
_SAM_WEIGHTS_SHA256 = (
    "ec2df62732614e57411cdcf32a23ffdf28910380d03139ee0f4fcbe91eb8c912"
)
_DINOV2_WEIGHTS_URL = (
    "https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth"
)
_DINOV2_WEIGHTS_SHA256 = (
    "b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9"
)

_DEFAULT_SIMILARITY_THRESHOLD = 0.65
_PROGRESS_EVERY_N = 20


def _read_propagate_executor_source() -> str:
    """Lê o runner self-contained embarcado no onstart (heredoc) — mesmo
    padrão de `tasks/training.py::_read_remote_train_source`. O pod RunPod
    NÃO tem acesso ao repositório — o script inteiro é embutido no onstart."""
    from app.infrastructure.queue.tasks.repo_files import find_repo_file  # noqa: PLC0415

    return find_repo_file("training", "propagate_seeded.py").read_text(encoding="utf-8")


def _as_str_list(value: Any) -> list[str]:
    """Normaliza uma coluna JSONB (list) que o driver pode devolver como
    str dependendo de configuração (mesmo achado defensivo de
    `tasks/training.py::_poll_status` pra `metrics`)."""
    if isinstance(value, str):
        with contextlib.suppress(ValueError):
            value = json.loads(value)
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        with contextlib.suppress(ValueError):
            value = json.loads(value)
    return value if isinstance(value, dict) else {}


def _build_manifest(
    storage: Any,
    frames_by_id: dict[str, dict[str, Any]],
    pool_frame_ids: list[str],
    seed_frame_ids: list[str],
    seed_boxes_by_frame: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Monta o manifesto JSON que o executor baixa (MANIFEST_URL): sementes
    (frame + imagem presigned + caixas humanas) e pool (frame + imagem
    presigned, sem anotação). `class` de cada caixa-semente é o
    `class_name` LITERAL gravado em `frame_annotations` — o executor nunca
    inventa/traduz label nenhum (o mesmo texto é o que
    `AnnotationService.get_frame_annotations` compara, case-insensitive,
    contra as classes conhecidas do tenant)."""
    seeds: list[dict[str, Any]] = []
    for frame_id in seed_frame_ids:
        boxes = seed_boxes_by_frame.get(frame_id) or []
        if not boxes:
            continue
        frame = frames_by_id.get(frame_id)
        if frame is None:
            continue
        seeds.append({
            "frame_id": frame_id,
            "image_url": storage.generate_presigned_download_url(
                frame["r2_key"], ttl=_PRESIGNED_GET_TTL,
            ),
            "boxes": [
                {
                    "class": box["class_name"],
                    "bbox": [
                        float(box["x_center"]), float(box["y_center"]),
                        float(box["width"]), float(box["height"]),
                    ],
                }
                for box in boxes
            ],
        })

    pool = [
        {
            "frame_id": frame_id,
            "image_url": storage.generate_presigned_download_url(
                frames_by_id[frame_id]["r2_key"], ttl=_PRESIGNED_GET_TTL,
            ),
        }
        for frame_id in pool_frame_ids
        if frame_id in frames_by_id
    ]
    return {"seeds": seeds, "pool": pool}


def _classify_failure_kind(exc: Exception) -> str:
    """Classifica a exceção do runner pra `metrics.failure_kind` — a UI
    mostra "por que falhou" sem parsear a mensagem técnica completa (que
    continua íntegra em `error_reason`, via `_fail`). `CostCapExceededError`
    é `RuntimeError` mas SEMPRE significa que o pod nunca foi criado (o
    guard de custo em `runpod_runner.py::run_runpod_job` corre ANTES de
    `create_pod`) — checado primeiro, antes do bucket genérico de
    `RuntimeError`."""
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


def _record_failure_metrics(
    repo: PropagationRepository, job_id: str, exc: Exception,
) -> None:
    """Grava `metrics.failure_kind` + (best-effort) custo real já gasto —
    chamado ANTES/junto de marcar o job (`_fail`/`mark_failed`, ou do
    retorno 'stopped'). Billing é best-effort: qualquer erro na consulta
    (RunPodError, chave ausente, pool indisponível) vira log warning e
    NUNCA mascara a falha original — o caller sempre segue pro seu próprio
    tratamento de erro depois desta chamada."""
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
            "propagation_failure_billing_lookup_failed: job=%s err=%s",
            job_id, billing_exc,
        )
    with contextlib.suppress(Exception):
        repo.merge_metrics(job_id, metrics)


@celery.task(
    bind=True, max_retries=0, queue="training",
    name="tasks.propagation.dispatch_propagation",
)
def dispatch_propagation(self, job_id: str) -> dict:  # noqa: ARG001
    """Despacha um `propagation_jobs` já criado pro RunPod.

    `max_retries=0` (vs. o `retry=1` de `dispatch_training`): um retry
    automático reprovisionaria GPU paga sobre um job que JÁ falhou uma
    checagem de segurança/integridade (flag desligada, guard de pool) —
    melhor exigir um novo `POST /propagation/jobs` explícito do operador
    (que revalida tudo do zero) do que reagendar silenciosamente.
    """
    pool = DatabasePool.get_instance()
    repo = PropagationRepository(pool)
    frame_repo = FrameRepository(pool)
    annotation_repo = AnnotationRepository(pool)

    job = repo.get_by_id(job_id)
    if job is None:
        logger.error("propagation_dispatch_job_missing: job=%s", job_id)
        return {"job_id": job_id, "status": "missing"}

    tenant_id = str(job["tenant_id"])
    repo.mark_running(job_id)
    # Marco de fase ANTES de qualquer guard — o cold start do pod dura
    # minutos sem nenhum callback do executor; a UI reconstrói a barra de
    # progresso só olhando `propagation_jobs.metrics` (nunca `railway logs`).
    repo.merge_metrics(job_id, {"stage": "preparing"})

    def _fail(reason: str) -> dict:
        logger.warning(
            "propagation_dispatch_failed: job=%s tenant=%s reason=%s",
            job_id, tenant_id, reason,
        )
        repo.mark_failed(job_id, reason)
        return {"job_id": job_id, "status": "failed", "reason": reason}

    if not _third_party_cloud_training_enabled(tenant_id):
        return _fail(
            "Propagação em nuvem de terceiro desabilitada para este tenant "
            "(training_third_party_cloud_enabled=false)"
        )

    api_key = resolve_runpod_api_key(tenant_id)
    if not api_key:
        return _fail("Nenhuma chave RunPod resolvível para o tenant")

    pool_criteria = _as_dict(job.get("pool_criteria"))
    pool_frame_ids = _as_str_list(job.get("pool_frame_ids"))
    seed_frame_ids = _as_str_list(job.get("seed_frame_ids"))

    try:
        camera_ids, date_from, date_to = parse_pool_criteria(pool_criteria)
        frames = frame_repo.get_by_ids(pool_frame_ids)
        revalidate_pool(
            frames,
            tenant_id=tenant_id,
            camera_ids=camera_ids,
            date_from=date_from,
            date_to=date_to,
            expected_frame_ids=pool_frame_ids,
            expected_pool_hash=str(job.get("pool_hash") or ""),
        )
    except PoolGuardError as exc:
        return _fail(f"Guard de pool falhou no dispatch: {exc}")

    frames_by_id = {str(f["id"]): f for f in frames}
    seed_boxes_rows = annotation_repo.get_manual_annotations_for_frames(seed_frame_ids)
    seed_boxes_by_frame: dict[str, list[dict[str, Any]]] = {}
    for row in seed_boxes_rows:
        seed_boxes_by_frame.setdefault(str(row["frame_id"]), []).append(row)

    storage = get_storage(tenant_id)
    manifest = _build_manifest(
        storage, frames_by_id, pool_frame_ids, seed_frame_ids, seed_boxes_by_frame,
    )
    if not manifest["seeds"]:
        return _fail(
            "nenhuma semente com caixas humanas disponível dentro do pool "
            "no momento do dispatch"
        )

    manifest_key = f"propagation/{tenant_id}/{job_id}/manifest.json"
    storage.upload_bytes(
        manifest_key, json.dumps(manifest).encode("utf-8"), "application/json",
    )
    manifest_url = storage.generate_presigned_download_url(
        manifest_key, ttl=_PRESIGNED_GET_TTL,
    )

    # Pesos de plataforma (SAM) — bucket compartilhado models/, SEM
    # tenant_id (mesmo storage que pre-annotation-service já usa).
    platform_storage = get_storage()
    sam_url = platform_storage.generate_presigned_download_url(
        _SAM_WEIGHTS_R2_KEY, ttl=_PRESIGNED_GET_TTL,
    )

    callback_token = secrets.token_urlsafe(48)
    repo.set_callback_token(job_id, callback_token)

    base_url = os.environ.get("PUBLIC_API_URL", _DEFAULT_PUBLIC_API_URL).rstrip("/")
    callback_url = f"{base_url}/api/v1/training/propagation/jobs/{job_id}/callback"

    remote_env = {
        "MANIFEST_URL": manifest_url,
        "CALLBACK_URL": callback_url,
        "CALLBACK_TOKEN": callback_token,
        "SAM_WEIGHTS_URL": sam_url,
        "SAM_WEIGHTS_SHA256": _SAM_WEIGHTS_SHA256,
        "DINOV2_WEIGHTS_URL": _DINOV2_WEIGHTS_URL,
        "DINOV2_WEIGHTS_SHA256": _DINOV2_WEIGHTS_SHA256,
        "SIMILARITY_THRESHOLD": str(
            pool_criteria.get("threshold", _DEFAULT_SIMILARITY_THRESHOLD)
        ),
        "PROGRESS_EVERY_N": str(_PROGRESS_EVERY_N),
    }
    max_results = pool_criteria.get("max_results")
    if max_results:
        remote_env["MAX_RESULTS"] = str(max_results)

    client = RunPodClient(api_key)

    # Recheca status ANTES de provisionar — fecha a janela de corrida entre
    # o início do dispatch e este ponto (mesmo padrão de
    # tasks/training.py::_run_runpod_train_job).
    current = repo.get_by_id(job_id)
    if (current or {}).get("status") == "stopped":
        with contextlib.suppress(Exception):
            repo.set_callback_token(job_id, None)
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
        `proposals_count` (sempre setado por `apply_callback_completed`,
        mesmo que 0 — "completed sem propostas = completed honesto") antes
        de reportar sucesso pro watchdog."""
        current_job = repo.get_by_id(job_id)
        return (
            (current_job or {}).get("status") == "completed"
            and (current_job or {}).get("proposals_count") is not None
        )

    def _on_dispatched(info: dict[str, Any]) -> None:
        """Pod criado, gpu_instance_ref já persistido — sobrevive até o
        primeiro callback do executor sobrescrever `stage` (manifest/deps/
        weights/...). `gpu_cost.actual_usd=None` aqui — só vira número real
        no fim (`run_runpod_job`, happy path) ou em `_record_failure_metrics`
        (falha com custo já gasto)."""
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

    # Marco de fase — pool revalidado, manifesto/pesos resolvidos, prestes a
    # chamar a RunPod (preço → teto de custo → create_pod, dentro de
    # run_runpod_job).
    repo.merge_metrics(job_id, {"stage": "creating_pod"})

    try:
        result = run_runpod_job(
            kind=JobKind.PROPAGATE,
            job_id=job_id,
            client=client,
            executor_source=_read_propagate_executor_source(),
            executor_filename="propagate_seeded.py",
            env=remote_env,
            poll_status_fn=_poll_status,
            persist_instance_ref_fn=_persist_instance_ref,
            verify_completed_fn=_verify_completed,
            on_dispatched_fn=_on_dispatched,
        )
    except JobStoppedError as exc:
        logger.info("propagation_dispatch_stopped: job=%s", job_id)
        _record_failure_metrics(repo, job_id, exc)
        with contextlib.suppress(Exception):
            repo.set_callback_token(job_id, None)
        return {"job_id": job_id, "status": "stopped"}
    except Exception as exc:  # noqa: BLE001 — qualquer falha vira job 'failed' legível
        _record_failure_metrics(repo, job_id, exc)
        with contextlib.suppress(Exception):
            repo.set_callback_token(job_id, None)
        return _fail(str(exc)[:2000])

    # SEMPRE: revogar o token de callback (o pod já foi terminado dentro de
    # run_runpod_job — camada 2 de garantia de morte).
    with contextlib.suppress(Exception):
        repo.set_callback_token(job_id, None)

    metrics = result.get("metrics") or {}
    if metrics:
        repo.merge_metrics(job_id, metrics)

    return {"job_id": job_id, "status": result["status"], "metrics": metrics}
