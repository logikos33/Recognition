"""
EPI Monitor V2 — Frame Quality Filter Task.

Celery task: baixa frame do R2, filtra por qualidade (blur, brightness),
atualiza DB com quality_status APPROVED/REJECTED.
"""
import logging
import os
import tempfile
from uuid import UUID

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)


def _get_storage():
    from app.infrastructure.storage.local_storage import get_storage
    return get_storage()


def _get_frame_repo():
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.frame_repository import FrameRepository
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("DatabasePool não inicializado no worker")
    return FrameRepository(pool)


@celery.task(bind=True, max_retries=2, queue="extraction", name="tasks.quality.quality_filter")
def quality_filter(
    self,
    frame_key: str,
    frame_id: str,
    video_id: str,
    blur_threshold: float = 100.0,
    brightness_threshold: float = 40.0,
) -> dict:
    """Filtra frame por qualidade.

    Pipeline:
    1. Baixa frame do R2 para /tmp
    2. Blur check (Laplacian variance)
    3. Brightness check (HSV V channel mean)
    4. Atualiza DB: quality_status = 'approved' | 'rejected'
    5. Limpa /tmp

    Args:
        frame_key: Chave R2 do frame (ex: frames/{user_id}/{video_id}/frame_0001.jpg)
        frame_id: UUID do frame no banco
        video_id: UUID do vídeo (para logging)
        blur_threshold: Mínimo de variância do Laplacian (padrão 100)
        brightness_threshold: Mínimo de brilho em HSV-V (padrão 40)
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    tmp_path = None
    try:
        storage = _get_storage()

        # 1. Download do frame do R2
        frame_data = storage.download_bytes(frame_key)

        # Decodificar com OpenCV direto da memória (sem salvar em /tmp)
        img_array = np.frombuffer(frame_data, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        del frame_data

        if img is None:
            logger.warning("quality_unreadable: frame_id=%s", frame_id)
            _set_status(frame_id, "rejected", {"reason": "unreadable"})
            return {"frame_id": frame_id, "accepted": False, "reason": "unreadable"}

        # 2. Blur check (Laplacian variance)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        if blur_score < blur_threshold:
            logger.debug("quality_reject: frame=%s, reason=blur, score=%.1f", frame_id, blur_score)
            _set_status(frame_id, "rejected", {"reason": "blur", "blur": blur_score})
            return {"frame_id": frame_id, "accepted": False, "reason": "blur",
                    "scores": {"blur": blur_score}}

        # 3. Brightness check (HSV V channel mean)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        brightness = float(np.mean(hsv[:, :, 2]))

        if brightness < brightness_threshold:
            logger.debug("quality_reject: frame=%s, reason=dark, score=%.1f", frame_id, brightness)
            _set_status(frame_id, "rejected", {"reason": "dark", "blur": blur_score, "brightness": brightness})
            return {"frame_id": frame_id, "accepted": False, "reason": "dark",
                    "scores": {"blur": blur_score, "brightness": brightness}}

        # 4. Aprovado
        scores = {"blur": blur_score, "brightness": brightness}
        _set_status(frame_id, "approved", scores)

        logger.debug("quality_approve: frame=%s, blur=%.1f, brightness=%.1f", frame_id, blur_score, brightness)
        return {"frame_id": frame_id, "accepted": True, "reason": "passed", "scores": scores}

    except Exception as exc:
        logger.error("quality_filter_failed: frame=%s, error=%s", frame_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=10)


def _set_status(frame_id: str, status: str, scores: dict) -> None:
    """Atualiza quality_status no DB."""
    try:
        repo = _get_frame_repo()
        repo.update_quality_status(UUID(frame_id), status, scores)
    except Exception as exc:
        logger.error("quality_set_status_failed: frame_id=%s, error=%s", frame_id, exc)
