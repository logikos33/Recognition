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
from app.domain.services.training_service import TrainingService
from app.domain.services.inference_service import InferenceService
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)
from app.infrastructure.database.repositories.alert_repository import AlertRepository
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.database.repositories.training_repository import TrainingRepository
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
            url = storage.generate_presigned_download_url(frame["filename"], ttl=3600)
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


# --- Training Jobs ---


def _training_service() -> TrainingService:
    pool = _get_pool()
    return TrainingService(TrainingRepository(pool))


def _inference_service() -> InferenceService:
    pool = _get_pool()
    return InferenceService(AlertRepository(pool))


@training_bp.route("/api/training/jobs", methods=["POST"])
@jwt_required()
def create_job():  # type: ignore[no-untyped-def]
    """Cria job de treinamento."""
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        service = _training_service()
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


@training_bp.route("/api/training/jobs", methods=["GET"])
@jwt_required()
def list_jobs():  # type: ignore[no-untyped-def]
    """Lista jobs de treinamento do usuário."""
    try:
        user_id = get_current_user_id()
        jobs = _training_service().list_jobs(user_id)
        return success(jobs)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_jobs_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@training_bp.route("/api/training/jobs/<job_id>/status", methods=["GET"])
@jwt_required()
def get_job_status(job_id: str):  # type: ignore[no-untyped-def]
    """Status de um job de treinamento."""
    try:
        from uuid import UUID
        job = _training_service().get_job(UUID(job_id))
        return success(job)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_job_status_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@training_bp.route("/api/training/models", methods=["GET"])
@jwt_required()
def list_models():  # type: ignore[no-untyped-def]
    """Lista modelos treinados do usuário."""
    try:
        user_id = get_current_user_id()
        models = _training_service().list_models(user_id)
        return success(models)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_models_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@training_bp.route("/api/training/models/<model_id>/activate", methods=["POST"])
@jwt_required()
def activate_model(model_id: str):  # type: ignore[no-untyped-def]
    """Ativa modelo para inferência."""
    try:
        from uuid import UUID
        user_id = get_current_user_id()
        model = _training_service().activate_model(UUID(model_id), user_id)
        return success(model)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("activate_model_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


# --- Alerts ---


@training_bp.route("/api/cameras/<camera_id>/alerts", methods=["GET"])
@jwt_required()
def get_alerts(camera_id: str):  # type: ignore[no-untyped-def]
    """Lista alertas de uma câmera."""
    try:
        from uuid import UUID
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        alerts = _inference_service().get_alerts(UUID(camera_id), limit, offset)
        return success(alerts)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_alerts_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@training_bp.route("/api/alerts/<alert_id>/acknowledge", methods=["POST"])
@jwt_required()
def acknowledge_alert(alert_id: str):  # type: ignore[no-untyped-def]
    """Marca alerta como reconhecido."""
    try:
        from uuid import UUID
        result = _inference_service().acknowledge_alert(UUID(alert_id))
        return success(result)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("acknowledge_alert_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
