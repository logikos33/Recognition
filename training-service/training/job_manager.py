import logging
import threading
import time
from typing import Any

from .progress_publisher import ProgressPublisher
from .runpod_client import RunPodClient
from . import config

logger = logging.getLogger(__name__)


class JobManager:
    def __init__(self) -> None:
        self._runpod = RunPodClient()
        self._pub = ProgressPublisher()
        self._active: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start_job(self, job_id: str, dataset_url: str) -> dict[str, Any]:
        self._pub.creating_pod(job_id)
        result = self._runpod.start_job(job_id, dataset_url)
        runpod_id = result.get("id", "")
        with self._lock:
            self._active[job_id] = {"runpod_id": runpod_id}
        threading.Thread(target=self._poll, args=(job_id, runpod_id),
                         daemon=True, name=f"poll-{job_id[:8]}").start()
        return {"job_id": job_id, "runpod_id": runpod_id, "status": "running"}

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            entry = self._active.get(job_id)
        if not entry:
            return False
        ok = self._runpod.cancel_job(entry["runpod_id"])
        if ok:
            self._pub.failed(job_id, "Cancelled by user")
            with self._lock:
                self._active.pop(job_id, None)
        return ok

    def active_jobs(self) -> list[str]:
        with self._lock:
            return list(self._active.keys())

    def _poll(self, job_id: str, runpod_id: str) -> None:
        while True:
            with self._lock:
                if job_id not in self._active:
                    return
            try:
                s = self._runpod.get_status(runpod_id)
                state = s.get("status", "")
                if state == "COMPLETED":
                    out = s.get("output", {})
                    self._pub.completed(job_id, out.get("model_key", ""), out.get("metrics", {}))
                    with self._lock:
                        self._active.pop(job_id, None)
                    return
                elif state == "FAILED":
                    self._pub.failed(job_id, s.get("error", "failed"))
                    with self._lock:
                        self._active.pop(job_id, None)
                    return
                elif state == "IN_PROGRESS":
                    out = s.get("output", {})
                    self._pub.training(job_id, out.get("epoch", 0), config.TRAINING_EPOCHS, out.get("loss"))
            except Exception as exc:
                logger.error("poll_error: job=%s err=%s", job_id, exc)
            time.sleep(config.POLL_INTERVAL)
