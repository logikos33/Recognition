"""
Recognition — Propagation Job handlers (propagação semeada, RunPod).

Rotas (routes.py):
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
