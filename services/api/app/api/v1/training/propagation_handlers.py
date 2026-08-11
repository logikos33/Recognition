"""
Recognition — Propagation Job handlers (propagação semeada, RunPod).

Rotas (routes.py):
  GET  /api/v1/training/propagation/preflight            insumos pro botão
                                                          "buscar imagens
                                                          iguais" ANTES de
                                                          criar o job (pool,
                                                          sementes, job
                                                          ativo, custo) —
                                                          só leitura
  POST /api/v1/training/propagation/jobs               cria job — materializa
                                                          + valida o pool
                                                          (domain/services/
                                                          propagation_pool.py),
                                                          dispara Celery
  GET  /api/v1/training/propagation/jobs/<id>            status do job
                                                          (cross-tenant → 404)
  GET  /api/v1/training/propagation/jobs                lista jobs do tenant
  POST /api/v1/training/propagation/jobs/<id>/callback   callback da GPU
                                                          remota — SEM jwt
                                                          (X-Callback-Token)

O guard fail-closed do pool (materialize_pool na criação, revalidate_pool
no dispatch — `tasks/propagation.py`) é o núcleo de segurança deste PR;
este módulo é responsável por resolver o CRITÉRIO (câmeras + intervalo de
data) a partir do request, validar posse de câmera por tenant (C-01), e —
no callback — validar que o payload final só referencia frames DENTRO do
pool antes de gravar qualquer `pre_annotations`.
"""
import hmac
import logging
from datetime import date
from typing import Any

from flask import request

from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.domain.services.propagation_pool import PoolGuardError, materialize_pool

logger = logging.getLogger(__name__)

_VALIDATION_ONLY_POOL_LIMIT = 5
_DEFAULT_SIMILARITY_THRESHOLD = 0.65
_ERROR_MAX_LEN = 2000
_MAX_RESULTS_MIN = 1
_MAX_RESULTS_MAX = 500


def _get_pool():
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415

    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _get_propagation_repo():
    from app.infrastructure.database.repositories.propagation_repository import (  # noqa: PLC0415,E501
        PropagationRepository,
    )

    return PropagationRepository(_get_pool())


def _get_frame_repo():
    from app.infrastructure.database.repositories.frame_repository import (  # noqa: PLC0415
        FrameRepository,
    )

    return FrameRepository(_get_pool())


def _get_annotation_repo():
    from app.infrastructure.database.repositories.annotation_repository import (  # noqa: PLC0415,E501
        AnnotationRepository,
    )

    return AnnotationRepository(_get_pool())


def _get_camera_repo():
    from app.infrastructure.database.repositories.camera_repository import (  # noqa: PLC0415
        CameraRepository,
    )

    return CameraRepository(_get_pool())


def _strip_callback_token(job: "dict[str, Any] | None") -> "dict[str, Any] | None":
    """Nunca expor `callback_token` (mesmo revogado) numa resposta HTTP —
    mesmo padrão de `job_handlers.py::stop_job_handler`."""
    if job is not None:
        job.pop("callback_token", None)
    return job


def _parse_bool_query(raw: "str | None") -> bool:
    """Query params são sempre string — `?validation_only=true/1/yes/on`
    (case-insensitive) vira True; ausente ou qualquer outro valor, False."""
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _third_party_cloud_enabled(tenant_id: str) -> bool:
    """Reusa o MESMO gate ADR-0047/0060 do treino (`tasks/training.py`) —
    lazy import, mesmo padrão dos `_get_*_repo` deste módulo."""
    from app.infrastructure.queue.tasks.training import (  # noqa: PLC0415
        _third_party_cloud_training_enabled,
    )

    return _third_party_cloud_training_enabled(tenant_id)


def _resolve_runpod_api_key(tenant_id: str) -> str:
    from app.infrastructure.gpu.runpod_client import resolve_runpod_api_key  # noqa: PLC0415

    return resolve_runpod_api_key(tenant_id)


def _gpu_job_limits() -> "tuple[str, int, float]":
    """(gpu_type, timeout_seconds, max_usd) do tipo de carga PROPAGATE —
    só leitura de env/defaults, SEM chamada de rede (ao contrário de
    `_gpu_price_estimate`, que consulta a RunPod)."""
    from app.infrastructure.gpu.runpod_runner import (  # noqa: PLC0415
        JobKind,
        gpu_type_default,
        max_usd_for_kind,
        timeout_seconds_for_kind,
    )

    return (
        gpu_type_default(),
        timeout_seconds_for_kind(JobKind.PROPAGATE),
        max_usd_for_kind(JobKind.PROPAGATE),
    )


