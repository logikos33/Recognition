"""
Recognition — Model endpoint handlers for camera routes.

Handlers:
  - get_camera_model / set_camera_model: ponteiro de modelo no Redis (legacy).
  - get_camera_models / put_camera_models: atribuição persistente de modelo
    por módulo (model_epi_id / model_quality_id / model_counting_id — Task 045).
"""
import json as _json
import logging
from uuid import UUID

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.exceptions import EpiMonitorError, NotFoundError, ValidationError
from app.core.responses import success, error
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.camera_repository import CameraRepository
from app.infrastructure.database.repositories.training_repository import (
    TrainingRepository,
)

from .helpers import _get_redis

logger = logging.getLogger(__name__)


def _get_camera_repo() -> CameraRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return CameraRepository(pool)


def _get_training_repo() -> TrainingRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return TrainingRepository(pool)


@jwt_required()
def get_camera_model(camera_id: str):  # type: ignore[no-untyped-def]
    """Retorna modelo YOLO ativo da câmera."""
    try:
        r = _get_redis()
        model_key = r.get(f"camera:model:{camera_id}")
        return success({
            "camera_id": camera_id,
            "model_key": model_key,
        })
    except Exception as exc:
        logger.error("get_camera_model_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def set_camera_model(camera_id: str):  # type: ignore[no-untyped-def]
    """Define qual modelo YOLO a câmera usa."""
    try:
        data = request.get_json() or {}
        model_key = data.get("model_key", "")
        r = _get_redis()
        if model_key:
            r.set(f"camera:model:{camera_id}", model_key)
            r.publish(f"camera:model_change:{camera_id}", _json.dumps({
                "camera_id": camera_id,
                "model_key": model_key,
            }))
            logger.info("camera_model_set: camera=%s model=%s", camera_id, model_key)
        else:
            r.delete(f"camera:model:{camera_id}")
        return success({"camera_id": camera_id, "model_key": model_key or None})
    except Exception as exc:
        logger.error("set_camera_model_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# ---------------------------------------------------------------------------
# Task 045 — atribuição persistente de modelo por câmera/módulo
# ---------------------------------------------------------------------------

@jwt_required()
def get_camera_models(camera_id: str):  # type: ignore[no-untyped-def]
    """
    GET /api/cameras/<id>/models

    Retorna a atribuição de modelo por módulo da câmera (filtra tenant do JWT).
    """
    try:
        tenant_id = get_tenant_id()
        row = _get_camera_repo().get_model_assignments(camera_id, tenant_id)
        if not row:
            raise NotFoundError("Câmera", camera_id)

        return success({
            "camera_id": camera_id,
            "models": {
                "epi": str(row["model_epi_id"]) if row.get("model_epi_id") else None,
                "quality": str(row["model_quality_id"]) if row.get("model_quality_id") else None,
                "counting": str(row["model_counting_id"]) if row.get("model_counting_id") else None,
            },
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_camera_models_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def put_camera_models(camera_id: str):  # type: ignore[no-untyped-def]
    """
    PUT /api/cameras/<id>/models

    Body: {"module": "epi"|"quality"|"counting", "model_id": "<uuid>" | null}

    model_id=null remove a atribuição. Valida que o modelo existe e pertence
    ao tenant do JWT antes de gravar. Notifica o worker via Redis (best-effort).
    """
    try:
        tenant_id = get_tenant_id()
        data = request.get_json() or {}
        module = (data.get("module") or "").strip()
        model_id = data.get("model_id")

        if module not in CameraRepository.MODEL_COLUMNS:
            raise ValidationError(
                f"Módulo inválido. Use: {sorted(CameraRepository.MODEL_COLUMNS)}"
            )

        camera_repo = _get_camera_repo()
        if not camera_repo.get_model_assignments(camera_id, tenant_id):
            raise NotFoundError("Câmera", camera_id)

        if model_id:
            try:
                model_uuid = UUID(str(model_id))
            except ValueError as exc:
                raise ValidationError("model_id deve ser um UUID válido") from exc
            model = _get_training_repo().get_model_for_tenant(model_uuid, tenant_id)
            if not model:
                raise NotFoundError("Modelo", str(model_id))

        row = camera_repo.set_model_assignment(
            camera_id, tenant_id, module, str(model_id) if model_id else None
        )

        _notify_model_assignment(camera_id, module, model_id)
        logger.info(
            "camera_model_assigned: camera=%s module=%s model=%s",
            camera_id, module, model_id,
        )
        return success({
            "camera_id": camera_id,
            "models": {
                "epi": str(row["model_epi_id"]) if row and row.get("model_epi_id") else None,
                "quality": str(row["model_quality_id"]) if row and row.get("model_quality_id") else None,
                "counting": str(row["model_counting_id"]) if row and row.get("model_counting_id") else None,
            },
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("put_camera_models_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def _notify_model_assignment(camera_id: str, module: str, model_id) -> None:  # type: ignore[no-untyped-def]
    """Publica evento Redis para o worker recarregar o modelo. Falha silenciosa."""
    try:
        r = _get_redis()
        r.publish(f"camera:model_change:{camera_id}", _json.dumps({
            "camera_id": camera_id,
            "module": module,
            "model_id": str(model_id) if model_id else None,
        }))
        r.close()
    except Exception as exc:
        logger.warning("notify_model_assignment_failed: camera=%s err=%s", camera_id, exc)
