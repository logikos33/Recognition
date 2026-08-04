"""`python -m app.live_view` — live view via push do edge (LV-2).

Unit systemd --user própria (deploy/edge-live-view.service) — ver
live_view_loop.py pra por que é processo separado do daemon principal.

Env: RECORDER_* (mesmo do daemon/coletor — protocolo/host/credenciais/
channel_map), EDGE_API_URL, EDGE_DEVICE_KEY_PATH (identidade já enrolada; o
device precisa do escopo `stream:write`), LIVE_VIEW_* (ver
build_live_view_loop_from_env).
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from types import FrameType

from ..auth.token_manager import TokenManagerError, build_token_manager_from_env
from ..recorder_client import RecorderError
from ..recorder_factory import build_recorder_client_from_env, validate_onvif_boot_or_raise
from .live_view_loop import build_live_view_loop_from_env

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        token_manager = build_token_manager_from_env()
    except TokenManagerError as exc:
        logger.error(
            "live_view_no_identity %s — device precisa estar enrolado antes do live view", exc
        )
        return 2
    if not token_manager.has_valid_identity():
        logger.error("live_view_no_identity: device ainda não enrolado — nada a fazer")
        return 2

    try:
        recorder = build_recorder_client_from_env()
        # RECORDER_PROTOCOL=onvif: one auth-liveness check now, at boot — not
        # a retry loop (anti-lockout). No-op for any other protocol.
        validate_onvif_boot_or_raise(recorder)
        loop = build_live_view_loop_from_env(recorder, token_manager)
    except (RecorderError, ValueError) as exc:
        logger.error("live_view_config_error %s", exc)
        return 2

    stop_event = threading.Event()

    def _handle_signal(signum: int, frame: FrameType | None) -> None:
        logger.info("live_view_shutdown_signal signum=%s", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("live_view_starting cameras=%s", loop.camera_ids)
    loop.run(stop_event)
    logger.info("live_view_stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