def _gpu_price_estimate(
    api_key: str, gpu_type: str, timeout_seconds: int,
) -> "tuple[float | None, float | None, bool]":
    """(price_usd_h, estimated_cost_usd, price_error). `RunPodError` (chave
    inválida, gpu_type desconhecido, RunPod fora do ar) vira campos `None` +
    `price_error=True` — NUNCA derruba o preflight inteiro, a UI mostra
    "preço indisponível". ⛔ `api_key` só é usada aqui pra instanciar o
    client — nunca logada, nunca volta no retorno."""
    from app.infrastructure.gpu.runpod_client import RunPodClient, RunPodError  # noqa: PLC0415
    from app.infrastructure.gpu.runpod_runner import estimate_cost_usd  # noqa: PLC0415

    try:
        client = RunPodClient(api_key)
        price = client.get_gpu_price(gpu_type)
    except RunPodError as exc:
        logger.warning("propagation_preflight_price_lookup_failed: err=%s", exc)
        return None, None, True
    return price, estimate_cost_usd(price, timeout_seconds), False


# --------------------------------------------------------------------------
# GET /api/v1/training/propagation/preflight
# --------------------------------------------------------------------------

def preflight_propagation_handler():
    """Preflight da propagação semeada — dados pro botão "buscar imagens
    iguais" decidir ANTES de criar o job: tamanho do pool, sementes
    disponíveis, job já em andamento do tenant, e custo estimado (RunPod).
    Só leitura — não materializa nem grava nada.
    ---
    tags:
      - training
    summary: Preflight de propagação semeada (pool/sementes/custo, sem criar job)
    security:
      - Bearer: []
    parameters:
      - in: query
        name: camera_id
        required: true
        schema: {type: string}
      - in: query
        name: date_from
        schema: {type: string, format: date}
      - in: query
        name: date_to
        schema: {type: string, format: date}
      - in: query
        name: date
        description: 'atalho — usado como date_from E date_to'
        schema: {type: string, format: date}
      - in: query
        name: validation_only
        schema: {type: boolean}
    responses:
      200:
        description: Dados de preflight (pool, sementes, job ativo, custo GPU)
    """
    try:
        tenant_id = get_tenant_id()

        camera_id = request.args.get("camera_id")
        if not camera_id:
            return error("camera_id é obrigatório", 400)

        date_from_raw = request.args.get("date_from") or request.args.get("date")
        date_to_raw = request.args.get("date_to") or request.args.get("date")
        if not date_from_raw or not date_to_raw:
            return error("date_from/date_to (ou date) são obrigatórios", 400)
        try:
            date_from = date.fromisoformat(str(date_from_raw))
            date_to = date.fromisoformat(str(date_to_raw))
        except ValueError:
            return error(
                "date_from/date_to devem estar em formato ISO (YYYY-MM-DD)", 400,
            )
        if date_from > date_to:
            return error("date_from posterior a date_to", 400)

        validation_only = _parse_bool_query(request.args.get("validation_only"))

        # Posse de câmera por tenant — cross-tenant → 404 (C-01), mesmo
        # guard da criação do job (nunca vaza existência de câmera de
        # outro tenant via a mensagem de erro).
        camera_repo = _get_camera_repo()
        if camera_repo.get_by_id_and_tenant(camera_id, str(tenant_id)) is None:
            return error("Câmera não encontrada", 404)

        frame_repo = _get_frame_repo()
        pool_frames = frame_repo.list_for_propagation_pool(
            tenant_id, [camera_id], date_from, date_to,
        )
        pool_total = len(pool_frames)
        pool_effective = (
            min(pool_total, _VALIDATION_ONLY_POOL_LIMIT) if validation_only else pool_total
        )

        annotation_repo = _get_annotation_repo()
        pool_frame_ids = [str(f["id"]) for f in pool_frames]
        manual_rows = annotation_repo.get_manual_annotations_for_frames(pool_frame_ids)
        seed_frame_count = len({str(r["frame_id"]) for r in manual_rows})
        seed_box_count = len(manual_rows)

        propagation_repo = _get_propagation_repo()
        active_job = propagation_repo.get_active_for_tenant(tenant_id)

        third_party_cloud_enabled = _third_party_cloud_enabled(str(tenant_id))

        # ⛔ nunca logar/retornar o valor da chave — só presença (bool).
        api_key = _resolve_runpod_api_key(str(tenant_id))
        runpod_configured = bool(api_key)

        gpu_type, timeout_seconds, max_usd = _gpu_job_limits()
        price_usd_h: float | None = None
        estimated_cost_usd: float | None = None
        price_error = False
        if runpod_configured:
            price_usd_h, estimated_cost_usd, price_error = _gpu_price_estimate(
                api_key, gpu_type, timeout_seconds,
            )

        return success({
            "pool_total": pool_total,
            "pool_effective": pool_effective,
            "validation_only": validation_only,
            "seed_frame_count": seed_frame_count,
            "seed_box_count": seed_box_count,
            "active_job": active_job,
            "third_party_cloud_enabled": third_party_cloud_enabled,
            "runpod_configured": runpod_configured,
            "gpu": {
                "gpu_type": gpu_type,
                "price_usd_h": price_usd_h,
                "estimated_cost_usd": estimated_cost_usd,
                "max_usd": max_usd,
                "timeout_seconds": timeout_seconds,
                "price_error": price_error,
            },
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("preflight_propagation_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# --------------------------------------------------------------------------
# POST /api/v1/training/propagation/jobs
# --------------------------------------------------------------------------

def create_propagation_job_handler():
    """Cria um job de propagação semeada.
    ---
    tags:
      - training
    summary: Cria job de propagação semeada (DINOv2+SAM no RunPod)
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          properties:
            camera_ids: {type: array, items: {type: string}}
            date_from: {type: string, format: date}
            date_to: {type: string, format: date}
            seed_frame_ids: {type: array, items: {type: string}, description: 'Opcional — default: todas as anotações humanas dos frames dentro do critério'}
            validation_only: {type: boolean, default: false}
            threshold: {type: number, default: 0.65}
            max_results: {type: integer, minimum: 1, maximum: 500, description: 'Opcional — cap de quantos frames do pool retornar propostas (top-N por confidence)'}
    responses:
      201:
        description: Job criado (queued) e despachado pro Celery
    """
    try:
        tenant_id = get_tenant_id()
        user_id = get_current_user_id()
        data = request.get_json() or {}

        camera_ids = data.get("camera_ids")
        if not isinstance(camera_ids, list) or not camera_ids:
            return error("camera_ids é obrigatório e não pode ser vazio", 400)
        camera_ids = [str(c) for c in camera_ids]

        date_from_raw = data.get("date_from") or data.get("date")
        date_to_raw = data.get("date_to") or data.get("date")
        if not date_from_raw or not date_to_raw:
            return error("date_from/date_to (ou date) são obrigatórios", 400)
        try:
            date_from = date.fromisoformat(str(date_from_raw))
            date_to = date.fromisoformat(str(date_to_raw))
        except ValueError:
            return error(
                "date_from/date_to devem estar em formato ISO (YYYY-MM-DD)", 400,
            )
        if date_from > date_to:
            return error("date_from posterior a date_to", 400)

        validation_only = bool(data.get("validation_only", False))

        threshold = data.get("threshold", _DEFAULT_SIMILARITY_THRESHOLD)
        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            return error("threshold deve ser numérico", 400)
        if not (0.0 < threshold <= 1.0):
            return error("threshold deve estar entre 0 e 1", 400)

        max_results_raw = data.get("max_results")
        max_results: int | None = None
        if max_results_raw is not None:
            if isinstance(max_results_raw, bool):
                return error(
                    f"max_results deve ser um inteiro entre {_MAX_RESULTS_MIN} "
                    f"e {_MAX_RESULTS_MAX}", 400,
                )
            try:
                max_results = int(max_results_raw)
            except (TypeError, ValueError):
                return error(
                    f"max_results deve ser um inteiro entre {_MAX_RESULTS_MIN} "
                    f"e {_MAX_RESULTS_MAX}", 400,
                )
            if not (_MAX_RESULTS_MIN <= max_results <= _MAX_RESULTS_MAX):
                return error(
                    f"max_results deve ser um inteiro entre {_MAX_RESULTS_MIN} "
                    f"e {_MAX_RESULTS_MAX}", 400,
                )

        # Posse de câmera por tenant — cross-tenant → 404 (C-01), ANTES de
        # sequer materializar o pool (nunca vaza existência de câmera de
        # outro tenant via a mensagem de erro do guard).
        camera_repo = _get_camera_repo()
        for camera_id in camera_ids:
            if camera_repo.get_by_id_and_tenant(camera_id, str(tenant_id)) is None:
                return error("Câmera não encontrada", 404)

        frame_repo = _get_frame_repo()
        candidate_frames = frame_repo.list_for_propagation_pool(
            tenant_id, camera_ids, date_from, date_to,
        )
        try:
            pool_frame_ids, pool_hash = materialize_pool(
                candidate_frames,
                tenant_id=str(tenant_id),
                camera_ids=camera_ids,
                date_from=date_from,
                date_to=date_to,
                limit=_VALIDATION_ONLY_POOL_LIMIT if validation_only else None,
            )
        except PoolGuardError as exc:
            return error(str(exc), 400)

        seed_frame_ids_raw = data.get("seed_frame_ids")
        if seed_frame_ids_raw is not None:
            if not isinstance(seed_frame_ids_raw, list) or not seed_frame_ids_raw:
                return error("seed_frame_ids, se informado, não pode ser vazio", 400)
            seed_frame_ids = [str(fid) for fid in seed_frame_ids_raw]
            pool_set = set(pool_frame_ids)
            outside = sorted(fid for fid in seed_frame_ids if fid not in pool_set)
            if outside:
                return error(
                    f"seed_frame_ids fora do pool do job: {outside}", 400,
                )
        else:
            annotation_repo = _get_annotation_repo()
            manual_rows = annotation_repo.get_manual_annotations_for_frames(
                pool_frame_ids
            )
            seed_frame_ids = sorted({str(r["frame_id"]) for r in manual_rows})

        if not seed_frame_ids:
            return error(
                "nenhuma semente disponível — anote ao menos um frame do pool "
                "antes de propagar, ou informe seed_frame_ids explícito", 400,
            )

        pool_criteria = {
            "camera_ids": camera_ids,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "validation_only": validation_only,
            "threshold": threshold,
        }
        if max_results is not None:
            pool_criteria["max_results"] = max_results

        repo = _get_propagation_repo()
        job = repo.create_job(
            tenant_id=tenant_id,
            pool_criteria=pool_criteria,
            pool_frame_ids=pool_frame_ids,
            pool_hash=pool_hash,
            seed_frame_ids=seed_frame_ids,
            created_by=user_id,
        )
        _strip_callback_token(job)

        from app.infrastructure.queue.tasks.propagation import (  # noqa: PLC0415
            dispatch_propagation,
        )
        dispatch_propagation.delay(job_id=str(job["id"]))

        return success(job, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_propagation_job_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# --------------------------------------------------------------------------
# GET /api/v1/training/propagation/jobs/<id>
# --------------------------------------------------------------------------

def get_propagation_job_handler(job_id: str):
    """Status de um job de propagação semeada (cross-tenant → 404, C-01)."""
    try:
        tenant_id = get_tenant_id()
        repo = _get_propagation_repo()
        job = repo.get_by_id_and_tenant(job_id, tenant_id)
        if job is None:
            return error("Job de propagação não encontrado", 404)
        _strip_callback_token(job)
        return success(job)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_propagation_job_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# --------------------------------------------------------------------------
# GET /api/v1/training/propagation/jobs
# --------------------------------------------------------------------------

def list_propagation_jobs_handler():
    """Lista jobs de propagação semeada do tenant do contexto."""
    try:
        tenant_id = get_tenant_id()
        repo = _get_propagation_repo()
        jobs = repo.list_for_tenant(tenant_id)
        for job in jobs:
            _strip_callback_token(job)
        return success(jobs)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_propagation_jobs_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# --------------------------------------------------------------------------
# POST /api/v1/training/propagation/jobs/<id>/callback (interno GPU→API)
# --------------------------------------------------------------------------

_ALLOWED_CALLBACK_STATUS = frozenset({"running", "completed", "failed"})


def _validate_completed_payload(
    proposals: Any, pool_frame_ids: list[str],
) -> "tuple[dict[str, list[dict]] | None, str | None]":
    """Valida o payload final ANTES de gravar qualquer coisa — "nunca
    sucesso silencioso": qualquer entrada malformada (bbox fora de [0,1],
    classe vazia, frame_id fora do pool) rejeita o payload INTEIRO (400);
    o job permanece 'running', NUNCA marcado 'completed' com dado
    parcial/adulterado. Retorna (payload normalizado, None) ou
    (None, mensagem_de_erro)."""
    if not isinstance(proposals, dict):
        return None, "proposals deve ser um objeto {frame_id: [propostas]}"

    pool_set = set(pool_frame_ids)
    validated: "dict[str, list[dict]]" = {}

    for frame_id, frame_proposals in proposals.items():
        frame_id = str(frame_id)
        if frame_id not in pool_set:
            return None, f"frame_id fora do pool do job: {frame_id!r}"
        if not isinstance(frame_proposals, list):
            return None, f"propostas de {frame_id!r} devem ser uma lista"

        checked: "list[dict]" = []
        for item in frame_proposals:
            if not isinstance(item, dict):
                return None, f"proposta inválida em {frame_id!r}: não é objeto"

            bbox = item.get("bbox")
            if (
                not isinstance(bbox, list)
                or len(bbox) != 4
                or not all(
                    isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in bbox
                )
                or not all(0.0 <= float(v) <= 1.0 for v in bbox)
            ):
                return None, f"bbox inválido em {frame_id!r}: {bbox!r}"

            class_name = item.get("class")
            if not isinstance(class_name, str) or not class_name.strip():
                return None, f"class inválida em {frame_id!r}: {class_name!r}"

            confidence = item.get("confidence")
            if (
                not isinstance(confidence, (int, float))
                or isinstance(confidence, bool)
                or not (0.0 <= float(confidence) <= 1.0)
            ):
                return None, f"confidence inválida em {frame_id!r}: {confidence!r}"

            checked.append({
                "bbox": [float(v) for v in bbox],
                "class": class_name.strip(),
                "confidence": float(confidence),
            })
        validated[frame_id] = checked

    return validated, None


def propagation_callback_handler(job_id: str):
    """Progresso/resultado da propagação remota (RunPod) — SEM JWT.

    Auth: header X-Callback-Token comparado em tempo constante
    (hmac.compare_digest) com propagation_jobs.callback_token (mesmo
    padrão de job_handlers.py::training_progress_callback_handler). Rate
    limit na rota (routes.py).
    """
    try:
        from app.infrastructure.queue.tasks.propagation import (  # noqa: PLC0415
            _as_str_list,
        )

        token = request.headers.get("X-Callback-Token", "")
        if not token:
            return error("Token de callback ausente", 401)

        repo = _get_propagation_repo()
        job = repo.get_by_id(job_id)
        stored = str((job or {}).get("callback_token") or "")
        if not job or not stored or not hmac.compare_digest(stored, token):
            logger.warning("propagation_callback_token_invalido: job=%s", job_id)
            return error("Token de callback inválido", 403)

        data = request.get_json(silent=True) or {}
        status = data.get("status")
        if status not in _ALLOWED_CALLBACK_STATUS:
            return error(
                f"status inválido: {status!r} "
                f"(permitidos: {sorted(_ALLOWED_CALLBACK_STATUS)})", 400,
            )

        if status == "failed":
            error_message = str(
                data.get("error_message") or "propagação falhou (sem detalhe)"
            )[:_ERROR_MAX_LEN]
            repo.apply_callback_failed(job_id, error_message)
            return success({"job_id": job_id, "status": "failed"})

        if status == "running":
            metrics = data.get("metrics")
            if metrics is not None and not isinstance(metrics, dict):
                return error("metrics deve ser um objeto", 400)
            repo.merge_metrics(job_id, metrics or {})
            return success({"job_id": job_id, "status": "running"})

        # status == "completed"
        pool_frame_ids = _as_str_list(job.get("pool_frame_ids"))
        validated, validation_error = _validate_completed_payload(
            data.get("proposals"), pool_frame_ids,
        )
        if validated is None:
            return error(validation_error or "payload de propostas inválido", 400)

        tenant_id = str(job["tenant_id"])
        frame_repo = _get_frame_repo()
        proposals_count = 0
        for frame_id, frame_proposals in validated.items():
            frame_repo.apply_propagation_proposals(frame_id, tenant_id, frame_proposals)
            proposals_count += len(frame_proposals)

        metrics = data.get("metrics")
        if not isinstance(metrics, dict):
            metrics = {}
        repo.apply_callback_completed(job_id, proposals_count, metrics)

        return success({
            "job_id": job_id, "status": "completed", "proposals_count": proposals_count,
        })
    except Exception as exc:
        logger.error("propagation_callback_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
