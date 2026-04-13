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

        frames_expected = video.get("frames_expected") or 0
        frame_count = video.get("frame_count") or 0
        video["progress_percent"] = (
            round(min(frame_count / frames_expected * 100, 100))
            if frames_expected > 0
            else 0
        )

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

        storage = get_storage()

        # Collect R2 frame keys before deleting DB records
        from app.infrastructure.storage.r2_storage import R2Storage  # noqa: PLC0415
        frame_keys: list[str] = []
        if isinstance(storage, R2Storage):
            try:
                frame_keys = storage.list_keys(f"frames/{user_id}/{video_id}/")
            except Exception as exc:
                logger.warning("delete_video_list_frames: %s", exc)

        # Delete raw video from R2 (best-effort)
        try:
            storage.delete(video["filename"])
        except Exception as exc:
            logger.warning("delete_video_r2_video: %s", exc)

        # Delete DB records (VideoRepository.delete handles frames cascade)
        service.delete_video(UUID(video_id))

        # Delete frame files from R2 in background to keep response fast
        if frame_keys:
            import threading  # noqa: PLC0415
            def _delete_r2_frames() -> None:
                s = get_storage()
                for key in frame_keys:
                    try:
                        s.delete(key)
                    except Exception as exc:
                        logger.warning("r2_frame_delete_failed: key=%s err=%s", key, exc)
            threading.Thread(target=_delete_r2_frames, daemon=True).start()
            logger.info("r2_cleanup_started: video_id=%s frames=%d", video_id, len(frame_keys))

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
        video = _video_service().get_video(UUID(video_id))
        if str(video.get("user_id")) != str(user_id):
            return error("Sem permissao", 403)

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


