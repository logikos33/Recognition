"""`python -m app.monitoring` — o coletor de monitoramento do box.

Unit systemd --user própria (deploy/edge-monitoring-collector.service), com
teto de recurso e linger, reciclada pelo OTA junto das outras (roda do
symlink `current`). Substitui o antigo `python -m app.telemetry` como coletor
residente: em vez de JSONL sem teto (chegou a 230MB no box), grava no ring
buffer SQLite com downsample e retenção (store.py).

Custo-alvo: ~1% de CPU. O tegrastats roda em modo CONTÍNUO (um processo, uma
linha por amostra — ⛔ nunca um fork por amostra); os demais leitores são
open/read de /sys//proc (baratíssimos) + UM systemctl show por tick + UM
nvpmodel e UM ping ao gateway local por minuto.

Sem rede: este processo NUNCA abre conexão com a nuvem. Quem responde à
página é o edge-sync-agent, lendo o mesmo SQLite em read-only quando um
comando `monitoring.*` chega pelo canal outbound.

Env (todos opcionais):
  EDGE_MONITORING_DB_PATH        default ~/edge-telemetry/metrics.db
  EDGE_MONITORING_STATE_DIR      default ~/.local/state/recognition/monitoring
  EDGE_MONITORING_INTERVAL_S     default 10
  EDGE_MONITORING_UNITS          default edge-sync-agent,edge-live-view,
                                 edge-frame-collector,edge-monitoring-collector,
                                 edge-sync-agent-updater
  EDGE_MONITORING_NIC            default enP8p1s0
  EDGE_MONITORING_MIN_FREE_GB    default 8 (guarda: perto disso, para de gravar)
  EDGE_MONITORING_MAX_DB_MB      default 64
  COLLECTOR_STATE_PATH           (o mesmo do frame-collector) p/ camada coleta
  OTA_CURRENT_SYMLINK, OTA_CHANNEL, EDGE_VERSION — camada versões
  TEGRASTATS_INTERVAL_MS         default 10000
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from types import FrameType

from ..collector.collector_state import DEFAULT_STATE_PATH as COLLECTOR_DEFAULT_STATE_PATH
from ..logging_setup import install_redacted_logging
from ..telemetry.collector import tegrastats_source
from ..telemetry.tegrastats_parser import parse_tegrastats_line
from .sampler import DEFAULT_UNITS, MonitoringSampler
from .status_file import (
    DEFAULT_STATE_DIR,
    INFERENCE_STATUS_FILENAME,
    LIVE_VIEW_STATUS_FILENAME,
    NET_STATUS_FILENAME,
)
from .store import MetricsStore

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL_S = 10.0
_MAINTAIN_EVERY_S = 60.0


def _tegrastats_thread(
    sampler: MonitoringSampler, interval_ms: int, stop_event: threading.Event
) -> None:
    """Consome o tegrastats contínuo e mantém a última amostra no sampler.
    Se o binário sumir (off-Jetson), loga e desiste — as demais camadas
    continuam (regra de honestidade: hw fica parcial, nunca inventado)."""
    while not stop_event.is_set():
        try:
            for line in tegrastats_source(interval_ms):
                if stop_event.is_set():
                    return
                sample = parse_tegrastats_line(line)
                if sample.ram_total_mb is not None or sample.temps_c:
                    sampler.update_tegra(sample)
        except FileNotFoundError:
            logger.warning("tegrastats indisponível — camada hw ficará parcial")
            return
        except Exception as exc:
            logger.warning("tegrastats_reiniciando err=%s", exc)
            stop_event.wait(timeout=10.0)


def main() -> int:
    install_redacted_logging()
    env = os.environ

    db_path = env.get("EDGE_MONITORING_DB_PATH") or str(
        Path.home() / "edge-telemetry" / "metrics.db"
    )
    state_dir = Path(env.get("EDGE_MONITORING_STATE_DIR") or DEFAULT_STATE_DIR)
    interval_s = float(env.get("EDGE_MONITORING_INTERVAL_S", str(_DEFAULT_INTERVAL_S)))
    units_raw = env.get("EDGE_MONITORING_UNITS")
    units = (
        [u.strip() for u in units_raw.split(",") if u.strip()]
        if units_raw
        else list(DEFAULT_UNITS)
    )
    nic = env.get("EDGE_MONITORING_NIC", "enP8p1s0")
    min_free_gb = float(env.get("EDGE_MONITORING_MIN_FREE_GB", "8"))
    max_db_mb = int(env.get("EDGE_MONITORING_MAX_DB_MB", "64"))
    tegra_interval_ms = int(env.get("TEGRASTATS_INTERVAL_MS", "10000"))

    store = MetricsStore(db_path, max_db_mb=max_db_mb, min_free_gb=min_free_gb)

    def on_event(ts: int, kind: str, detail: str) -> None:
        logger.info("evento kind=%s detail=%s", kind, detail)
        store.insert_event(ts, kind, detail)

    sampler = MonitoringSampler(
        units=units,
        nic=nic,
        live_view_status_path=state_dir / LIVE_VIEW_STATUS_FILENAME,
        net_status_path=state_dir / NET_STATUS_FILENAME,
        inference_status_path=state_dir / INFERENCE_STATUS_FILENAME,
        collector_state_path=env.get("COLLECTOR_STATE_PATH", COLLECTOR_DEFAULT_STATE_PATH),
        ota_current_symlink=env.get(
            "OTA_CURRENT_SYMLINK", str(Path.home() / "recognition" / "current")
        ),
        ota_channel=env.get("OTA_CHANNEL", "dev"),
        edge_version=env.get("EDGE_VERSION") or None,
        disk_min_free_gb=min_free_gb,
        on_event=on_event,
    )

    stop_event = threading.Event()

    def _handle_signal(signum: int, frame: FrameType | None) -> None:
        logger.info("monitoring_shutdown_signal signum=%s", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    tegra_thread = threading.Thread(
        target=_tegrastats_thread,
        args=(sampler, tegra_interval_ms, stop_event),
        name="tegrastats",
        daemon=True,
    )
    tegra_thread.start()

    store.insert_event(int(time.time()), "collector_start", db_path)
    logger.info(
        "monitoring_collector_iniciado db=%s interval=%.0fs units=%s nic=%s",
        db_path, interval_s, ",".join(units), nic,
    )

    last_maintain = 0.0
    while not stop_event.is_set():
        tick_started = time.time()
        try:
            record = sampler.build_sample(tick_started)
            ts = record.pop("ts")
            written = store.insert_sample(ts, record)
            if not written:
                logger.warning("amostra descartada (guarda de disco ativa)")
            if tick_started - last_maintain >= _MAINTAIN_EVERY_S:
                last_maintain = tick_started
                store.maintain(int(tick_started))
        except Exception:
            # Uma amostra ruim não pode matar o coletor — o vazio na série é
            # visível na página (timestamp de coleta), o crash seria invisível.
            logger.exception("tick_falhou")
        elapsed = time.time() - tick_started
        stop_event.wait(timeout=max(0.5, interval_s - elapsed))

    store.close()
    logger.info("monitoring_collector_parado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
