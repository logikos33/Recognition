"""
Recognition — Training Routes.

Routes compatíveis com AnnotationInterface.jsx:
  GET  /api/training/videos/<video_id>/frames
  GET  /api/training/frames/<frame_id>/annotations
  POST /api/training/frames/<frame_id>/annotations
  POST /api/training/frames/<frame_id>/pre-annotate           (WS-B4, backend plugável OFF por padrão)
  POST /api/training/frames/<frame_id>/accept-suggestions     (WS-B4)
  POST /api/training/frames/<frame_id>/pre-annotation-review  (fila de aprovação de propostas — migration 111)
  GET  /api/training/frames/<frame_id>/image
  GET  /api/training/active-learning/queue                (WS-B2)
  GET  /api/classes
  POST /api/classes
  PATCH /api/classes/<id>                                  (curadoria — migration 110)
  GET  /api/training/videos  (lista vídeos do usuário)
  POST /api/training/videos  (upload de vídeo)
  GET  /api/training/images/facets                         (curadoria — migration 110)
  POST /api/training/frames/curation                       (curadoria — migration 110)
  GET  /api/v1/training/propagation/preflight               (pool/sementes/custo antes de criar o job)
  POST /api/v1/training/propagation/jobs                   (propagação semeada — migration 112)
  GET  /api/v1/training/propagation/jobs
  GET  /api/v1/training/propagation/jobs/<id>
  POST /api/v1/training/propagation/jobs/<id>/callback     (interno GPU→API)
  POST /api/v1/training/search/preflight                   (elegibilidade+custo antes de criar o job)
  POST /api/v1/training/search/jobs                         (busca por conteúdo — migration 113)
  GET  /api/v1/training/search/jobs
  GET  /api/v1/training/search/jobs/<id>
  POST /api/v1/training/search/jobs/<id>/callback           (interno GPU→API)
  POST /api/v1/training/search/jobs/<id>/promote             (achado → proposta pendente)
"""
from flask import Blueprint
from flask_jwt_extended import jwt_required

from app.core.auth import require_training_role
from app.core.rate_limiting import get_rate_limit_identifier
from app.extensions import limiter

