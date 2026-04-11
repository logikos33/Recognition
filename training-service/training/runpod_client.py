import logging
import time
from typing import Any

import requests

from . import config

logger = logging.getLogger(__name__)
_BASE = "https://api.runpod.io/v2"


class RunPodClient:
    def __init__(self) -> None:
        self._hdrs = {
            "Authorization": f"Bearer {config.RUNPOD_API_KEY}",
            "Content-Type": "application/json",
        }
        self._failures = 0
        self._open_until = 0.0

    def _circuit_ok(self) -> bool:
        return not (self._failures >= 3 and time.time() < self._open_until)

    def start_job(self, job_id: str, dataset_url: str) -> dict[str, Any]:
        if not self._circuit_ok():
            raise RuntimeError("RunPod circuit OPEN")
        if not config.RUNPOD_ENDPOINT_ID:
            raise ValueError("RUNPOD_ENDPOINT_ID not set")
        payload = {"input": {
            "job_id": job_id, "dataset_url": dataset_url,
            "epochs": config.TRAINING_EPOCHS, "batch_size": config.TRAINING_BATCH_SIZE,
            "img_size": config.TRAINING_IMG_SIZE, "r2_endpoint": config.R2_ENDPOINT,
            "r2_bucket": config.R2_BUCKET, "r2_key": config.R2_KEY, "r2_secret": config.R2_SECRET,
        }}
        try:
            r = requests.post(f"{_BASE}/{config.RUNPOD_ENDPOINT_ID}/run",
                              headers=self._hdrs, json=payload, timeout=30)
            r.raise_for_status()
            self._failures = 0
            return r.json()
        except Exception as exc:
            self._failures += 1
            if self._failures >= 3:
                self._open_until = time.time() + 60
            raise RuntimeError(f"RunPod failed: {exc}") from exc

    def get_status(self, runpod_id: str) -> dict[str, Any]:
        r = requests.get(f"{_BASE}/{config.RUNPOD_ENDPOINT_ID}/status/{runpod_id}",
                         headers=self._hdrs, timeout=10)
        r.raise_for_status()
        return r.json()

    def cancel_job(self, runpod_id: str) -> bool:
        try:
            r = requests.post(f"{_BASE}/{config.RUNPOD_ENDPOINT_ID}/cancel/{runpod_id}",
                              headers=self._hdrs, timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    def start_pod(self, pod_id: str) -> bool:
        try:
            r = requests.post(f"https://api.runpod.io/v2/pod/{pod_id}/start",
                              headers=self._hdrs, timeout=30)
            r.raise_for_status()
            logger.info("runpod_pod_started: pod_id=%s", pod_id)
            return True
        except Exception as exc:
            logger.warning("runpod_pod_start_failed: pod_id=%s err=%s", pod_id, exc)
            return False

    def stop_pod(self, pod_id: str) -> bool:
        try:
            r = requests.post(f"https://api.runpod.io/v2/pod/{pod_id}/stop",
                              headers=self._hdrs, timeout=30)
            r.raise_for_status()
            logger.info("runpod_pod_stopped: pod_id=%s", pod_id)
            return True
        except Exception as exc:
            logger.warning("runpod_pod_stop_failed: pod_id=%s err=%s", pod_id, exc)
            return False
