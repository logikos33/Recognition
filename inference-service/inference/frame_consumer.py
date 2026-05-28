"""
Consome frames do Redis via psubscribe("frame:*").

Padrão idêntico ao socket_bridge._bridge_loop() da API-V2:
- psubscribe com socket_timeout=None
- backoff exponencial em reconexão
- filtra msg["type"] == "pmessage"
- extrai camera_id do nome do canal

Canal de entrada: frame:{camera_id}
  {camera_id, frame_b64, timestamp}
"""
import json
import logging
import time

from .inference_engine import InferenceEngine
from .redis_client import make_redis

logger = logging.getLogger(__name__)

_PATTERN = "frame:*"


class FrameConsumer:
    """Assina frame:* e despacha para InferenceEngine."""

    def __init__(self, engine: InferenceEngine) -> None:
        self._engine = engine
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        """Loop principal com reconexão exponencial."""
        backoff = 2.0
        while self._running:
            pubsub = None
            try:
                r = make_redis(for_subscribe=True)
                pubsub = r.pubsub()
                pubsub.psubscribe(_PATTERN)
                logger.info("frame_consumer_subscribed: pattern=%s", _PATTERN)
                backoff = 2.0
                for msg in pubsub.listen():
                    if not self._running:
                        return
                    if msg.get("type") != "pmessage":
                        continue
                    try:
                        channel = msg["channel"]
                        if isinstance(channel, bytes):
                            channel = channel.decode()
                        camera_id = channel.split(":", 1)[1]
                        data = json.loads(msg["data"])
                        self._engine.process_frame(
                            camera_id=camera_id,
                            frame_b64=data["frame_b64"],
                            timestamp=data.get("timestamp", ""),
                        )
                    except Exception as exc:
                        logger.warning("frame_consumer_msg_error: %s", exc)
            except Exception as exc:
                logger.error(
                    "frame_consumer_error: err=%s reconnect_in=%.0fs", exc, backoff
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
            finally:
                if pubsub is not None:
                    try:
                        pubsub.close()
                    except Exception:
                        pass
