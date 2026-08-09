"""Entrypoint do coletor de telemetria: `python -m app.telemetry`.

Lê configuração de env, coleta `tegrastats` continuamente e grava o dataset
JSONL local. Se `EDGE_API_URL` + `EDGE_DEVICE_BEARER` estiverem setados, também
envia heartbeats à API (canal de observabilidade da frota).

Encerra graciosamente em SIGTERM/SIGINT (systemd `stop` / Ctrl-C) — o processo
`tegrastats` filho é terminado no finally do gerador.

Env:
  EDGE_DEVICE_ID          (obrigatório) id do device (ex.: 'rvb-blumenau-01-orin')
  EDGE_TELEMETRY_PHASE    idle | inference           (default: idle)
  EDGE_TELEMETRY_DIR      diretório dos datasets      (default: ~/edge-telemetry)
  TEGRASTATS_INTERVAL_MS  intervalo de amostragem     (default: 5000)
  TEGRASTATS_BIN          binário do tegrastats       (default: tegrastats)
  EDGE_VERSION            versão do stack edge         (opcional)
  EDGE_API_URL            base da API cloud            (opcional — liga o sink)
  EDGE_DEVICE_BEARER      device token RS256 p/ o sink (opcional)
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from .. import logging_setup
from .collector import (
    HeartbeatSink,
    JsonlWriter,
    TelemetryCollector,
    tegrastats_source,
)

logging_setup.install_redacted_logging()
logger = logging.getLogger("app.telemetry")


def _build_heartbeat_sink(device_id: str, edge_version: str | None) -> HeartbeatSink | None:
    """Liga o sink HTTP só se API_URL + bearer estiverem configurados."""
    api_url = os.environ.get("EDGE_API_URL", "").rstrip("/")
    bearer = os.environ.get("EDGE_DEVICE_BEARER", "")
    if not api_url or not bearer:
        logger.info("heartbeat sink off (sem EDGE_API_URL/EDGE_DEVICE_BEARER) — só JSONL local")
        return None
    try:
        import requests  # dependência opcional; só necessária com o sink ligado
    except ImportError:
        logger.warning("requests indisponível — heartbeat sink desativado")
        return None

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {bearer}"})
    endpoint = f"{api_url}/api/v1/edge/heartbeat"
    logger.info("heartbeat sink ativo → %s", endpoint)
    return HeartbeatSink(session, endpoint, device_id=device_id, edge_version=edge_version)


def main() -> int:
    device_id = os.environ.get("EDGE_DEVICE_ID")
    if not device_id:
        logger.error("EDGE_DEVICE_ID é obrigatório")
        return 2

    phase = os.environ.get("EDGE_TELEMETRY_PHASE", "idle")
    data_dir = Path(os.environ.get("EDGE_TELEMETRY_DIR", "~/edge-telemetry")).expanduser()
    interval_ms = int(os.environ.get("TEGRASTATS_INTERVAL_MS", "5000"))
    binary = os.environ.get("TEGRASTATS_BIN", "tegrastats")
    edge_version = os.environ.get("EDGE_VERSION") or None

    started = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    jsonl_path = data_dir / f"{phase}_{started}.jsonl"
    writer = JsonlWriter(jsonl_path)
    heartbeat_sink = _build_heartbeat_sink(device_id, edge_version)

    try:
        collector = TelemetryCollector(
            device_id=device_id,
            phase=phase,
            jsonl_writer=writer,
            heartbeat_sink=heartbeat_sink,
        )
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    stop_event = threading.Event()

    def _handle_signal(signum, _frame) -> None:
        logger.info("sinal %s recebido — encerrando coleta", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info(
        "coletando: device=%s phase=%s interval=%dms → %s",
        device_id, phase, interval_ms, jsonl_path,
    )
    source = tegrastats_source(interval_ms, binary=binary)
    try:
        collector.run(source, stop_event=stop_event)
    except FileNotFoundError:
        logger.error("binário '%s' não encontrado — este coletor roda no Jetson", binary)
        return 1
    logger.info("coleta encerrada. dataset: %s", jsonl_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
