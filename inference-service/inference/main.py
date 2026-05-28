"""
Entrypoint do Inference Service.

Inicia:
  1. InferenceEngine — carrega YOLO (pode demorar ~30s)
  2. HealthReporter  — thread daemon, publica service:inference:health
  3. FrameConsumer   — thread daemon, assina frame:* e processa
  4. Flask app       — thread principal (blocking), serve /health

Shutdown gracioso via SIGTERM/SIGINT.
"""
import logging
import signal
import sys
import threading

from .app import app, set_engine
from .frame_consumer import FrameConsumer
from .health_reporter import HealthReporter
from .inference_engine import InferenceEngine
from .model_watcher import ModelWatcher
from .redis_client import make_redis
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
        logger.info("inference_redis_ok")
    except Exception as exc:
        logger.error("inference_redis_unreachable: %s", exc)
        sys.exit(1)

    # Carrega YOLO (pode demorar — por isso o healthcheckTimeout=300)
    logger.info("inference_loading_model: %s", config.YOLO_MODEL_PATH)
    engine = InferenceEngine()
    set_engine(engine)
    logger.info("inference_model_ready: ready=%s", engine.is_ready())

    reporter = HealthReporter(engine)
    consumer = FrameConsumer(engine)
    watcher = ModelWatcher(engine)

    threading.Thread(target=reporter.run, daemon=True, name="health-reporter").start()
    threading.Thread(target=consumer.run, daemon=True, name="frame-consumer").start()
    threading.Thread(target=watcher.run, daemon=True, name="model-watcher").start()

    def _shutdown(sig, frame):  # noqa: ANN001
        logger.info("inference_shutdown_signal: sig=%d", sig)
        reporter.stop()
        consumer.stop()
        watcher.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("inference_starting: port=%d", config.PORT)
    app.run(host="0.0.0.0", port=config.PORT, use_reloader=False)


if __name__ == "__main__":
    main()
