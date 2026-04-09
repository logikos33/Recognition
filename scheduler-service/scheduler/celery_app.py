from celery import Celery
from celery.schedules import crontab
from . import config

celery = Celery(
    "scheduler",
    broker=config.REDIS_URL,
    backend=config.REDIS_URL,
    include=["scheduler.tasks"],
)

celery.conf.beat_schedule = {
    "cleanup-old-alerts": {
        "task": "scheduler.tasks.cleanup_old_alerts",
        "schedule": crontab(hour=3, minute=0),
    },
    "cleanup-old-frames": {
        "task": "scheduler.tasks.cleanup_old_frames",
        "schedule": crontab(hour=4, minute=0),
    },
    "check-cameras-health": {
        "task": "scheduler.tasks.check_cameras_health",
        "schedule": crontab(minute="*/5"),
    },
}

celery.conf.timezone = "America/Sao_Paulo"
celery.conf.task_serializer = "json"
celery.conf.result_serializer = "json"
celery.conf.accept_content = ["json"]
