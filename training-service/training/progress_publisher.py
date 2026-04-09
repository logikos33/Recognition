import json
import logging
from datetime import datetime, timezone

from .redis_client import make_redis

logger = logging.getLogger(__name__)


class ProgressPublisher:
    def __init__(self) -> None:
        self._r = make_redis()

    def _pub(self, job_id: str, payload: dict) -> None:
        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        try:
            self._r.publish(f"training:{job_id}", json.dumps(payload))
        except Exception as exc:
            logger.warning("progress_publish_error: %s", exc)

    def creating_pod(self, job_id: str) -> None:
        self._pub(job_id, {"job_id": job_id, "status": "creating_pod", "progress": 5})

    def training(self, job_id: str, epoch: int, total: int, loss: float | None = None) -> None:
        pct = 10 + int(epoch / max(total, 1) * 80)
        self._pub(job_id, {"job_id": job_id, "status": "training", "epoch": epoch,
                           "total_epochs": total, "loss": loss, "progress": pct})

    def completed(self, job_id: str, model_key: str, metrics: dict) -> None:
        self._pub(job_id, {"job_id": job_id, "status": "completed",
                           "model_key": model_key, "metrics": metrics, "progress": 100})

    def failed(self, job_id: str, error: str) -> None:
        self._pub(job_id, {"job_id": job_id, "status": "failed", "error": error, "progress": 0})
