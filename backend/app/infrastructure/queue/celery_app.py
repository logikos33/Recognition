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
        include=[
            "app.infrastructure.queue.tasks.extraction",
            "app.infrastructure.queue.tasks.quality",
            "app.infrastructure.queue.tasks.versioning",
            "app.infrastructure.queue.tasks.inference",
            "app.infrastructure.queue.tasks.training",
            "app.infrastructure.queue.tasks.verification",
            # Módulo de Qualidade Industrial — filas dedicadas e isoladas
            "app.infrastructure.queue.tasks.quality_recording",
            "app.infrastructure.queue.tasks.quality_clips",
            "app.infrastructure.queue.tasks.quality_annotation",
            "app.infrastructure.queue.tasks.quality_training",
            "app.infrastructure.queue.tasks.quality_inference",
            "app.infrastructure.queue.tasks.quality_cep",
        ],
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
            "app.infrastructure.queue.tasks.verification.*": {"queue": "inference"},
            # Módulo de Qualidade Industrial — filas isoladas
            "app.infrastructure.queue.tasks.quality_recording.*": {"queue": "quality_recording"},
            "app.infrastructure.queue.tasks.quality_clips.*":     {"queue": "quality_clips"},
            "app.infrastructure.queue.tasks.quality_annotation.*": {"queue": "quality_annotation"},
            "app.infrastructure.queue.tasks.quality_training.*":  {"queue": "quality_training"},
            "app.infrastructure.queue.tasks.quality_inference.*": {"queue": "quality_inference"},
            "app.infrastructure.queue.tasks.quality_cep.*":       {"queue": "quality_cep"},
        },
        # Celery Beat — tarefas agendadas do módulo de qualidade
        beat_schedule={
            "quality-cep-baseline": {
                "task": "app.infrastructure.queue.tasks.quality_cep.update_quality_cep_baseline",
                "schedule": 84600,  # diário (23.5h para evitar drift)
                "options": {"queue": "quality_cep"},
            },
            "quality-cleanup-recordings": {
                "task": "app.infrastructure.queue.tasks.quality_cep.cleanup_quality_recordings",
                "schedule": 3600,  # horário
                "options": {"queue": "quality_cep"},
            },
            "quality-cleanup-clips": {
                "task": "app.infrastructure.queue.tasks.quality_cep.cleanup_quality_clips",
                "schedule": 86400,  # diário
                "options": {"queue": "quality_cep"},
            },
            "quality-shift-reports": {
                "task": "app.infrastructure.queue.tasks.quality_cep.generate_shift_reports",
                "schedule": 28800,  # a cada 8h (cobre 06:15, 14:15, 22:15 com margem)
                "options": {"queue": "quality_cep"},
            },
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


# Inicializa DatabasePool em cada worker process (prefork model)
from celery.signals import worker_process_init  # noqa: E402


@worker_process_init.connect
def _init_worker_db(**kwargs):  # type: ignore[no-untyped-def]
    """Chamado em cada forked worker — garante sys.path e inicializa o pool DB."""
    import os as _os  # noqa: PLC0415
    import sys  # noqa: PLC0415

    # celery_app.py está em backend/app/infrastructure/queue/ — sobe 4 níveis para backend/
    _backend = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__)
    ))))
    if _backend not in sys.path:
        sys.path.insert(0, _backend)
        logger.info("worker_syspath_fixed: %s", _backend)

    from app.infrastructure.database.connection import DatabasePool, get_database_url
    db_url = get_database_url()
    if db_url:
        DatabasePool.initialize(db_url, min_conn=1, max_conn=3)
        logger.info("worker_db_pool_initialized")


def get_inference_queue(tenant_schema: str) -> str:
    """
    Retorna a fila de inferência correta para o tenant.

    Se um worker on-premise estiver ativo (heartbeat Redis presente),
    retorna `inference_{tenant_schema}`.
    Caso contrário, retorna `inference` (fila padrão Railway).

    Args:
        tenant_schema: schema do tenant (ex: "rvb")

    Returns:
        Nome da fila Celery a usar para enviar tasks de inferência.
    """
    try:
        from app.infrastructure.queue.worker_registry import get_worker_status
        status = get_worker_status(tenant_schema)
        if status == "onpremise":
            return f"inference_{tenant_schema}"
    except Exception as exc:
        logger.debug("get_inference_queue_error: schema=%s err=%s", tenant_schema, exc)
    return "inference"
