"""
Ultralytics Hub REST client for cloud training.

Autentica via Bearer token, faz upload de dataset, cria modelo,
dispara training e faz polling de status — sem depender do hub-sdk.
"""
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

_HUB_BASE = "https://hub.ultralytics.com/v1"
_TIMEOUT_SHORT = 30
_TIMEOUT_UPLOAD = 300  # dataset zip pode ser grande


class UltralyticsHubClient:
    """Cliente para a REST API do Ultralytics Hub."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("ULTRALYTICS_HUB_API_KEY não configurado")
        self._api_key = api_key
        self._auth = {"Authorization": f"Bearer {api_key}"}

    # ------------------------------------------------------------------ #
    # Primitivas HTTP                                                       #
    # ------------------------------------------------------------------ #

    def _get(self, path: str) -> dict[str, Any]:
        r = requests.get(
            f"{_HUB_BASE}{path}",
            headers=self._auth,
            timeout=_TIMEOUT_SHORT,
        )
        r.raise_for_status()
        return r.json()

    def _post_json(self, path: str, body: dict) -> dict[str, Any]:
        r = requests.post(
            f"{_HUB_BASE}{path}",
            headers={**self._auth, "Content-Type": "application/json"},
            json=body,
            timeout=_TIMEOUT_SHORT,
        )
        r.raise_for_status()
        return r.json()

    def _post_file(self, path: str, file_path: str) -> dict[str, Any]:
        with open(file_path, "rb") as fh:
            r = requests.post(
                f"{_HUB_BASE}{path}",
                headers=self._auth,
                files={"file": (os.path.basename(file_path), fh, "application/zip")},
                timeout=_TIMEOUT_UPLOAD,
            )
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str) -> bool:
        try:
            r = requests.delete(
                f"{_HUB_BASE}{path}",
                headers=self._auth,
                timeout=_TIMEOUT_SHORT,
            )
            return r.status_code in (200, 204)
        except Exception as exc:
            logger.warning("hub_delete_failed: path=%s err=%s", path, exc)
            return False

    # ------------------------------------------------------------------ #
    # Dataset                                                               #
    # ------------------------------------------------------------------ #

    def upload_dataset(self, zip_path: str, name: str) -> str:
        """Cria dataset no Hub e faz upload do zip. Retorna dataset_id."""
        data = self._post_json("/datasets", {
            "meta": {"name": name},
            "data": {"license": "AGPL-3.0"},
        })
        dataset_id = data["data"]["id"]
        logger.info("hub_dataset_created: id=%s name=%s", dataset_id, name)

        self._post_file(f"/datasets/{dataset_id}/upload", zip_path)
        logger.info(
            "hub_dataset_uploaded: id=%s size_kb=%d",
            dataset_id,
            os.path.getsize(zip_path) // 1024,
        )
        return dataset_id

    # ------------------------------------------------------------------ #
    # Model / Training                                                      #
    # ------------------------------------------------------------------ #

    def create_model(
        self,
        name: str,
        dataset_id: str,
        arch: str,
        epochs: int,
        imgsz: int,
        batch: int,
    ) -> str:
        """Cria configuração de modelo no Hub. Retorna model_id."""
        data = self._post_json("/models", {
            "meta": {"name": name},
            "data": {
                "datasetId": dataset_id,
                "modelType": arch,
                "trainArgs": {
                    "epochs": epochs,
                    "batch": batch,
                    "imgsz": imgsz,
                    "task": "detect",
                },
            },
        })
        model_id = data["data"]["id"]
        logger.info("hub_model_created: id=%s arch=%s epochs=%d", model_id, arch, epochs)
        return model_id

    def start_training(self, model_id: str) -> None:
        """Dispara cloud training no Hub para model_id."""
        self._post_json(f"/models/{model_id}/deploy", {})
        logger.info("hub_training_deployed: model_id=%s", model_id)

    def get_model_status(self, model_id: str) -> dict[str, Any]:
        """Retorna status normalizado do modelo.

        Returns:
            {
                status: "pending"|"running"|"completed"|"failed",
                progress: 0-100,
                epoch: int,
                metrics: {mAP50, precision, recall, loss},
                weights_url: str | None,
            }
        """
        data = self._get(f"/models/{model_id}")
        m = data.get("data", {})

        raw = m.get("status", "created")
        status_map = {
            "created": "pending",
            "queued":  "pending",
            "training": "running",
            "trained":  "completed",
            "exported": "completed",
            "failed":   "failed",
            "stopped":  "failed",
            "canceled": "failed",
        }
        status = status_map.get(raw, "running")

        epochs_total = (m.get("trainArgs") or {}).get("epochs", 1)
        current_epoch = m.get("epoch", 0)
        if status == "running":
            progress = min(99, int((current_epoch / max(epochs_total, 1)) * 100))
        elif status == "completed":
            progress = 100
        else:
            progress = 0

        raw_m = m.get("metrics") or {}
        metrics = {
            "mAP50":     float(raw_m.get("mAP50",     raw_m.get("map50", 0.0))),
            "precision": float(raw_m.get("precision", raw_m.get("p",     0.0))),
            "recall":    float(raw_m.get("recall",    raw_m.get("r",     0.0))),
            "loss":      float(raw_m.get("loss",      raw_m.get("box_loss", 0.0))),
        }

        weights_url = m.get("weightsUrl") or m.get("url")

        return {
            "status":      status,
            "progress":    progress,
            "epoch":       current_epoch,
            "metrics":     metrics,
            "weights_url": weights_url,
        }

    def cancel_training(self, model_id: str) -> bool:
        """Para training ativo no Hub."""
        ok = self._delete(f"/models/{model_id}/deploy")
        logger.info("hub_training_cancelled: model_id=%s ok=%s", model_id, ok)
        return ok

    def download_weights(self, model_id: str, dest_path: str) -> str:
        """Baixa best.pt do Hub para dest_path. Retorna dest_path."""
        s = self.get_model_status(model_id)
        weights_url = s.get("weights_url")
        if not weights_url:
            raise RuntimeError(f"Sem URL de pesos para model {model_id}")

        r = requests.get(weights_url, timeout=300, stream=True)
        r.raise_for_status()
        with open(dest_path, "wb") as fh:
            for chunk in r.iter_content(chunk_size=32768):
                fh.write(chunk)
        logger.info("hub_weights_downloaded: model_id=%s path=%s", model_id, dest_path)
        return dest_path
