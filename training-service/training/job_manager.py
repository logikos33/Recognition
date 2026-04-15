"""
Job manager para treinamento via Ultralytics Hub.

Fluxo por job:
  1. Download dataset.zip da presigned URL (R2)
  2. Upload dataset para Ultralytics Hub
  3. Criar modelo no Hub (arch + hyperparams)
  4. Disparar cloud training no Hub
  5. Poll status a cada POLL_INTERVAL segundos
  6. Quando completed: baixar best.pt → upload para R2
  7. Publicar conclusão via Redis
"""
import logging
import os
import tempfile
import threading
import time
from typing import Any

import boto3
import requests

from .hub_client import UltralyticsHubClient
from .progress_publisher import ProgressPublisher
from . import config

logger = logging.getLogger(__name__)


def _make_r2() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=config.R2_ENDPOINT,
        aws_access_key_id=config.R2_KEY,
        aws_secret_access_key=config.R2_SECRET,
        region_name="auto",
    )


class JobManager:
    def __init__(self) -> None:
        self._hub: UltralyticsHubClient | None = None
        self._pub = ProgressPublisher()
        self._active: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _get_hub(self) -> UltralyticsHubClient:
        if self._hub is None:
            self._hub = UltralyticsHubClient(config.ULTRALYTICS_HUB_API_KEY)
        return self._hub

    def start_job(self, job_id: str, dataset_url: str) -> dict[str, Any]:
        self._pub.creating_pod(job_id)
        with self._lock:
            self._active[job_id] = {}
        threading.Thread(
            target=self._run,
            args=(job_id, dataset_url),
            daemon=True,
            name=f"hub-{job_id[:8]}",
        ).start()
        return {"job_id": job_id, "status": "running"}

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            entry = self._active.get(job_id)
        if not entry:
            return False
        hub_model_id = entry.get("hub_model_id")
        if hub_model_id:
            try:
                self._get_hub().cancel_training(hub_model_id)
            except Exception as exc:
                logger.warning("cancel_hub_error: job=%s err=%s", job_id, exc)
        self._pub.failed(job_id, "Cancelled by user")
        with self._lock:
            self._active.pop(job_id, None)
        return True

    def active_jobs(self) -> list[str]:
        with self._lock:
            return list(self._active.keys())

    # ------------------------------------------------------------------ #
    # Pipeline interno                                                      #
    # ------------------------------------------------------------------ #

    def _run(self, job_id: str, dataset_url: str) -> None:
        """Thread principal: download → Hub upload → treino → R2 upload."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                hub = self._get_hub()

                # 1. Download dataset zip da presigned URL
                zip_path = os.path.join(tmpdir, f"{job_id}.zip")
                _download_url(dataset_url, zip_path)
                logger.info("hub_dataset_downloaded: job=%s size_kb=%d",
                            job_id, os.path.getsize(zip_path) // 1024)

                # 2. Upload para Ultralytics Hub
                dataset_id = hub.upload_dataset(zip_path, name=f"epi-{job_id[:8]}")

                # 3. Criar modelo no Hub
                model_id = hub.create_model(
                    name=f"epi-{job_id[:8]}",
                    dataset_id=dataset_id,
                    arch=config.TRAINING_MODEL_ARCH,
                    epochs=config.TRAINING_EPOCHS,
                    imgsz=config.TRAINING_IMG_SIZE,
                    batch=config.TRAINING_BATCH_SIZE,
                )
                with self._lock:
                    self._active[job_id] = {
                        "hub_model_id": model_id,
                        "hub_dataset_id": dataset_id,
                    }

                # 4. Disparar cloud training
                hub.start_training(model_id)

                # 5. Poll até concluir
                self._poll(job_id, model_id, tmpdir)

        except Exception as exc:
            logger.error("hub_run_failed: job=%s err=%s", job_id, exc, exc_info=True)
            self._pub.failed(job_id, str(exc)[:500])
            with self._lock:
                self._active.pop(job_id, None)

    def _poll(self, job_id: str, model_id: str, tmpdir: str) -> None:
        """Faz polling no Hub até completed/failed, depois baixa e sobe modelo ao R2."""
        while True:
            with self._lock:
                if job_id not in self._active:
                    return  # cancelado externamente

            try:
                s = self._get_hub().get_model_status(model_id)
                status = s["status"]

                if status == "completed":
                    # Baixar pesos do Hub
                    weights_path = os.path.join(tmpdir, "best.pt")
                    self._get_hub().download_weights(model_id, weights_path)

                    # Subir para R2
                    r2_key = _upload_to_r2(weights_path, job_id)

                    self._pub.completed(job_id, r2_key, s["metrics"])
                    with self._lock:
                        self._active.pop(job_id, None)
                    return

                elif status == "failed":
                    self._pub.failed(job_id, "Hub training failed")
                    with self._lock:
                        self._active.pop(job_id, None)
                    return

                else:
                    self._pub.training(
                        job_id,
                        s["epoch"],
                        config.TRAINING_EPOCHS,
                        s["metrics"].get("loss"),
                    )

            except Exception as exc:
                logger.error("hub_poll_error: job=%s err=%s", job_id, exc)

            time.sleep(config.POLL_INTERVAL)


# ------------------------------------------------------------------ #
# Helpers de I/O                                                        #
# ------------------------------------------------------------------ #

def _download_url(url: str, dest: str) -> None:
    """Baixa arquivo de URL HTTP para dest."""
    r = requests.get(url, timeout=300, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as fh:
        for chunk in r.iter_content(chunk_size=32768):
            fh.write(chunk)


def _upload_to_r2(weights_path: str, job_id: str) -> str:
    """Faz upload de best.pt para R2. Retorna a R2 key."""
    r2_key = f"models/{job_id}/best.pt"
    s3 = _make_r2()
    s3.upload_file(weights_path, config.R2_BUCKET, r2_key)
    logger.info("hub_model_uploaded_r2: job=%s key=%s", job_id, r2_key)
    return r2_key
