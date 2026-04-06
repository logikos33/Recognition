"""
EPI Monitor V2 — Frame Quality Filter Task.

Celery task: filtra frames por qualidade (blur, brightness, duplicates).
"""
import logging

import cv2
import numpy as np

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=2, queue="extraction", name="tasks.quality.quality_filter")
def quality_filter(
    self,
    frame_path: str,
    frame_id: str,
    blur_threshold: float = 100.0,
    brightness_threshold: float = 40.0,
) -> dict:
    """Filtra frame por qualidade.

    Checks em sequência (falha rápida):
    1. Blur check (Laplacian variance)
    2. Brightness check (HSV V channel mean)

    Retorna dict com resultado e scores.
    """
    try:
        img = cv2.imread(frame_path)
        if img is None:
            return {
                "frame_id": frame_id,
                "accepted": False,
                "reason": "unreadable",
                "scores": {},
            }

        # 1. Blur check
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

        if blur_score < blur_threshold:
            logger.debug("quality_reject: frame=%s, reason=blur, score=%.1f", frame_id, blur_score)
            return {
                "frame_id": frame_id,
                "accepted": False,
                "reason": "blur",
                "scores": {"blur": blur_score},
            }

        # 2. Brightness check
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        brightness = float(np.mean(hsv[:, :, 2]))

        if brightness < brightness_threshold:
            logger.debug(
                "quality_reject: frame=%s, reason=dark, score=%.1f",
                frame_id, brightness,
            )
            return {
                "frame_id": frame_id,
                "accepted": False,
                "reason": "dark",
                "scores": {"blur": blur_score, "brightness": brightness},
            }

        logger.debug(
            "quality_accept: frame=%s, blur=%.1f, brightness=%.1f",
            frame_id, blur_score, brightness,
        )
        return {
            "frame_id": frame_id,
            "accepted": True,
            "reason": "passed",
            "scores": {"blur": blur_score, "brightness": brightness},
        }

    except Exception as exc:
        logger.error(
            "quality_filter_failed: frame=%s, error=%s",
            frame_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc, countdown=10)
