"""
EPI Monitor V2 — Camera Routes.

CRUD de câmeras IP + controle de stream.
Senhas SEMPRE criptografadas — NUNCA retornadas na API.
"""
import logging
import os

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error
from app.domain.services.camera_service import CameraService
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.camera_repository import CameraRepository
from app.infrastructure.database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

cameras_bp = Blueprint("cameras", __name__, url_prefix="/api/cameras")


def _get_camera_service() -> CameraService:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    fernet_key = os.environ.get("CAMERA_SECRET_KEY", "")
    return CameraService(CameraRepository(pool), fernet_key)


def _is_admin(user_id) -> bool:  # type: ignore[no-untyped-def]
    pool = DatabasePool.get_instance()
    if pool is None:
        return False
    repo = UserRepository(pool)
    user = repo.get_by_id(user_id)
    return user is not None and user.get("role") == "admin"


@cameras_bp.route("", methods=["GET"])
@jwt_required()
def list_cameras():  # type: ignore[no-untyped-def]
    """Lista câmeras do usuário (admin vê todas)."""
    try:
        user_id = get_current_user_id()
        service = _get_camera_service()
        cameras = service.list_cameras(user_id, _is_admin(user_id))
        return success(cameras)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_cameras_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@cameras_bp.route("", methods=["POST"])
@jwt_required()
def create_camera():  # type: ignore[no-untyped-def]
    """Cria nova câmera IP."""
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


@cameras_bp.route("/<camera_id>", methods=["GET"])
@jwt_required()
def get_camera(camera_id: str):  # type: ignore[no-untyped-def]
    """Busca câmera por ID (sem senha)."""
    try:
        from uuid import UUID
        service = _get_camera_service()
        camera = service.get_camera(UUID(camera_id))
        return success(camera)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_camera_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@cameras_bp.route("/<camera_id>", methods=["DELETE"])
@jwt_required()
def delete_camera(camera_id: str):  # type: ignore[no-untyped-def]
    """Deleta câmera."""
    try:
        from uuid import UUID
        user_id = get_current_user_id()
        service = _get_camera_service()
        service.delete_camera(UUID(camera_id), user_id, _is_admin(user_id))
        return success({"deleted": True})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("delete_camera_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@cameras_bp.route("/<camera_id>/stream/start", methods=["POST"])
@jwt_required()
def start_stream(camera_id: str):  # type: ignore[no-untyped-def]
    """Inicia stream HLS + inferência YOLO para uma câmera."""
    try:
        from uuid import UUID
        user_id = get_current_user_id()
        service = _get_camera_service()
        rtsp_url = service.build_rtsp_url(
            UUID(camera_id), user_id, _is_admin(user_id)
        )
        # TODO: Fase 5 — enfileirar inference_loop e start_hls_stream
        return success({
            "camera_id": camera_id,
            "rtsp_url_validated": True,
            "status": "starting",
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("start_stream_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@cameras_bp.route("/<camera_id>/stream/stop", methods=["POST"])
@jwt_required()
def stop_stream(camera_id: str):  # type: ignore[no-untyped-def]
    """Para stream de uma câmera."""
    # TODO: Fase 5 — parar via Redis camera_control
    return success({"camera_id": camera_id, "status": "stopped"})
