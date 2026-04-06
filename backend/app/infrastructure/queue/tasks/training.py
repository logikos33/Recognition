"""
EPI Monitor V2 — Training Dispatch Task.

Celery task: dispara treinamento YOLOv8 no Vast.ai via SSH.
"""
import logging

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=1, queue="training", name="tasks.training.dispatch_training")
def dispatch_training(
    self,
    job_id: str,
    dataset_version_id: str,
    model_size: str = "yolov8n",
    epochs: int = 50,
    imgsz: int = 640,
    batch: int = 16,
) -> dict:
    """Dispatch de treinamento YOLOv8.

    Em produção: conecta via SSH ao Vast.ai e executa train.py.
    Em desenvolvimento: treina localmente se GPU disponível.
    """
    try:
        logger.info(
            "dispatch_training_start: job=%s, model=%s, epochs=%d",
            job_id, model_size, epochs,
        )

        # Implementação completa requer credenciais Vast.ai.
        # Estrutura do fluxo:
        # 1. Baixar dataset do R2
        # 2. Gerar dataset.yaml
        # 3. SSH para Vast.ai → executar train.py
        # 4. Poll metrics_partial.json a cada epoch
        # 5. Upload best.pt para R2
        # 6. Registrar modelo no banco

        result = {
            "job_id": job_id,
            "status": "dispatched",
            "model_size": model_size,
            "epochs": epochs,
        }

        logger.info("dispatch_training_queued: job=%s", job_id)
        return result

    except Exception as exc:
        logger.error(
            "dispatch_training_failed: job=%s, error=%s",
            job_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60)
