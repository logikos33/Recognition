"""Coletor de telemetria device-side (task-100).

Fluxo: `tegrastats` → parse → registro estruturado → sinks.
Dois sinks compõem:
  - `JsonlWriter`: grava cada amostra como uma linha JSON num arquivo local
    (datasets de baseline idle/inference para o estudo de dimensionamento);
  - `HeartbeatSink` (opcional): mapeia a amostra para o payload `Heartbeat` e
    envia via um `http_client` injetado a `POST /api/v1/edge/heartbeat`.

A fonte de linhas é desacoplada do processamento (`process_line`/`run` aceitam
qualquer iterável), então todo o coletor é testável offline — sem Jetson.

`phase` ('idle' | 'inference') rotula cada amostra: é o eixo do estudo de
baseline (consumo ocioso vs. sob carga de inferência).
"""
from __future__ import annotations

import json
import logging
import subprocess
import threading
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .tegrastats_parser import TegrastatsSample, parse_tegrastats_line

logger = logging.getLogger(__name__)

_VALID_PHASES = frozenset({"idle", "inference"})
_VALID_STATUSES = frozenset({"healthy", "degraded", "critical", "offline"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_record(
    sample: TegrastatsSample,
    *,
    phase: str,
    device_id: str,
    ts: datetime,
) -> dict[str, Any]:
    """Registro completo (JSON-serializável) de uma amostra — o que vai pro JSONL."""
    return {
        "ts": ts.isoformat(),
        "device_id": device_id,
        "phase": phase,
        "cpu_pct": sample.cpu_pct,
        "cpu_cores_pct": sample.cpu_cores_pct,
        "ram_used_mb": sample.ram_used_mb,
        "ram_total_mb": sample.ram_total_mb,
        "ram_pct": sample.ram_pct,
        "swap_used_mb": sample.swap_used_mb,
        "swap_total_mb": sample.swap_total_mb,
        "emc_pct": sample.emc_pct,
        "gpu_pct": sample.gpu_pct,
        "gpu_temp_c": sample.gpu_temp_c,
        "cpu_temp_c": sample.cpu_temp_c,
        "temps_c": sample.temps_c,
        "power_mw": sample.power_mw,
        "power_in_mw": sample.power_in_mw,
    }


def build_heartbeat_payload(
    sample: TegrastatsSample,
    *,
    device_id: str,
    status: str = "healthy",
    edge_version: str | None = None,
    config_version_applied: str | None = None,
) -> dict[str, Any]:
    """Mapeia a amostra para o subconjunto do modelo `Heartbeat` que tegrastats
    consegue preencher. Campos de pipeline (inference_fps, câmeras, decode) ficam
    ausentes — serão preenchidos quando o pipeline DeepStream (task-088) subir.

    `config_version_applied` (ADR-0058, opcional) — o config_version do
    RECORDER_CHANNEL_MAP efetivamente em uso neste processo (edge_config_cache.py
    via recorder_factory.resolve_channel_map); permite ao backend comparar
    contra o config_version corrente e logar divergência (edge/routes.py).

    Só inclui chaves não-nulas (payloads enxutos; o modelo aceita ausência).
    """
    if status not in _VALID_STATUSES:
        raise ValueError(f"status inválido: {status!r} (esperado {sorted(_VALID_STATUSES)})")

    payload: dict[str, Any] = {"device_id": device_id, "status": status}
    optional = {
        "cpu_pct": sample.cpu_pct,
        "mem_pct": sample.ram_pct,
        "gpu_pct": sample.gpu_pct,
        "gpu_temp_c": sample.gpu_temp_c,
        "cpu_temp_c": sample.cpu_temp_c,
        "edge_version": edge_version,
        "config_version_applied": config_version_applied,
    }
    payload.update({k: v for k, v in optional.items() if v is not None})
    return payload


class JsonlWriter:
    """Append de registros como JSON-lines num arquivo local (thread-safe)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    @property
    def path(self) -> Path:
        return self._path


class HttpClient(Protocol):
    """Interface mínima do cliente HTTP injetado (compatível com requests.Session)."""

    def post(self, url: str, *, json: Any, timeout: float) -> Any: ...


class HeartbeatSink:
    """Envia amostras como heartbeats à API. NÃO derruba o coletor em falha de rede.

    A auth (device token RS256) é responsabilidade do `http_client` injetado —
    tipicamente uma sessão que assina o header Authorization. Mantido opcional:
    sem device enrolado, o coletor ainda grava o JSONL de baseline localmente.
    """

    def __init__(
        self,
        http_client: HttpClient,
        endpoint: str,
        *,
        device_id: str,
        edge_version: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._http = http_client
        self._endpoint = endpoint
        self._device_id = device_id
        self._edge_version = edge_version
        self._timeout = timeout

    def send(self, sample: TegrastatsSample, *, status: str = "healthy") -> bool:
        payload = build_heartbeat_payload(
            sample,
            device_id=self._device_id,
            status=status,
            edge_version=self._edge_version,
        )
        try:
            resp = self._http.post(self._endpoint, json=payload, timeout=self._timeout)
        except Exception as exc:  # rede indisponível não pode derrubar a coleta
            logger.warning("heartbeat sink: envio falhou: %s", exc)
            return False
        status_code = getattr(resp, "status_code", None)
        if status_code in (200, 201):
            return True
        logger.warning("heartbeat sink: API rejeitou (%s)", status_code)
        return False


class TelemetryCollector:
    """Orquestra fonte de linhas → parse → registro → sinks.

    `run()` consome qualquer iterável de linhas (subprocess real nos testes é
    substituído por uma lista), parando de forma graciosa via `stop_event`.
    """

    def __init__(
        self,
        *,
        device_id: str,
        phase: str,
        jsonl_writer: JsonlWriter | None = None,
        heartbeat_sink: HeartbeatSink | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        if phase not in _VALID_PHASES:
            raise ValueError(f"phase inválida: {phase!r} (esperado {sorted(_VALID_PHASES)})")
        self._device_id = device_id
        self._phase = phase
        self._jsonl = jsonl_writer
        self._heartbeat = heartbeat_sink
        self._clock = clock

    def process_line(self, line: str) -> dict[str, Any] | None:
        """Parseia uma linha, fan-out para os sinks, retorna o registro (ou None
        se a linha for vazia/ruído sem nenhum campo aproveitável)."""
        sample = parse_tegrastats_line(line)
        # Ignora linhas sem nenhum sinal (ex.: banner/erro do tegrastats).
        if sample.ram_total_mb is None and sample.gpu_pct is None and not sample.temps_c:
            return None
        record = build_record(
            sample, phase=self._phase, device_id=self._device_id, ts=self._clock()
        )
        if self._jsonl is not None:
            self._jsonl.write(record)
        if self._heartbeat is not None:
            self._heartbeat.send(sample)
        return record

    def run(
        self,
        lines: Iterable[str],
        *,
        stop_event: threading.Event | None = None,
    ) -> int:
        """Consome `lines` até esgotar ou `stop_event` sinalizar. Retorna a
        contagem de amostras processadas."""
        count = 0
        for line in lines:
            if stop_event is not None and stop_event.is_set():
                break
            if self.process_line(line) is not None:
                count += 1
        logger.info("coletor: %d amostras processadas (phase=%s)", count, self._phase)
        return count


def tegrastats_source(
    interval_ms: int = 5000,
    *,
    binary: str = "tegrastats",
) -> Iterator[str]:
    """Gera linhas do `tegrastats --interval` em tempo real (uma por amostra).

    Usado no box; nos testes injeta-se um iterável no lugar. Encerra o processo
    ao fim da iteração (GeneratorExit)."""
    proc = subprocess.Popen(
        [binary, "--interval", str(interval_ms)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            yield line.rstrip("\n")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
