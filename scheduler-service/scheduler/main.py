import logging
import os
import signal
import subprocess
import sys
import threading

from .app import app
from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_proc: subprocess.Popen | None = None


def _start_beat() -> None:
    global _proc
    cmd = [sys.executable, "-m", "celery",
           "-A", "scheduler.celery_app:celery",
           "worker", "--beat", "--loglevel=info", "--concurrency=1"]
    _proc = subprocess.Popen(cmd, cwd="/app")
    logger.info("beat_started: pid=%d", _proc.pid)
    _proc.wait()
    logger.warning("beat_exited")


def _shutdown(sig, frame):  # noqa: ANN001
    if _proc and _proc.poll() is None:
        _proc.terminate()
    sys.exit(0)


signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)

threading.Thread(target=_start_beat, daemon=True, name="celery-beat").start()
logger.info("scheduler_ready: port=%d", config.PORT)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, use_reloader=False)
