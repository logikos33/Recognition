"""
EPI Monitor V2 — Video and Frame handlers.

Handles: list_videos, create_video, get_video_frames, get_frame_image
"""
import logging
import os

from flask import request, send_file
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError, NotFoundError
from app.core.responses import success, error
from app.infrastructure.database.repositories.frame_repository import FrameRepository

from .helpers import _get_pool, get_video_service

logger = logging.getLogger(__name__)


def list_videos_handler():
    """Lista vídeos de treinamento do usuário.
    ---
    tags:
      - training
    summary: Listar vídeos de treinamento
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de vídeos
    """
    try:
        user_id = get_current_user_id()
        videos = get_video_service().list_videos(user_id)
        return success(videos)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_videos_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def create_video_handler():
    """Registra upload de vídeo."""
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        video = get_video_service().create_video(
            user_id=user_id,
            filename=data.get("filename", ""),
            original_filename=data.get("original_filename"),
            file_size=data.get("file_size"),
        )
        return success(video, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_video_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_video_frames_handler(video_id: str):
    """Lista frames de um vídeo. Usado pelo AnnotationInterface.jsx.
    ---
    tags:
      - training
    summary: Listar frames aprovados de um vídeo
    security:
      - Bearer: []
    parameters:
      - in: path
        name: video_id
        type: string
        required: true
    responses:
      200:
        description: Lista de frames com status de anotação
      404:
        description: Vídeo não encontrado
    """
    try:
        from uuid import UUID

        frames = get_video_service().get_video_frames(UUID(video_id))
        return success(frames)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_frames_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_frame_image_handler(frame_id: str):
    """Serve imagem de um frame. Redireciona para R2 presigned URL quando disponível."""
    from uuid import UUID
    from flask import redirect
    from app.infrastructure.storage.local_storage import get_storage
    from app.infrastructure.storage.r2_storage import R2Storage

    try:
        pool = _get_pool()
        frame_repo = FrameRepository(pool)
        frame = frame_repo.get_by_id(UUID(frame_id))
        if not frame:
            raise NotFoundError("Frame", frame_id)

        storage = get_storage()

        # R2: gerar presigned URL e redirecionar (307 Temporary Redirect)
        if isinstance(storage, R2Storage):
            url = storage.generate_presigned_download_url(frame["filename"], ttl=3600, response_content_type="image/jpeg")
            return redirect(url, code=307)

        # LocalStorage: servir arquivo direto (fallback dev)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )))
        storage_dir = os.path.realpath(os.path.join(base_dir, "storage"))
        frame_path = os.path.realpath(os.path.join(storage_dir, frame["filename"]))

        # SEC: path traversal guard
        if not frame_path.startswith(storage_dir + os.sep):
            raise NotFoundError("Arquivo de frame", "path traversal blocked")

        if not os.path.exists(frame_path):
            raise NotFoundError("Arquivo de frame", frame["filename"])

        return send_file(frame_path, mimetype="image/jpeg")

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_frame_image_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
