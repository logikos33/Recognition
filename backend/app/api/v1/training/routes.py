"""
EPI Monitor V2 — Training Routes.

Routes compatíveis com AnnotationInterface.jsx:
  GET  /api/training/videos/<video_id>/frames
  GET  /api/training/frames/<frame_id>/annotations
  POST /api/training/frames/<frame_id>/annotations
  GET  /api/training/frames/<frame_id>/image
  GET  /api/classes
  POST /api/classes
  GET  /api/training/videos  (lista vídeos do usuário)
  POST /api/training/videos  (upload de vídeo)
"""
import logging
import os

from flask import Blueprint, request, send_file
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError, NotFoundError
from app.core.responses import success, error
from app.domain.services.annotation_service import AnnotationService
from app.domain.services.video_service import VideoService
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.database.repositories.video_repository import VideoRepository

logger = logging.getLogger(__name__)

training_bp = Blueprint("training", __name__)


def _get_pool() -> DatabasePool:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def _video_service() -> VideoService:
    pool = _get_pool()
    return VideoService(VideoRepository(pool), FrameRepository(pool))


def _annotation_service() -> AnnotationService:
    pool = _get_pool()
    return AnnotationService(AnnotationRepository(pool), FrameRepository(pool))


# --- Videos ---


@training_bp.route("/api/training/videos", methods=["GET"])
@jwt_required()
def list_videos():  # type: ignore[no-untyped-def]
    """Lista vídeos de treinamento do usuário."""
    try:
        user_id = get_current_user_id()
        videos = _video_service().list_videos(user_id)
        return success(videos)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_videos_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@training_bp.route("/api/training/videos", methods=["POST"])
@jwt_required()
def create_video():  # type: ignore[no-untyped-def]
    """Registra upload de vídeo."""
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        video = _video_service().create_video(
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


# --- Frames (AnnotationInterface.jsx contract) ---


@training_bp.route(
    "/api/training/videos/<video_id>/frames", methods=["GET"]
)
@jwt_required()
def get_video_frames(video_id: str):  # type: ignore[no-untyped-def]
    """Lista frames de um vídeo. Usado pelo AnnotationInterface.jsx."""
    try:
        from uuid import UUID

        frames = _video_service().get_video_frames(UUID(video_id))
        return success(frames)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_frames_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@training_bp.route(
    "/api/training/frames/<frame_id>/image", methods=["GET"]
)
@jwt_required()
def get_frame_image(frame_id: str):  # type: ignore[no-untyped-def]
    """Serve imagem de um frame. Usado pelo AnnotationInterface.jsx."""
    try:
        from uuid import UUID

        pool = _get_pool()
        frame_repo = FrameRepository(pool)
        frame = frame_repo.get_by_id(UUID(frame_id))
        if not frame:
            raise NotFoundError("Frame", frame_id)

        # Buscar do filesystem local (storage/frames/)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )))
        frame_path = os.path.join(base_dir, "storage", "frames", frame["filename"])

        if not os.path.exists(frame_path):
            # Fallback: tentar caminho do projeto raiz
            project_root = os.path.dirname(base_dir)
            frame_path = os.path.join(
                project_root, "storage", "frames", frame["filename"]
            )

        if not os.path.exists(frame_path):
            raise NotFoundError("Arquivo de frame", frame["filename"])

        return send_file(frame_path, mimetype="image/jpeg")
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_frame_image_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# --- Annotations (AnnotationInterface.jsx contract) ---


@training_bp.route(
    "/api/training/frames/<frame_id>/annotations", methods=["GET"]
)
@jwt_required()
def get_annotations(frame_id: str):  # type: ignore[no-untyped-def]
    """Lista anotações de um frame."""
    try:
        from uuid import UUID

        annotations = _annotation_service().get_frame_annotations(UUID(frame_id))
        return success(annotations)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_annotations_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@training_bp.route(
    "/api/training/frames/<frame_id>/annotations", methods=["POST"]
)
@jwt_required()
def save_annotations(frame_id: str):  # type: ignore[no-untyped-def]
    """Salva anotações de um frame. Formato AnnotationInterface.jsx."""
    try:
        from uuid import UUID

        data = request.get_json() or {}
        annotations = data.get("annotations", [])
        count = _annotation_service().save_annotations(
            UUID(frame_id), annotations
        )
        return success({"saved": count})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("save_annotations_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# --- Classes (AnnotationInterface.jsx contract) ---


@training_bp.route("/api/classes", methods=["GET"])
@jwt_required()
def get_classes():  # type: ignore[no-untyped-def]
    """Lista classes YOLO do usuário."""
    try:
        user_id = get_current_user_id()
        classes = _annotation_service().get_classes(user_id)
        return success(classes)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_classes_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@training_bp.route("/api/classes", methods=["POST"])
@jwt_required()
def create_class():  # type: ignore[no-untyped-def]
    """Cria classe YOLO."""
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        cls = _annotation_service().create_class(
            user_id=user_id,
            name=data.get("name", ""),
            color=data.get("color", "#3b82f6"),
        )
        return success(cls, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_class_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