from .annotation_handlers import (
    accept_suggestions_handler,
    create_class_handler,
    delete_class_handler,
    get_annotations_handler,
    get_classes_handler,
    patch_class_handler,
    pre_annotate_frame_handler,
    pre_annotation_review_handler,
    save_annotations_handler,
    update_class_handler,
)
from .coverage_handlers import get_coverage_matrix_handler
from .image_handlers import (
    active_learning_queue_handler,
    curate_frames_handler,
    get_image_facets_handler,
    list_training_images_handler,
    upload_training_images_handler,
)
from .job_handlers import (
    activate_model_handler,
    create_job_handler,
    get_alerts_handler,
    get_current_job_status_handler,
    get_job_status_handler,
    list_jobs_handler,
    list_models_handler,
    stop_job_handler,
    training_progress_callback_handler,
)
from .propagation_handlers import (
    create_propagation_job_handler,
    get_propagation_job_handler,
    list_propagation_jobs_handler,
    preflight_propagation_handler,
    propagation_callback_handler,
)
from .scenario_handlers import (
    get_scenario_config_handler,
    upsert_scenario_config_handler,
)
from .search_handlers import (
    create_search_job_handler,
    get_search_job_handler,
    list_search_jobs_handler,
    preflight_search_handler,
    promote_search_findings_handler,
    search_callback_handler,
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


# --- Pré-anotação plugável (WS-B4, ADR-0031 adendo — OFF por padrão) ---

@training_bp.route("/api/training/frames/<frame_id>/pre-annotate", methods=["POST"])
@jwt_required()
@require_training_role("write")
def pre_annotate_frame(frame_id: str):  # type: ignore[no-untyped-def]
    return pre_annotate_frame_handler(frame_id)


@training_bp.route("/api/training/frames/<frame_id>/accept-suggestions", methods=["POST"])
@jwt_required()
@require_training_role("write")
def accept_suggestions(frame_id: str):  # type: ignore[no-untyped-def]
    return accept_suggestions_handler(frame_id)


# --- Fila de aprovação de propostas (migration 111) ---

@training_bp.route("/api/training/frames/<frame_id>/pre-annotation-review", methods=["POST"])
@jwt_required()
@require_training_role("write")
def pre_annotation_review(frame_id: str):  # type: ignore[no-untyped-def]
    return pre_annotation_review_handler(frame_id)


# --- Classes (AnnotationInterface.jsx contract) ---

@training_bp.route("/api/classes", methods=["GET"])
@jwt_required()
def get_classes():  # type: ignore[no-untyped-def]
    return get_classes_handler()


@training_bp.route("/api/classes", methods=["POST"])
@jwt_required()
@require_training_role("write")
def create_class():  # type: ignore[no-untyped-def]
    return create_class_handler()


@training_bp.route("/api/classes/<int:class_id>", methods=["PUT"])
@jwt_required()
@require_training_role("write")
def update_class(class_id: int):  # type: ignore[no-untyped-def]
    return update_class_handler(class_id)


@training_bp.route("/api/classes/<int:class_id>", methods=["PATCH"])
@jwt_required()
@require_training_role("write")
def patch_class(class_id: int):  # type: ignore[no-untyped-def]
    return patch_class_handler(class_id)


@training_bp.route("/api/classes/<int:class_id>", methods=["DELETE"])
@jwt_required()
@require_training_role("write")
def delete_class(class_id: int):  # type: ignore[no-untyped-def]
    return delete_class_handler(class_id)


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


# --- Propagação semeada (migration 112 — DINOv2+SAM no RunPod) ---

@training_bp.route("/api/v1/training/propagation/preflight", methods=["GET"])
@jwt_required()
@require_training_role("write")
def preflight_propagation():  # type: ignore[no-untyped-def]
    return preflight_propagation_handler()


@training_bp.route("/api/v1/training/propagation/jobs", methods=["POST"])
@jwt_required()
@require_training_role("write")
def create_propagation_job():  # type: ignore[no-untyped-def]
    return create_propagation_job_handler()


@training_bp.route("/api/v1/training/propagation/jobs", methods=["GET"])
@jwt_required()
def list_propagation_jobs():  # type: ignore[no-untyped-def]
    return list_propagation_jobs_handler()


@training_bp.route("/api/v1/training/propagation/jobs/<job_id>", methods=["GET"])
@jwt_required()
def get_propagation_job(job_id: str):  # type: ignore[no-untyped-def]
    return get_propagation_job_handler(job_id)


# Callback interno GPU→API — SEM @jwt_required(): mesmo padrão de
# /api/v1/training/jobs/<job_id>/progress-callback (auth via
# X-Callback-Token, hmac.compare_digest, ver propagation_handlers.py).
@training_bp.route(
    "/api/v1/training/propagation/jobs/<job_id>/callback", methods=["POST"]
)
@limiter.limit("60 per minute")
def propagation_callback(job_id: str):  # type: ignore[no-untyped-def]
    return propagation_callback_handler(job_id)


# --- Busca por conteúdo (migration 113 — OWLv2 no RunPod) ---

@training_bp.route("/api/v1/training/search/preflight", methods=["POST"])
@jwt_required()
@require_training_role("write")
def preflight_search():  # type: ignore[no-untyped-def]
    return preflight_search_handler()


@training_bp.route("/api/v1/training/search/jobs", methods=["POST"])
@jwt_required()
@require_training_role("write")
def create_search_job():  # type: ignore[no-untyped-def]
    return create_search_job_handler()


@training_bp.route("/api/v1/training/search/jobs", methods=["GET"])
@jwt_required()
def list_search_jobs():  # type: ignore[no-untyped-def]
    return list_search_jobs_handler()


@training_bp.route("/api/v1/training/search/jobs/<job_id>", methods=["GET"])
@jwt_required()
def get_search_job(job_id: str):  # type: ignore[no-untyped-def]
    return get_search_job_handler(job_id)


@training_bp.route("/api/v1/training/search/jobs/<job_id>/promote", methods=["POST"])
@jwt_required()
@require_training_role("write")
def promote_search_findings(job_id: str):  # type: ignore[no-untyped-def]
    return promote_search_findings_handler(job_id)


# Callback interno GPU→API — SEM @jwt_required(): mesmo padrão de
# /api/v1/training/propagation/jobs/<job_id>/callback (auth via
# X-Callback-Token, hmac.compare_digest, ver search_handlers.py).
@training_bp.route(
    "/api/v1/training/search/jobs/<job_id>/callback", methods=["POST"]
)
@limiter.limit("60 per minute")
def search_callback(job_id: str):  # type: ignore[no-untyped-def]
    return search_callback_handler(job_id)


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


# --- Training Images gallery ---

@training_bp.route("/api/training/images", methods=["GET"])
@jwt_required()
def list_training_images():  # type: ignore[no-untyped-def]
    return list_training_images_handler()


@training_bp.route("/api/training/images/upload", methods=["POST"])
@jwt_required()
@require_training_role("write")
def upload_training_images():  # type: ignore[no-untyped-def]
    return upload_training_images_handler()


@training_bp.route("/api/training/images/facets", methods=["GET"])
@jwt_required()
def get_training_images_facets():  # type: ignore[no-untyped-def]
    return get_image_facets_handler()


@training_bp.route("/api/training/coverage-matrix", methods=["GET"])
@jwt_required()
def get_training_coverage_matrix():  # type: ignore[no-untyped-def]
    return get_coverage_matrix_handler()


# --- Curadoria de frames (migration 110) ---

@training_bp.route("/api/training/frames/curation", methods=["POST"])
@jwt_required()
@require_training_role("write")
def curate_frames():  # type: ignore[no-untyped-def]
    return curate_frames_handler()


# --- Active learning queue (WS-B2) ---

@training_bp.route("/api/training/active-learning/queue", methods=["GET"])
@jwt_required()
def active_learning_queue():  # type: ignore[no-untyped-def]
    return active_learning_queue_handler()


# --- Current job status (polling endpoint) ---

@training_bp.route("/api/training/jobs/current/status", methods=["GET"])
@jwt_required()
def get_current_job_status():  # type: ignore[no-untyped-def]
    return get_current_job_status_handler()


@training_bp.route("/api/training/jobs/<job_id>/stop", methods=["POST"])
@jwt_required()
def stop_job(job_id: str):  # type: ignore[no-untyped-def]
    return stop_job_handler(job_id)


# --- Progress callback (interno GPU→API, WS-A4) ---
# SEM @jwt_required(): o pod RunPod não tem JWT de usuário — auth é
# via header X-Callback-Token comparado a training_jobs.callback_token
# (hmac.compare_digest, ver training_progress_callback_handler). Rate limit
# por IP (sem identidade de tenant/usuário nesta rota).

@training_bp.route("/api/v1/training/jobs/<job_id>/progress-callback", methods=["POST"])
@limiter.limit("60 per minute")
def training_progress_callback(job_id: str):  # type: ignore[no-untyped-def]
    return training_progress_callback_handler(job_id)


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


# --- Scenario Config ---

@training_bp.route("/api/training/scenarios/<model_id>/config", methods=["PUT"])
@jwt_required()
def upsert_scenario_config(model_id: str):  # type: ignore[no-untyped-def]
    return upsert_scenario_config_handler(model_id)


@training_bp.route("/api/training/scenarios/<model_id>/config", methods=["GET"])
@jwt_required()
def get_scenario_config(model_id: str):  # type: ignore[no-untyped-def]
    return get_scenario_config_handler(model_id)


# --- Alerts ---

@training_bp.route("/api/cameras/<camera_id>/alerts", methods=["GET"])
@jwt_required()
def get_alerts(camera_id: str):  # type: ignore[no-untyped-def]
    return get_alerts_handler(camera_id)
