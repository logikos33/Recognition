"""`python -m app.collector` — the motion-triggered continuous frame collector
(Onda 2 shadow-mode pilot, task-093). Its OWN long-running systemd --user
unit (deploy/edge-frame-collector.service) — see collector_loop.py's
docstring for why this is a separate process from main.py's run_daemon().

Env: RECORDER_* (same as main.py/recorder_factory.py — protocol/host/creds/
channel_map), RECORDER_CLOUD_ID (novo — UUID do public.recorders na nuvem),
EDGE_API_URL, EDGE_DEVICE_KEY_PATH (mesma identidade do daemon principal — o
coletor não enrola, só lê a identidade já persistida), COLLECTOR_* (ver
collector_loop.py's build_collector_loop_from_env para defaults/descrição).
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
from types import FrameType

from ..auth.token_manager import TokenManagerError, build_token_manager_from_env
from ..logging_setup import install_redacted_logging
from ..recorder_client import RecorderError
from ..recorder_factory import build_recorder_client_from_env, validate_onvif_boot_or_raise
from .collector_loop import build_collector_loop_from_env, log_configuracao_efetiva
from .collector_state import collection_enabled

logger = logging.getLogger(__name__)


def main() -> int:
    install_redacted_logging()

    # Interruptor-mestre ANTES de qualquer conexão (gravador/nuvem): desligado
    # é desligado — nem RTSP, nem ONVIF, nem token. Persistido no .env, então
    # sobrevive a restart/reboot (D-86: "a cota bateu" em memória não é
    # desligamento; systemctl stop não sobrevive a reboot da unit habilitada).
    # O processo fica vivo e ocioso de propósito: Restart=always transformaria
    # um exit em loop quente de restart, e a unit ficar "active" mantém a
    # telemetria/ops iguais. Religar = COLLECTOR_ENABLED=1 no .env + restart.
    if not collection_enabled():
        stop_event = threading.Event()

        def _handle_signal_idle(signum: int, frame: FrameType | None) -> None:
            logger.info("collector_shutdown_signal signum=%s", signum)
            stop_event.set()

        signal.signal(signal.SIGTERM, _handle_signal_idle)
        signal.signal(signal.SIGINT, _handle_signal_idle)
        logger.warning(
            "coleta DESLIGADA (COLLECTOR_ENABLED=0 no .env) — nenhuma câmera "
            "será capturada; processo ocioso até o próximo restart. Religar: "
            "COLLECTOR_ENABLED=1 + systemctl --user restart edge-frame-collector"
        )
        stop_event.wait()
        logger.info("collector_stopped")
        return 0

    try:
        token_manager = build_token_manager_from_env()
    except TokenManagerError as exc:
        logger.error(
            "collector_no_identity %s — device precisa estar enrolado antes do coletor", exc
        )
        return 2
    if not token_manager.has_valid_identity():
        logger.error("collector_no_identity: device ainda não enrolado — nada a fazer")
        return 2

    try:
        recorder = build_recorder_client_from_env()
        # RECORDER_PROTOCOL=onvif: one auth-liveness check now, at boot — not
        # a retry loop (anti-lockout). No-op for any other protocol.
        validate_onvif_boot_or_raise(recorder)
        loop = build_collector_loop_from_env(recorder, token_manager)
    except (RecorderError, ValueError) as exc:
        logger.error("collector_config_error %s", exc)
        return 2

    stop_event = threading.Event()

    def _handle_signal(signum: int, frame: FrameType | None) -> None:
        logger.info("collector_shutdown_signal signum=%s", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("collector_starting cameras=%s", loop.camera_ids)
    # Antes de rodar: dizer o que a config vai FAZER, e reclamar de config
    # auto-sabotadora. Três paradas silenciosas já custaram uma janela de
    # coleta cada — ver log_configuracao_efetiva.
    log_configuracao_efetiva(loop)
    loop.run(stop_event)
    logger.info("collector_stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
