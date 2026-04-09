"""Entrypoint do WS Gateway."""
import logging
import signal
import sys

from .app import app, socketio
from .bridge import RedisBridge
from .redis_client import make_redis
from . import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

bridge = RedisBridge(socketio)


def _startup() -> None:
    r = make_redis()
    try:
        r.ping()
        logger.info("ws_gateway_redis_ok")
    except Exception as exc:
        logger.error("ws_gateway_redis_unreachable: %s", exc)
        sys.exit(1)
    bridge.start()
    logger.info("ws_gateway_ready: port=%d", config.PORT)


_startup()


def _shutdown(sig, frame):  # noqa: ANN001
    bridge.stop()
    sys.exit(0)


signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=config.PORT, use_reloader=False)
