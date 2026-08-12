"""Handlers dos comandos `monitoring.*` — executados pelo command_poller.

O canal é o outbound que JÁ existe (GET /edge/commands/pending + PATCH de
resultado — ADR-0020: nada inbound, nada de porta nova). A nuvem enfileira
`monitoring.query`/`monitoring.snapshot`/`monitoring.logtail`; o box responde
com a janela pedida do ring buffer local, ou o tail de log JÁ REDIGIDO.

Zero egress sem acesso: nenhum handler roda sem um comando enfileirado, e
comando só existe quando a página /monitoring está aberta pedindo.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from ..redact import redact_url_credentials
from .store import MetricsReader

logger = logging.getLogger(__name__)

_MAX_LOG_LINES = 500
_MAX_LOG_BYTES = 64 * 1024
_DEFAULT_DB_PATH = str(Path.home() / "edge-telemetry" / "metrics.db")

COMMAND_PREFIX = "monitoring."


def default_log_registry() -> dict[str, list[Path]]:
    """unit → candidatos de arquivo de log (whitelist FECHADA — logtail nunca
    lê path vindo do payload; o payload só escolhe uma CHAVE daqui)."""
    home = Path.home()
    return {
        "edge-live-view": [home / "logs" / "edge-live-view.log"],
        "edge-sync-agent": [home / "logs" / "edge-sync-agent.log"],
        "edge-frame-collector": [
            home / "logs" / "edge-frame-collector.log",
            home / "recognition" / "logs" / "frame-collector.log",
        ],
        "edge-monitoring-collector": [home / "logs" / "edge-monitoring-collector.log"],
    }


def tail_lines(
    path: Path, max_lines: int, max_bytes: int = _MAX_LOG_BYTES
) -> tuple[list[str], bool]:
    """Últimas `max_lines` linhas lendo só o FIM do arquivo (seek, nunca o
    arquivo inteiro — o log da live view passa de 20MB). Devolve
    (linhas, truncado_por_teto_de_bytes)."""
    size = path.stat().st_size
    read_from = max(0, size - max_bytes)
    with path.open("rb") as fh:
        fh.seek(read_from)
        raw = fh.read(max_bytes)
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if read_from > 0 and lines:
        lines = lines[1:]  # primeira linha provavelmente cortada no meio
    truncated = read_from > 0 and len(lines) <= max_lines
    return lines[-max_lines:], truncated or len(lines) > max_lines


class MonitoringCommandHandler:
    """Despacho dos `monitoring.*`. Nunca levanta para fora de `handle` —
    erro vira dict de falha e o poller faz ack failed (fila nunca entope)."""

    def __init__(
        self,
        db_path: str | Path = _DEFAULT_DB_PATH,
        *,
        log_registry: dict[str, list[Path]] | None = None,
    ) -> None:
        self._reader = MetricsReader(db_path)
        self._log_registry = log_registry if log_registry is not None else default_log_registry()

    def can_handle(self, command_type: str) -> bool:
        return isinstance(command_type, str) and command_type.startswith(COMMAND_PREFIX)

    def handle(self, command_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Executa e devolve o result do ack. Levanta ValueError para payload
        inválido (o poller acka failed com a razão)."""
        if command_type == "monitoring.query":
            return self._query(payload)
        if command_type == "monitoring.snapshot":
            return self._snapshot()
        if command_type == "monitoring.logtail":
            return self._logtail(payload)
        raise ValueError(f"comando de monitoramento desconhecido: {command_type!r}")

    # ── comandos ─────────────────────────────────────────────────────────────

    def _base(self) -> dict[str, Any]:
        return {
            "schema": 1,
            "device_ts": int(time.time()),
            "collector": self._reader.status(),
        }

    def _query(self, payload: dict[str, Any]) -> dict[str, Any]:
        window = str(payload.get("window") or "2h")
        max_points = int(payload.get("max_points") or 360)
        result = self._base()
        if not self._reader.available():
            # Coletor nunca rodou/DB ausente: responde MESMO ASSIM — a página
            # precisa dizer "coletor parado", não ficar sem resposta.
            result.update({"samples": [], "events": [], "resolution": None, "window": window})
            return result
        result.update(self._reader.query(window, max_points=max_points))
        return result

    def _snapshot(self) -> dict[str, Any]:
        result = self._base()
        latest = self._reader.latest() if self._reader.available() else None
        result["samples"] = [latest] if latest else []
        result["events"] = []
        result["resolution"] = "10s"
        return result

    def _logtail(self, payload: dict[str, Any]) -> dict[str, Any]:
        unit = str(payload.get("unit") or "")
        lines_wanted = max(1, min(int(payload.get("lines") or 200), _MAX_LOG_LINES))
        candidates = self._log_registry.get(unit)
        if not candidates:
            raise ValueError(
                f"unit fora da whitelist de logtail: {unit!r} "
                f"(válidas: {sorted(self._log_registry)})"
            )
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            return {
                **self._base(),
                "unit": unit,
                "path": None,
                "lines": [],
                "truncated": False,
                "reason": "arquivo de log não existe no box",
            }
        try:
            raw_lines, truncated = tail_lines(path, lines_wanted)
        except OSError as exc:
            raise ValueError(f"falha lendo log de {unit}: {exc}") from exc
        # 🔴 Redação NO BOX, antes de qualquer byte sair (credencial de câmera
        # vive nesses logs — o ffmpeg ecoa a URL RTSP inteira ao falhar).
        redacted = [redact_url_credentials(line) for line in raw_lines]
        return {
            **self._base(),
            "unit": unit,
            "path": str(path),
            "lines": redacted,
            "truncated": truncated,
        }


def build_monitoring_handler_from_env(
    env: dict[str, str] | None = None,
) -> MonitoringCommandHandler:
    source = env if env is not None else os.environ
    db_path = source.get("EDGE_MONITORING_DB_PATH") or _DEFAULT_DB_PATH
    return MonitoringCommandHandler(db_path)
