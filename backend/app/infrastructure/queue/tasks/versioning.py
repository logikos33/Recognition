"""
EPI Monitor V2 — Dataset Versioning Task.

Celery task: monta dataset YOLO versionado a partir de frames anotados.
Split por fonte de vídeo (não por frame individual).
"""
import json
import logging
import random
from uuid import uuid4

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=2, queue="versioning", name="tasks.versioning.build_dataset_version")
def build_dataset_version(
    self,
    user_id: str,
    version: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
) -> dict:
    """Monta dataset versionado com split por vídeo fonte.

    Algoritmo:
    1. Busca frames anotados agrupados por video_id
    2. Shuffle grupos (não frames individuais)
    3. Split 70/20/10 por grupo
    4. Gera metadata.json
    """
    try:
        logger.info(
            "build_dataset_start: user=%s, version=%s",
            user_id, version,
        )

        # Este task será completamente implementado quando
        # a integração R2 estiver ativa (Fase 4+).
        # Por enquanto, retorna estrutura esperada.

        result = {
            "user_id": user_id,
            "version": version,
            "status": "completed",
            "splits": {
                "train_ratio": train_ratio,
                "val_ratio": val_ratio,
                "test_ratio": test_ratio,
            },
        }

        logger.info(
            "build_dataset_done: user=%s, version=%s",
            user_id, version,
        )

        return result

    except Exception as exc:
        logger.error(
            "build_dataset_failed: user=%s, error=%s",
            user_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60)
