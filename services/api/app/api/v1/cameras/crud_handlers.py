"""
Recognition — CRUD handlers for camera routes.

Handlers: list_cameras, create_camera, get_camera, update_camera, delete_camera.
"""
import json as _json
import logging
from uuid import UUID

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error

from .helpers import _get_camera_service, _is_admin, _get_redis

logger = logging.getLogger(__name__)


@jwt_required()
def list_cameras():  # type: ignore[no-untyped-def]
    """---
    tags: [cameras]
    summary: Listar câmeras do usuário
    security: [{Bearer: []}]
    responses: {200: {description: Lista de câmeras}}
    """
    try:
        user_id = get_current_user_id()
        service = _get_camera_service()
        cameras = service.list_cameras(user_id, _is_admin(user_id))
        try:
            r = _get_redis()
            gw_raw = r.get("service:gateway:health")
            inf_raw = r.get("service:inference:health")
            gateway_status = _json.loads(gw_raw) if gw_raw else {"status": "offline"}
            inference_status = _json.loads(inf_raw) if inf_raw else {"status": "offline"}
        except Exception:
            gateway_status = {"status": "unavailable"}
            inference_status = {"status": "unavailable"}
        return success({
            "cameras": cameras,
            "gateway_status": gateway_status,
            "inference_status": inference_status,
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_cameras_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def create_camera():  # type: ignore[no-untyped-def]
    """---
    tags: [cameras]
    summary: Criar nova câmera IP
    security: [{Bearer: []}]
    parameters:
      - {in: body, name: body, required: true, schema: {required: [name, host],
         properties: {name: {type: string}, host: {type: string},
         manufacturer: {type: string}, port: {type: integer},
         username: {type: string}, password: {type: string}}}}
    responses: {201: {description: Câmera criada}, 400: {description: Dados inválidos}}
    """
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        service = _get_camera_service()
        camera = service.create_camera(user_id, data)
        return success(camera, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_camera_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def get_camera(camera_id: str):  # type: ignore[no-untyped-def]
    """---
    tags: [cameras]
    summary: Obter câmera por ID
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: camera_id, type: string, required: true}
    responses: {200: {description: Dados da câmera (sem senha)},
                403: {description: Sem permissão}, 404: {description: Câmera não encontrada}}
    """
    try:
        user_id = get_current_user_id()
        service = _get_camera_service()
        camera = service.get_camera(UUID(camera_id))
        if camera.get("user_id") and str(camera["user_id"]) != str(user_id) and not _is_admin(user_id):
            return error("Sem permissão", 403)
        return success(camera)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_camera_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def update_camera(camera_id: str):  # type: ignore[no-untyped-def]
    """---
    tags: [cameras]
    summary: Atualizar câmera
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: camera_id, type: string, required: true}
      - {in: body, name: body, schema: {properties: {name: {type: string},
         host: {type: string}, port: {type: integer}, username: {type: string},
         password: {type: string}, manufacturer: {type: string},
         location: {type: string}, rtsp_url_override: {type: string}}}}
    responses: {200: {description: Câmera atualizada},
                403: {description: Sem permissão}, 404: {description: Câmera não encontrada}}
    """
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        service = _get_camera_service()
        camera = service.update_camera(UUID(camera_id), user_id, data, _is_admin(user_id))
        return success(camera)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("update_camera_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def delete_camera(camera_id: str):  # type: ignore[no-untyped-def]
    """---
    tags: [cameras]
    summary: Deletar câmera
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: camera_id, type: string, required: true}
    responses: {200: {description: Câmera deletada},
                403: {description: Sem permissão}, 404: {description: Câmera não encontrada}}
    """
    try:
        user_id = get_current_user_id()
        service = _get_camera_service()
        service.delete_camera(UUID(camera_id), user_id, _is_admin(user_id))
        return success({"deleted": True})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("delete_camera_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
