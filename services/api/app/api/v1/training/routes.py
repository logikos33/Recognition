"""
Recognition — Training Routes.

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
from flask import Blueprint
from flask_jwt_extended import jwt_required

from app.core.rate_limiting import get_rate_limit_identifier
from app.extensions import limiter

from .annotation_handlers import (
    create_class_handler,
    get_annotations_handler,
    get_classes_handler,
    save_annotations_handler,
)
from .job_handlers import (
    acknowledge_alert_handler,
    activate_model_handler,
    create_job_handler,
    get_alerts_handler,
    get_job_status_handler,
    list_jobs_handler,
    list_models_handler,
)
from .validation_handlers import (
    get_frame_validation_stats_handler,
    validate_frame_handler,
)
from .video_handlers import (
    create_video_handler,
    get_frame_image_handler,
    get_video_frames_handler,
    list_videos_handler,
)

training_bp = Blueprint("training", __name__)


# --- Videos ---

@training_bp.route("/api/training/videos", methods=["GET"])
@jwt_required()
def list_videos():  # type: ignore[no-untyped-def]
    return list_videos_handler()


@training_bp.route("/api/training/videos", methods=["POST"])
@jwt_required()
def create_video():  # type: ignore[no-untyped-def]
    return create_video_handler()


# --- Frames (AnnotationInterface.jsx contract) ---

@training_bp.route("/api/training/videos/<video_id>/frames", methods=["GET"])
@jwt_required()
def get_video_frames(video_id: str):  # type: ignore[no-untyped-def]
    return get_video_frames_handler(video_id)


@training_bp.route("/api/training/frames/<frame_id>/image", methods=["GET"])
@jwt_required()
def get_frame_image(frame_id: str):  # type: ignore[no-untyped-def]
    return get_frame_image_handler(frame_id)


# --- Annotations (AnnotationInterface.jsx contract) ---

@training_bp.route("/api/training/frames/<frame_id>/annotations", methods=["GET"])
@jwt_required()
def get_annotations(frame_id: str):  # type: ignore[no-untyped-def]
    return get_annotations_handler(frame_id)


@training_bp.route("/api/training/frames/<frame_id>/annotations", methods=["POST"])
@jwt_required()
def save_annotations(frame_id: str):  # type: ignore[no-untyped-def]
    return save_annotations_handler(frame_id)


# --- Classes (AnnotationInterface.jsx contract) ---

@training_bp.route("/api/classes", methods=["GET"])
@jwt_required()
def get_classes():  # type: ignore[no-untyped-def]
    return get_classes_handler()


@training_bp.route("/api/classes", methods=["POST"])
@jwt_required()
def create_class():  # type: ignore[no-untyped-def]
    return create_class_handler()


# --- Training Jobs ---

@training_bp.route("/api/training/jobs", methods=["POST"])
@limiter.limit("20 per day", key_func=get_rate_limit_identifier)
@jwt_required()
def create_job():  # type: ignore[no-untyped-def]
    return create_job_handler()


@training_bp.route("/api/training/jobs", methods=["GET"])
@jwt_required()
def list_jobs():  # type: ignore[no-untyped-def]
    return list_jobs_handler()


@training_bp.route("/api/training/jobs/<job_id>/status", methods=["GET"])
@jwt_required()
def get_job_status(job_id: str):  # type: ignore[no-untyped-def]
    return get_job_status_handler(job_id)


# --- Models ---

@training_bp.route("/api/training/models", methods=["GET"])
@jwt_required()
def list_models():  # type: ignore[no-untyped-def]
    return list_models_handler()


@training_bp.route("/api/training/models/<model_id>/activate", methods=["POST"])
@jwt_required()
def activate_model(model_id: str):  # type: ignore[no-untyped-def]
    return activate_model_handler(model_id)


# --- Validation ---

@training_bp.route("/api/training/frames/<frame_id>/validate", methods=["POST"])
@jwt_required()
def validate_frame(frame_id: str):  # type: ignore[no-untyped-def]
    return validate_frame_handler(frame_id)


@training_bp.route("/api/training/videos/<video_id>/validation-stats", methods=["GET"])
@jwt_required()
def get_validation_stats(video_id: str):  # type: ignore[no-untyped-def]
    return get_frame_validation_stats_handler(video_id)


# --- Job Progress (Redis — no DB query) ---

@training_bp.route("/api/training/jobs/<job_id>/progress", methods=["GET"])
@jwt_required()
def get_job_progress(job_id: str):  # type: ignore[no-untyped-def]
    """Lê progresso do job via Redis sem bater no banco."""
    import json
    import os

    import redis as _redis

    from app.core.responses import error as err_resp
    from app.core.responses import success

    try:
        r = _redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True,
        )
        raw = r.get(f"training_progress:{job_id}")
        r.close()
        if raw is None:
            return err_resp("Progresso não disponível — job ainda não iniciado ou expirado", 404)
        return success(json.loads(raw))
    except Exception as exc:
        return err_resp(f"Erro ao ler progresso: {exc}", 500)


# --- Alerts ---

@training_bp.route("/api/cameras/<camera_id>/alerts", methods=["GET"])
@jwt_required()
def get_alerts(camera_id: str):  # type: ignore[no-untyped-def]
    return get_alerts_handler(camera_id)


@training_bp.route("/api/alerts/<alert_id>/acknowledge", methods=["POST"])
@jwt_required()
def acknowledge_alert(alert_id: str):  # type: ignore[no-untyped-def]
    return acknowledge_alert_handler(alert_id)
