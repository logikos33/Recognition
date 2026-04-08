"""
EPI Monitor V2 — Video Upload Routes.

POST /api/v1/videos/upload        — Upload video file directly
POST /api/v1/videos/upload-url    — Get presigned upload URL (R2)
POST /api/v1/videos/<id>/extract  — Trigger frame extraction
GET  /api/v1/videos/<id>/status   — Get video processing status
"""
import logging
import os
from uuid import UUID, uuid4
from werkzeug.utils import secure_filename

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError, ValidationError
from app.core.responses import success, error
from app.core.validators import VideoUploadValidator
from app.domain.services.video_service import VideoService
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.video_repository import VideoRepository
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.storage.local_storage import get_storage

logger = logging.getLogger(__name__)

videos_bp = Blueprint("videos", __name__, url_prefix="/api/v1/videos")

MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2GB


def _video_service() -> VideoService:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return VideoService(VideoRepository(pool), FrameRepository(pool))


@videos_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_video():  # type: ignore[no-untyped-def]
    """Upload video file directly (multipart/form-data)."""
    try:
        user_id = get_current_user_id()

        if "file" not in request.files:
            raise ValidationError("Campo 'file' obrigatorio")

        file = request.files["file"]
        if not file.filename:
            raise ValidationError("Filename vazio")

        VideoUploadValidator.validate_extension(file.filename)
        safe_name = VideoUploadValidator.sanitize_filename(file.filename)

        # Save to storage
        storage = get_storage()
        video_id = str(uuid4())
        storage_key = f"raw-videos/{user_id}/{video_id}/{safe_name}"

        # Read file data
        file_data = file.read()
        if len(file_data) > MAX_UPLOAD_BYTES:
            raise ValidationError(f"Arquivo excede limite de {MAX_UPLOAD_BYTES // (1024*1024)}MB")

        storage.upload_bytes(storage_key, file_data, file.content_type or "video/mp4")

        # Create DB record
        service = _video_service()
        video = service.create_video(
            user_id=user_id,
            filename=storage_key,
            original_filename=file.filename,
            file_size=len(file_data),
        )

        return success(video, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("upload_video_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@videos_bp.route("/upload-url", methods=["POST"])
@jwt_required()
def get_upload_url():  # type: ignore[no-untyped-def]
    """Get presigned URL for direct upload to R2."""
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        filename = data.get("filename", "")
        content_type = data.get("content_type", "video/mp4")

        if not filename:
            raise ValidationError("filename obrigatorio")
        VideoUploadValidator.validate_extension(filename)
        safe_name = VideoUploadValidator.sanitize_filename(filename)

        video_id = str(uuid4())
        storage_key = f"raw-videos/{user_id}/{video_id}/{safe_name}"

        storage = get_storage()
        upload_url = storage.generate_presigned_upload_url(
            storage_key, content_type=content_type
        )

        # Create DB record
        service = _video_service()
        video = service.create_video(
            user_id=user_id,
            filename=storage_key,
            original_filename=filename,
            file_size=data.get("file_size"),
        )

        return success({
            "upload_url": upload_url,
            "video_id": video["id"],
            "storage_key": storage_key,
        }, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_upload_url_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@videos_bp.route("/<video_id>/extract", methods=["POST"])
@jwt_required()
def trigger_extraction(video_id: str):  # type: ignore[no-untyped-def]
    """Trigger frame extraction for a video."""
    try:
        user_id = get_current_user_id()
        service = _video_service()
        video = service.get_video(UUID(video_id))

        service.update_status(UUID(video_id), "extracting")

        # Despachar task Celery de extração
        from app.infrastructure.queue.tasks.extraction import extract_frames
        extract_frames.delay(
            video_key=video["filename"],
            video_id=video_id,
            user_id=str(user_id),
        )

        return success({"video_id": video_id, "status": "extracting"})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("trigger_extraction_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@videos_bp.route("/<video_id>/status", methods=["GET"])
@jwt_required()
def get_video_status(video_id: str):  # type: ignore[no-untyped-def]
    """Get video processing status with frame counts."""
    try:
        service = _video_service()
        video = service.get_video(UUID(video_id))
        counts = service.get_frame_counts(UUID(video_id))

        return success({
            "video": video,
            "frames": counts,
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_video_status_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
