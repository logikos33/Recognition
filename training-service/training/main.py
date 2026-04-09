import logging
import signal
import sys

from .app import app
from .redis_client import make_redis
from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _startup() -> None:
    try:
        make_redis().ping()
        logger.info("training_redis_ok")
    except Exception as exc:
        logger.error("training_redis_unreachable: %s", exc)
        sys.exit(1)
    logger.info("training_ready: port=%d", config.PORT)


_startup()
signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, use_reloader=False)
