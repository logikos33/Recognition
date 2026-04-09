"""
Entrypoint do Camera Gateway.

Inicia:
  1. HealthReporter  — thread daemon, publica service:gateway:health
  2. CommandListener — thread daemon, assina gateway:commands
  3. Flask app       — thread principal (blocking), serve /health

Shutdown gracioso via SIGTERM/SIGINT.
"""
import logging
import os
import signal
import sys
import threading

from .app import app
from .command_listener import CommandListener
from .health_reporter import HealthReporter
from .redis_client import make_redis
from .stream_manager import StreamManager
from . import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    # Verifica Redis antes de iniciar
    r = make_redis()
    try:
        r.ping()
        logger.info("gateway_redis_ok")
    except Exception as exc:
        logger.error("gateway_redis_unreachable: %s", exc)
        sys.exit(1)

    mgr = StreamManager()
    reporter = HealthReporter(mgr)
    listener = CommandListener(mgr)

    # Inicia threads daemon
    threading.Thread(target=reporter.run, daemon=True, name="health-reporter").start()
    threading.Thread(target=listener.run, daemon=True, name="cmd-listener").start()

    def _shutdown(sig, frame):  # noqa: ANN001
        logger.info("gateway_shutdown_signal: sig=%d", sig)
        reporter.stop()
        for cam_id in mgr.active_camera_ids():
            mgr.stop_stream(cam_id)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("gateway_starting: port=%d", config.PORT)
    # Flask bloqueia a thread principal (mantém o processo vivo)
    app.run(host="0.0.0.0", port=config.PORT, use_reloader=False)


if __name__ == "__main__":
    main()
