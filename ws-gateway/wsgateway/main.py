"""Entrypoint do WS Gateway.

eventlet.monkey_patch() DEVE ser chamado antes de qualquer outro import
para que sockets e threads sejam patched corretamente.
"""
import eventlet
eventlet.monkey_patch()  # noqa: E402 — deve ser primeiro

import logging  # noqa: E402
import signal   # noqa: E402
import sys      # noqa: E402

from .app import app, socketio  # noqa: E402
from .bridge import RedisBridge  # noqa: E402
from .redis_client import make_redis  # noqa: E402
from . import config  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

bridge = RedisBridge(socketio)


def _startup() -> None:
    """Verifica Redis e inicia bridge. Não chama sys.exit para compatibilidade com gunicorn."""
    try:
        make_redis().ping()
        logger.info("ws_gateway_redis_ok")
    except Exception as exc:
        logger.warning("ws_gateway_redis_unavailable: %s -- bridge will retry", exc)
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
