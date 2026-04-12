"""
EPI Monitor V2 — Video Upload Routes.

POST /api/v1/videos/upload                  — Upload video file directly
POST /api/v1/videos/upload-url              — Get presigned upload URL (R2)
POST /api/v1/videos/<id>/extract            — Trigger frame extraction
POST /api/v1/videos/<id>/retry-extraction   — Retry failed extraction
GET  /api/v1/videos/<id>/status             — Get video processing status
DELETE /api/v1/videos/<id>                  — Delete video and frames
GET  /api/v1/videos/storage                 — Storage usage stats
"""
import logging
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


def _frame_repo() -> FrameRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return FrameRepository(pool)


def _video_repo() -> VideoRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return VideoRepository(pool)


@videos_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_video():  # type: ignore[no-untyped-def]
    """Upload video file directly (multipart/form-data).
    ---
    tags:
      - videos
    summary: Upload direto de vídeo (multipart)
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: Arquivo de vídeo (mp4, avi, mov) — máx 2GB
    responses:
      201:
        description: Vídeo salvo
      400:
        description: Arquivo inválido
    """
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
        logger.info("upload_video_stored: storage=%s, key=%s, size=%d", type(storage).__name__, storage_key, len(file_data))

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
    """Get presigned URL for direct upload to R2.
    ---
    tags:
      - videos
    summary: Obter presigned URL para upload direto ao R2
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [filename]
          properties:
            filename: {type: string, example: video.mp4}
            content_type: {type: string, example: video/mp4}
            file_size: {type: integer}
    responses:
      201:
        description: URL de upload gerada
        schema:
          properties:
            upload_url: {type: string}
            video_id: {type: string}
            storage_key: {type: string}
      400:
        description: Filename inválido
    """
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
    """Get video processing status with frame counts.
    ---
    tags:
      - videos
    summary: Status do processamento de vídeo
    security:
      - Bearer: []
    parameters:
      - in: path
        name: video_id
        type: string
        required: true
    responses:
      200:
        description: Status e contagem de frames
      404:
        description: Vídeo não encontrado
    """
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


@videos_bp.route("/<video_id>", methods=["DELETE"])
@jwt_required()
def delete_video(video_id: str):  # type: ignore[no-untyped-def]
    """Delete a video and its frames."""
    try:
        from app.core.exceptions import NotFoundError  # noqa: PLC0415
        user_id = get_current_user_id()
        service = _video_service()

        try:
            video = service.get_video(UUID(video_id))
        except NotFoundError:
            # Already deleted — idempotent DELETE is correct REST behavior
            return success({"deleted": True, "video_id": video_id, "already_gone": True})

        if str(video.get("user_id")) != str(user_id):
            return error("Sem permissao", 403)

        # Cleanup video file from storage (best-effort, frames cleaned by DB cascade)
        try:
            storage = get_storage()
            storage.delete(video["filename"])
        except Exception as exc:
            logger.warning("delete_video_storage_cleanup: %s", exc)

        service.delete_video(UUID(video_id))
        return success({"deleted": True, "video_id": video_id})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("delete_video_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@videos_bp.route("/<video_id>/retry-extraction", methods=["POST"])
@jwt_required()
def retry_extraction(video_id: str):  # type: ignore[no-untyped-def]
    """Reset video to pending and re-dispatch frame extraction."""
    try:
        user_id = get_current_user_id()
        service = _video_service()
        video = service.get_video(UUID(video_id))

        if str(video.get("user_id")) != str(user_id):
            return error("Sem permissao", 403)

        service.update_status(UUID(video_id), "extracting", error_message=None)

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
        logger.error("retry_extraction_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@videos_bp.route("/<video_id>/download-url", methods=["GET"])
@jwt_required()
def get_download_url(video_id: str):  # type: ignore[no-untyped-def]
    """Generate presigned download URL for raw video (browser-side frame extraction)."""
    try:
        user_id = get_current_user_id()
        service = _video_service()
        video = service.get_video(UUID(video_id))
        if str(video.get("user_id")) != str(user_id):
            return error("Sem permissao", 403)
        storage = get_storage()
        url = storage.generate_presigned_download_url(video["filename"], ttl=900)
        logger.info("download_url_generated: video_id=%s, key=%s, storage=%s",
                    video_id, video["filename"], type(storage).__name__)
        return success({"url": url})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_download_url_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@videos_bp.route("/<video_id>/frames/upload", methods=["POST"])
@jwt_required()
def upload_frame(video_id: str):  # type: ignore[no-untyped-def]
    """Receive a single JPEG frame from browser extraction and persist it."""
    try:
        user_id = get_current_user_id()
        if "frame" not in request.files:
            raise ValidationError("Campo 'frame' obrigatorio")
        file = request.files["frame"]
        frame_number = int(request.form.get("frame_number", 0))
        timestamp = float(request.form.get("timestamp", 0.0))

        frame_data = file.read()
        frame_key = f"frames/{user_id}/{video_id}/frame_{frame_number:04d}.jpg"
        get_storage().upload_bytes(frame_key, frame_data, "image/jpeg")

        repo = _frame_repo()
        frame = repo.create(
            video_id=UUID(video_id),
            frame_number=frame_number,
            filename=frame_key,
            timestamp_seconds=timestamp,
        )
        repo.update_quality_status(UUID(frame["id"]), "approved", {})
        return success({"frame_id": frame["id"], "frame_number": frame_number}, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("upload_frame_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@videos_bp.route("/<video_id>/finalize-extraction", methods=["POST"])
@jwt_required()
def finalize_extraction(video_id: str):  # type: ignore[no-untyped-def]
    """Mark video as extracted after browser-side frame capture completes."""
    try:
        frame_count = (request.get_json() or {}).get("frame_count", 0)
        _video_repo().update_status(UUID(video_id), "extracted", frame_count=frame_count)
        return success({"status": "extracted", "frame_count": frame_count})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("finalize_extraction_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@videos_bp.route("/storage", methods=["GET"])
@jwt_required()
def get_storage_stats():  # type: ignore[no-untyped-def]
    """Get user's training storage usage."""
    try:
        user_id = get_current_user_id()
        service = _video_service()
        stats = service.get_storage_stats(user_id)
        return success(stats)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_storage_stats_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
