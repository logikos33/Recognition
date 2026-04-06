"""
EPI Monitor V2 — Celery Factory.

Celery integrado ao contexto Flask via make_celery().
Entry point do worker: celery -A app.infrastructure.queue.celery_app:celery worker
"""
import logging
import os

from celery import Celery

logger = logging.getLogger(__name__)


def make_celery(app: object | None = None) -> Celery:
    """Cria instância Celery configurada.

    Se app Flask fornecido, integra com app context.
    Caso contrário, cria standalone (para worker).
    """
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    celery = Celery(
        "epi_monitor",
        broker=redis_url,
        backend=redis_url,
    )

    celery.conf.update(
        # Serialização
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        # Confiabilidade
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        # Cleanup
        worker_max_tasks_per_child=100,
        # Timezone
        timezone="UTC",
        enable_utc=True,
        # Rotas por fila
        task_routes={
            "app.infrastructure.queue.tasks.extraction.*": {"queue": "extraction"},
            "app.infrastructure.queue.tasks.quality.*": {"queue": "extraction"},
            "app.infrastructure.queue.tasks.versioning.*": {"queue": "versioning"},
            "app.infrastructure.queue.tasks.training.*": {"queue": "training"},
            "app.infrastructure.queue.tasks.inference.*": {"queue": "inference"},
        },
    )

    # Integrar com Flask app context se disponível
    if app is not None:
        class ContextTask(celery.Task):  # type: ignore[name-defined]
            abstract = True

            def __call__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                with app.app_context():  # type: ignore[union-attr]
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask

    logger.info("celery_configured: broker=%s", redis_url[:30])
    return celery


# Standalone celery instance para o worker
celery = make_celery()
