"""
EPI Monitor V2 — Training Job, Model, and Alert handlers.

Handles: create_job, list_jobs, get_job_status, list_models,
         activate_model, get_alerts, acknowledge_alert

Dispatch flow:
  create_job → inserts to training_jobs → fires _dispatch_to_training_service()
               (fire-and-forget thread, does not block response)
  activate_model → updates trained_models → publishes model:reload to Redis
                   (inference-service subscribes and hot-reloads)
"""
import json
import logging
import os
import threading

import requests as http_requests
from flask import request

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success

from .helpers import get_inference_service, get_training_service

logger = logging.getLogger(__name__)

_TRAINING_SERVICE_URL = os.environ.get(
    "TRAINING_SERVICE_INTERNAL_URL",
    "http://training-service.railway.internal:8080",
)
_REDIS_URL = os.environ.get("REDIS_URL", "")


def _build_dataset_url(user_id: str, job_id: str) -> str:
    """Constrói URL do dataset no R2 (convenção: exportado antes do treino)."""
    endpoint = os.environ.get("R2_ENDPOINT", "").rstrip("/")
    bucket = os.environ.get("R2_BUCKET", "epi-monitor")
    return f"{endpoint}/{bucket}/datasets/{user_id}/{job_id}/dataset.zip"


def _dispatch_to_training_service(job_id: str, user_id: str) -> None:
    """Dispara job para training-service via HTTP. Roda em thread separada.

    AI_NOTE: US-029 — fallback para Celery quando HTTP falha, evitando
    que jobs fiquem presos em status 'pending'.
    """
    dataset_url = _build_dataset_url(user_id, job_id)
    http_ok = False
    try:
        resp = http_requests.post(
            f"{_TRAINING_SERVICE_URL}/jobs",
            json={"job_id": job_id, "dataset_url": dataset_url},
            timeout=5,
        )
        if resp.status_code not in (200, 201):
            logger.warning(
                "training_dispatch_non2xx: job=%s status=%d body=%s",
                job_id, resp.status_code, resp.text[:200],
            )
        else:
            logger.info("training_dispatch_ok: job=%s", job_id)
            http_ok = True
    except Exception as exc:
        logger.warning(
            "training_dispatch_http_failed: job=%s err=%s — tentando Celery fallback",
            job_id, exc,
        )

    if not http_ok:
        _dispatch_celery_fallback(job_id)


def _dispatch_celery_fallback(job_id: str) -> None:
    """Fallback: enfileira dispatch_training via Celery quando HTTP falhou.

    AI_NOTE: US-029 — garante que job sai de 'pending' mesmo quando
    training-service.railway.internal está indisponível.
    """
    try:
        from app.infrastructure.queue.tasks.training import dispatch_training
        dispatch_training.delay(
            job_id=job_id,
            dataset_version_id=job_id,  # usa job_id como version placeholder
        )
        logger.info("training_dispatch_celery_fallback: job=%s", job_id)
    except Exception as exc:
        logger.error(
            "training_dispatch_both_failed: job=%s err=%s — job permanece pending",
            job_id, exc,
        )


def _publish_model_reload(model_path: str) -> None:
    """Publica model:reload no Redis para inference-service hot-reload."""
    if not _REDIS_URL or not model_path:
        return
    try:
        import redis as _redis
        r = _redis.from_url(_REDIS_URL, socket_timeout=3)
        r.publish("model:reload", json.dumps({"model_path": model_path}))
        logger.info("model_reload_published: path=%s", model_path)
    except Exception as exc:
        logger.warning("model_reload_publish_failed: %s", exc)


def create_job_handler():
    """Cria job de treinamento.
    ---
    tags:
      - training
    summary: Criar job de treinamento YOLOv8
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          properties:
            preset: {type: string, enum: [fast, balanced, quality], default: balanced}
            model_size: {type: string, example: yolov8n}
            total_epochs: {type: integer, example: 100}
    responses:
      201:
        description: Job criado
    """
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        service = get_training_service()
        job = service.create_job(
            user_id=user_id,
            preset=data.get("preset", "balanced"),
            model_size=data.get("model_size", "yolov8n"),
            total_epochs=data.get("total_epochs", 100),
        )
        # Dispara training-service em background — não bloqueia resposta
        threading.Thread(
            target=_dispatch_to_training_service,
            args=(job["id"], str(user_id)),
            daemon=True,
            name=f"dispatch-{job['id'][:8]}",
        ).start()
        return success(job, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_job_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def list_jobs_handler():
    """Lista jobs de treinamento do usuário."""
    try:
        user_id = get_current_user_id()
        jobs = get_training_service().list_jobs(user_id)
        return success(jobs)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_jobs_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_job_status_handler(job_id: str):
    """Status de um job de treinamento."""
    try:
        from uuid import UUID

        job = get_training_service().get_job(UUID(job_id))
        return success(job)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_job_status_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def list_models_handler():
    """Lista modelos treinados do usuário."""
    try:
        user_id = get_current_user_id()
        models = get_training_service().list_models(user_id)
        return success(models)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_models_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def activate_model_handler(model_id: str):
    """Ativa modelo para inferência."""
    try:
        from uuid import UUID

        user_id = get_current_user_id()
        model = get_training_service().activate_model(UUID(model_id), user_id)
        # Notifica inference-service para hot-reload
        _publish_model_reload(model.get("model_path", ""))
        return success(model)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("activate_model_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_alerts_handler(camera_id: str):
    """Lista alertas de uma câmera."""
    try:
        from uuid import UUID

        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        alerts = get_inference_service().get_alerts(UUID(camera_id), limit, offset)
        return success(alerts)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_alerts_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def acknowledge_alert_handler(alert_id: str):
    """Marca alerta como reconhecido."""
    try:
        from uuid import UUID

        result = get_inference_service().acknowledge_alert(UUID(alert_id))
        return success(result)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("acknowledge_alert_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