@videos_bp.route("/<video_id>/blob", methods=["GET"])
@jwt_required()
def get_video_blob(video_id: str):  # type: ignore[no-untyped-def]
    """Stream raw video bytes through the API for browser-side frame extraction.

    Using our API as proxy avoids requiring R2 CORS for GET requests.
    The client receives a streamable response it can use as a blob URL.
    """
    from flask import Response, stream_with_context  # noqa: PLC0415
    try:
        user_id = get_current_user_id()
        service = _video_service()
        video = service.get_video(UUID(video_id))
        if str(video.get("user_id")) != str(user_id):
            return error("Sem permissao", 403)

        storage = get_storage()
        filename = video["filename"]
        content_type = video.get("content_type") or "video/mp4"

        # R2Storage: stream directly via boto3 get_object (no full buffer)
        if hasattr(storage, "_client"):
            try:
                obj = storage._client.get_object(  # type: ignore[attr-defined]
                    Bucket=storage._bucket,  # type: ignore[attr-defined]
                    Key=filename,
                )
                body = obj["Body"]
                content_length = str(obj.get("ContentLength", ""))

                def _generate():  # type: ignore[no-untyped-def]
                    for chunk in body.iter_chunks(chunk_size=65536):
                        yield chunk

                headers = {"Content-Disposition": "inline"}
                if content_length:
                    headers["Content-Length"] = content_length
                logger.info(
                    "video_blob_stream: video_id=%s, key=%s, size=%s",
                    video_id, filename, content_length,
                )
                return Response(
                    stream_with_context(_generate()),
                    mimetype=content_type,
                    headers=headers,
                )
            except Exception as exc:
                logger.error("video_blob_r2_error: %s", exc, exc_info=True)
                return error("Erro ao baixar video do armazenamento", 500)

        # LocalStorage: read into memory and serve
        data = storage.download_bytes(filename)
        return Response(data, mimetype=content_type, headers={"Content-Disposition": "inline"})

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_video_blob_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def _run_extraction(video_id: str, user_id: str, filename: str) -> None:  # type: ignore[no-untyped-def]
    """Background thread: download from R2, extract frames with OpenCV, upload back."""
    import cv2  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    import os  # noqa: PLC0415

    pool = DatabasePool.get_instance()
    if pool is None:
        # Mark as error via a fresh pool attempt — if still None, status stays stuck (logged)
        logger.error("server_extract_thread: db pool unavailable, video_id=%s will remain extracting", video_id)
        # Try once more after a brief pause (pool may have been briefly unavailable)
        import time  # noqa: PLC0415
        time.sleep(2)
        pool = DatabasePool.get_instance()
        if pool is None:
            logger.critical("server_extract_thread: db pool permanently unavailable, video_id=%s stuck", video_id)
            return
    svc = VideoService(VideoRepository(pool), FrameRepository(pool))
    frame_repo = FrameRepository(pool)
    storage = get_storage()

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
            if hasattr(storage, "_client"):
                obj = storage._client.get_object(  # type: ignore[attr-defined]
                    Bucket=storage._bucket,  # type: ignore[attr-defined]
                    Key=filename,
                )
                tmp.write(obj["Body"].read())
            else:
                tmp.write(storage.download_bytes(filename))

        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            svc.update_status(UUID(video_id), "error", error_message="cv2 nao conseguiu abrir o video")
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        target = min(60, max(10, int(duration / 2))) if duration > 0 else 10
        interval = duration / target if target > 0 else 1.0
        timestamps = [i * interval for i in range(target)]

        # Persiste total esperado para o frontend calcular progresso
        video_repo = VideoRepository(pool)
        video_repo.update_status(UUID(video_id), "extracting", frames_expected=target)

        captured = 0
        for i, ts in enumerate(timestamps):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(ts * fps))
            ret, frame = cap.read()
            if not ret:
                continue
            frame_resized = cv2.resize(frame, (640, 360))
            ok, buf = cv2.imencode(".jpg", frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                continue
            frame_key = f"frames/{user_id}/{video_id}/frame_{i:04d}.jpg"
            storage.upload_bytes(frame_key, buf.tobytes(), "image/jpeg")
            fr = frame_repo.create(
                video_id=UUID(video_id),
                frame_number=i,
                filename=frame_key,
                timestamp_seconds=ts,
            )
            frame_repo.update_quality_status(UUID(fr["id"]), "approved", {})
            captured += 1
            if captured % 5 == 0:
                video_repo.update_progress(UUID(video_id), captured)

        cap.release()
        svc.update_status(UUID(video_id), "extracted", frame_count=captured)
        logger.info("server_extract_done: video_id=%s, frames=%d", video_id, captured)

    except Exception as exc:
        logger.error("server_extract_thread_error: %s", exc, exc_info=True)
        try:
            svc.update_status(UUID(video_id), "error", error_message=str(exc))
        except Exception:
            pass
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@videos_bp.route("/<video_id>/server-extract", methods=["POST"])
@jwt_required()
def server_extract(video_id: str):  # type: ignore[no-untyped-def]
    """Start server-side frame extraction in a background thread.

    Returns 202 immediately; poll /<video_id>/status to track progress.
    Handles all codecs (AVI/MOV/MP4/H265) via OpenCV — no browser dependency.
    """
    import threading  # noqa: PLC0415
    try:
        user_id = get_current_user_id()
        service = _video_service()
        video = service.get_video(UUID(video_id))
        if str(video.get("user_id")) != str(user_id):
            return error("Sem permissao", 403)

        service.update_status(UUID(video_id), "extracting")

        t = threading.Thread(
            target=_run_extraction,
            args=(video_id, str(user_id), video["filename"]),
            daemon=True,
        )
        t.start()

        return success({"video_id": video_id, "status": "extracting"}, status=202)

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("server_extract_error: %s", exc, exc_info=True)
        return error("Erro ao iniciar extracao", 500)


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


_ALLOWED_IMAGE_EXTS: frozenset = frozenset({"jpg", "jpeg", "png", "webp"})
_MAX_IMAGES_PER_BATCH = 50
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


@videos_bp.route("/images/upload", methods=["POST"])
@jwt_required()
def upload_images():  # type: ignore[no-untyped-def]
    """Upload direct images (JPG/PNG/WebP) as training frames.

    Creates a synthetic training_videos record so AnnotationInterface can
    load frames via GET /api/training/videos/{video_id}/frames.
    Returns video_id for frontend to open annotation workflow.
    """
    try:
        user_id = get_current_user_id()

        if "images" not in request.files:
            raise ValidationError("Campo 'images' obrigatorio")

        files = request.files.getlist("images")
        if not files:
            raise ValidationError("Nenhum arquivo enviado")
        if len(files) > _MAX_IMAGES_PER_BATCH:
            raise ValidationError(f"Maximo de {_MAX_IMAGES_PER_BATCH} imagens por upload")

        pool = DatabasePool.get_instance()
        if pool is None:
            raise RuntimeError("Database pool not initialized")
        video_repo = VideoRepository(pool)
        frame_repo = FrameRepository(pool)

        batch_id = str(uuid4())
        video = video_repo.create(
            user_id=user_id,
            filename=f"direct-upload/{user_id}/{batch_id}/batch",
            original_filename="direct_upload_batch",
            file_size=None,
        )
        actual_video_id = str(video["id"])

        storage = get_storage()
        uploaded = 0
        failed = 0

        for i, file in enumerate(files):
            try:
                fname = file.filename or ""
                ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                if ext not in _ALLOWED_IMAGE_EXTS:
                    failed += 1
                    continue

                data = file.read()
                if not data or len(data) > _MAX_IMAGE_BYTES:
                    failed += 1
                    continue

                frame_key = f"frames/{user_id}/{actual_video_id}/frame_{i:04d}.{ext}"
                content_type = "image/jpeg" if ext == "jpg" else f"image/{ext}"
                storage.upload_bytes(frame_key, data, content_type)

                fr = frame_repo.create(
                    video_id=UUID(actual_video_id),
                    frame_number=i,
                    filename=frame_key,
                    timestamp_seconds=float(i),
                )
                frame_repo.update_quality_status(UUID(fr["id"]), "approved", {})
                uploaded += 1

            except Exception as exc:
                logger.warning("upload_images_frame_error: i=%d, err=%s", i, exc)
                failed += 1

        video_repo.update_status(UUID(actual_video_id), "extracted", frame_count=uploaded)
        logger.info("upload_images_done: video_id=%s, uploaded=%d, failed=%d", actual_video_id, uploaded, failed)
        return success({
            "video_id": actual_video_id,
            "uploaded": uploaded,
            "failed": failed,
            "status": "extracted",
        }, status=201)

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("upload_images_error: %s", exc, exc_info=True)
        return error("Erro ao processar imagens", 500)
