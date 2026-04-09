"""
EPI Monitor V2 — Training Job, Model, and Alert handlers.

Handles: create_job, list_jobs, get_job_status, list_models,
         activate_model, get_alerts, acknowledge_alert
"""
import logging

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error

from .helpers import get_training_service, get_inference_service

logger = logging.getLogger(__name__)


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
