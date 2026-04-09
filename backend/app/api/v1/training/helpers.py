"""
EPI Monitor V2 — Training service factories.

Shared helpers used by video_handlers, annotation_handlers, and job_handlers.
"""
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


def _get_pool() -> DatabasePool:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def get_video_service() -> VideoService:
    pool = _get_pool()
    return VideoService(VideoRepository(pool), FrameRepository(pool))


def get_annotation_service() -> AnnotationService:
    pool = _get_pool()
    return AnnotationService(AnnotationRepository(pool), FrameRepository(pool))


def get_training_service() -> TrainingService:
    pool = _get_pool()
    return TrainingService(TrainingRepository(pool))


def get_inference_service() -> InferenceService:
    pool = _get_pool()
    return InferenceService(AlertRepository(pool))
