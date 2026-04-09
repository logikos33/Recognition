"""
Publica a chave 'service:gateway:health' no Redis periodicamente.

A API-V2 usa a existência dessa chave (com TTL) para saber se o
gateway está online. Se o processo morrer, o TTL expira e a chave
desaparece automaticamente.
"""
import json
import logging
import time

from .redis_client import make_redis
from .stream_manager import StreamManager
from . import config

logger = logging.getLogger(__name__)

_KEY = "service:gateway:health"


class HealthReporter:
    """Thread daemon que mantém a chave de health no Redis."""

    def __init__(self, stream_manager: StreamManager) -> None:
        self._mgr = stream_manager
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
                ids = self._mgr.active_camera_ids()
                payload = {
                    "gateway_id": config.GATEWAY_ID,
                    "status": "online",
                    "active_cameras": ids,
                    "active_count": len(ids),
                    "ts": time.time(),
                }
                self._r.setex(_KEY, config.HEALTH_TTL, json.dumps(payload))
            except Exception as exc:
                logger.error("health_reporter_error: %s", exc)
            time.sleep(config.HEALTH_INTERVAL)
