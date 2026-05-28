"""
Inference Service — Model Watcher.

Subscreve Redis channel `model:reload` e faz hot-reload do YOLO
sem reiniciar o serviço. Suporta download de modelos do R2 (boto3)
ou URLs HTTP diretas.

Canal: model:reload
Payload: {"model_path": "<r2-key-ou-url>"}
"""
import json
import logging
import os
import time

from .redis_client import make_redis

logger = logging.getLogger(__name__)

_CACHE_DIR = "/tmp/epi_models"


def _download_from_r2(model_key: str) -> str:
    """Baixa modelo do R2 para /tmp/epi_models/. Retorna path local."""
    import boto3
    from botocore.config import Config

    endpoint = os.environ.get("R2_ENDPOINT", "")
    bucket = os.environ.get("R2_BUCKET", "epi-monitor")
    key_id = os.environ.get("R2_KEY", "")
    secret = os.environ.get("R2_SECRET", "")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        config=Config(signature_version="s3v4"),
    )
    os.makedirs(_CACHE_DIR, exist_ok=True)
    filename = os.path.basename(model_key.rstrip("/")) or "model.pt"
    local_path = os.path.join(_CACHE_DIR, filename)
    logger.info("model_watcher_downloading: key=%s → %s", model_key, local_path)
    s3.download_file(bucket, model_key, local_path)
    logger.info("model_watcher_downloaded: %s (%d bytes)", local_path, os.path.getsize(local_path))
    return local_path


def _download_from_url(url: str) -> str:
    """Baixa modelo via HTTP para /tmp/epi_models/. Retorna path local."""
    import requests

    os.makedirs(_CACHE_DIR, exist_ok=True)
    filename = url.split("/")[-1].split("?")[0] or "model.pt"
    local_path = os.path.join(_CACHE_DIR, filename)
    logger.info("model_watcher_downloading_url: %s → %s", url, local_path)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    logger.info("model_watcher_downloaded: %s", local_path)
    return local_path


def _resolve_model(model_path: str) -> str:
    """Resolve model_path para path local — baixa se necessário."""
    if model_path.startswith("http://") or model_path.startswith("https://"):
        return _download_from_url(model_path)
    if os.path.isfile(model_path):
        return model_path
    # Assume R2 object key
    return _download_from_r2(model_path)


class ModelWatcher:
    """Thread que escuta model:reload e faz hot-reload do engine."""

    def __init__(self, engine) -> None:  # type: ignore[no-untyped-def]
        self._engine = engine
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        backoff = 2
        while self._running:
            try:
                r = make_redis()
                ps = r.pubsub()
                ps.subscribe("model:reload")
                logger.info("model_watcher: subscribed to model:reload")
                backoff = 2

                for message in ps.listen():
                    if not self._running:
                        break
                    if message["type"] != "message":
                        continue
                    try:
                        payload = json.loads(message["data"])
                        model_path = payload.get("model_path", "")
                        if not model_path:
                            logger.warning("model_reload_empty_path")
                            continue
                        local_path = _resolve_model(model_path)
                        self._engine.reload_model(local_path)
                    except Exception as exc:
                        logger.error("model_reload_error: %s", exc)

            except Exception as exc:
                logger.error("model_watcher_failed: %s — retry in %ds", exc, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
