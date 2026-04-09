import logging
import signal
import sys
from .app import app
from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _startup() -> None:
    try:
        from .db import _get_pool
        _get_pool()
        logger.info("auth_db_ok")
    except Exception as exc:
        logger.error("auth_db_fail: %s", exc)
        sys.exit(1)
    logger.info("auth_ready: port=%d", config.PORT)


_startup()
signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, use_reloader=False)
