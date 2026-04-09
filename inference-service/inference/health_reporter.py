"""
Publica a chave 'service:inference:health' no Redis periodicamente.

A API-V2 usa a existência dessa chave (com TTL) para saber se o
inference-service está online.
"""
import json
import logging
import time

from .inference_engine import InferenceEngine
from .redis_client import make_redis
from . import config

logger = logging.getLogger(__name__)

_KEY = "service:inference:health"


class HealthReporter:
    """Thread daemon que mantém a chave de health no Redis."""

    def __init__(self, engine: InferenceEngine) -> None:
        self._engine = engine
        self._running = True
        self._r = make_redis()

    def stop(self) -> None:
        self._running = False
        try:
            self._r.delete(_KEY)
        except Exception:
            pass

    def run(self) -> None:
        while self._running:
            try:
                payload = {
                    "inference_id": config.INFERENCE_ID,
                    "status": "online",
                    "model": config.YOLO_MODEL_PATH,
                    "ready": self._engine.is_ready(),
                    "frames_processed": self._engine.frames_processed,
                    "ts": time.time(),
                }
                self._r.setex(_KEY, config.HEALTH_TTL, json.dumps(payload))
            except Exception as exc:
                logger.error("health_reporter_error: %s", exc)
            time.sleep(config.HEALTH_INTERVAL)
