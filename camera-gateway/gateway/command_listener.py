"""
Assina o canal Redis 'gateway:commands' e despacha para StreamManager.

Comandos suportados:
  {action: "start_stream", camera_id, rtsp_url, hls_segment_time?, hls_list_size?}
  {action: "stop_stream",  camera_id}
  {action: "ping"}
"""
import json
import logging
import time

from .redis_client import make_redis
from .stream_manager import StreamManager

logger = logging.getLogger(__name__)

_CHANNEL = "gateway:commands"


class CommandListener:
    """Escuta comandos Redis e despacha para o StreamManager."""

    def __init__(self, stream_manager: StreamManager) -> None:
        self._mgr = stream_manager
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        """Loop principal com reconexão exponencial (padrão worker_server.py)."""
        backoff = 2.0
        while self._running:
            pubsub = None
            try:
                r = make_redis(for_subscribe=True)
                pubsub = r.pubsub()
                pubsub.subscribe(_CHANNEL)
                logger.info("command_listener_subscribed: channel=%s", _CHANNEL)
                backoff = 2.0
                for msg in pubsub.listen():
                    if not self._running:
                        return
                    if msg.get("type") != "message":
                        continue
                    try:
                        self._handle(json.loads(msg["data"]))
                    except Exception as exc:
                        logger.warning("command_handle_error: %s", exc)
            except Exception as exc:
                logger.error(
                    "command_listener_error: err=%s reconnect_in=%.0fs", exc, backoff
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
            finally:
                if pubsub is not None:
                    try:
                        pubsub.close()
                    except Exception:
                        pass

    def _handle(self, cmd: dict) -> None:
        action = cmd.get("action")
        if action == "start_stream":
            camera_id = cmd.get("camera_id", "")
            rtsp_url = cmd.get("rtsp_url", "")
            if camera_id and rtsp_url:
                self._mgr.start_stream(camera_id, rtsp_url, cmd)
            else:
                logger.warning("start_stream_missing_fields: %s", cmd)
        elif action == "stop_stream":
            camera_id = cmd.get("camera_id", "")
            if camera_id:
                self._mgr.stop_stream(camera_id)
        elif action == "ping":
            logger.info("gateway_ping_received")
        else:
            logger.warning("unknown_command: action=%s", action)
