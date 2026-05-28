"""
Recognition — Model endpoint handlers for camera routes.

Handlers: get_camera_model, set_camera_model.
"""
import json as _json
import logging

from flask import request
from flask_jwt_extended import jwt_required

from app.core.responses import success, error

from .helpers import _get_redis

logger = logging.getLogger(__name__)


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
