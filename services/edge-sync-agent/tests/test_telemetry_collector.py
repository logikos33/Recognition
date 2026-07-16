"""Testes do coletor de telemetria (task-100). Offline — sem Jetson e sem rede."""
import json
from datetime import datetime, timezone

import pytest

from app.telemetry.collector import (
    HeartbeatSink,
    JsonlWriter,
    TelemetryCollector,
    build_heartbeat_payload,
)
from app.telemetry.tegrastats_parser import parse_tegrastats_line
from tests.test_tegrastats_parser import IDLE_LINE, INFERENCE_LINE

# --- build_heartbeat_payload -------------------------------------------------


def test_heartbeat_payload_maps_and_omits_none():
    s = parse_tegrastats_line(IDLE_LINE)
    payload = build_heartbeat_payload(s, device_id="dev-1", edge_version="1.2.3")
    assert payload["device_id"] == "dev-1"
    assert payload["status"] == "healthy"
    assert payload["gpu_pct"] == 0
    assert payload["gpu_temp_c"] == 42.5
    assert payload["cpu_temp_c"] == 43.5
    assert payload["mem_pct"] == s.ram_pct
    assert payload["edge_version"] == "1.2.3"
    # campos de pipeline (não vindos de tegrastats) ausentes, não None
    assert "inference_fps" not in payload
    assert "cameras_online" not in payload


def test_heartbeat_payload_rejects_invalid_status():
    s = parse_tegrastats_line(IDLE_LINE)
    with pytest.raises(ValueError):
        build_heartbeat_payload(s, device_id="dev-1", status="bogus")


# --- JsonlWriter -------------------------------------------------------------


def test_jsonl_writer_creates_dir_and_appends(tmp_path):
    path = tmp_path / "nested" / "idle.jsonl"
    writer = JsonlWriter(path)
    writer.write({"a": 1})
    writer.write({"b": 2})
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert [json.loads(x) for x in lines] == [{"a": 1}, {"b": 2}]


# --- TelemetryCollector ------------------------------------------------------


def test_collector_writes_records_and_counts(tmp_path):
    path = tmp_path / "run.jsonl"
    fixed_ts = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    collector = TelemetryCollector(
        device_id="orin-01",
        phase="idle",
        jsonl_writer=JsonlWriter(path),
        clock=lambda: fixed_ts,
    )
    processed = collector.run([IDLE_LINE, INFERENCE_LINE])
    assert processed == 2
    records = [json.loads(x) for x in path.read_text().strip().splitlines()]
    assert len(records) == 2
    assert records[0]["phase"] == "idle"
    assert records[0]["device_id"] == "orin-01"
    assert records[0]["ts"] == fixed_ts.isoformat()
    assert records[1]["gpu_pct"] == 88


def test_collector_ignores_noise_lines(tmp_path):
    path = tmp_path / "run.jsonl"
    collector = TelemetryCollector(
        device_id="orin-01", phase="idle", jsonl_writer=JsonlWriter(path)
    )
    processed = collector.run(["tegrastats banner\n", "", IDLE_LINE])
    assert processed == 1  # só a linha com sinal real


def test_collector_stop_event_halts_early(tmp_path):
    import threading

    path = tmp_path / "run.jsonl"
    stop = threading.Event()
    stop.set()  # já sinalizado → não processa nada
    collector = TelemetryCollector(
        device_id="orin-01", phase="idle", jsonl_writer=JsonlWriter(path)
    )
    assert collector.run([IDLE_LINE, INFERENCE_LINE], stop_event=stop) == 0


def test_collector_rejects_invalid_phase():
    with pytest.raises(ValueError):
        TelemetryCollector(device_id="orin-01", phase="bogus")


# --- HeartbeatSink (rede injetada) -------------------------------------------


class _FakeResp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _FakeHttp:
    def __init__(self, status_code=201, raises=False) -> None:
        self._status = status_code
        self._raises = raises
        self.calls: list[dict] = []

    def post(self, url, *, json, timeout):  # noqa: A002 - assinatura do Protocol
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if self._raises:
            raise ConnectionError("rede indisponível")
        return _FakeResp(self._status)


def test_heartbeat_sink_success():
    http = _FakeHttp(status_code=201)
    sink = HeartbeatSink(http, "http://x/api/v1/edge/heartbeat", device_id="dev-1")
    ok = sink.send(parse_tegrastats_line(IDLE_LINE))
    assert ok is True
    assert http.calls[0]["json"]["device_id"] == "dev-1"
    assert http.calls[0]["json"]["gpu_temp_c"] == 42.5


def test_heartbeat_sink_network_failure_does_not_raise():
    http = _FakeHttp(raises=True)
    sink = HeartbeatSink(http, "http://x/api/v1/edge/heartbeat", device_id="dev-1")
    assert sink.send(parse_tegrastats_line(IDLE_LINE)) is False


def test_heartbeat_sink_non_2xx_is_false():
    http = _FakeHttp(status_code=422)
    sink = HeartbeatSink(http, "http://x/api/v1/edge/heartbeat", device_id="dev-1")
    assert sink.send(parse_tegrastats_line(IDLE_LINE)) is False


def test_collector_fans_out_to_heartbeat_sink(tmp_path):
    http = _FakeHttp(status_code=201)
    sink = HeartbeatSink(http, "http://x/api/v1/edge/heartbeat", device_id="orin-01")
    collector = TelemetryCollector(
        device_id="orin-01",
        phase="inference",
        jsonl_writer=JsonlWriter(tmp_path / "r.jsonl"),
        heartbeat_sink=sink,
    )
    collector.run([IDLE_LINE, INFERENCE_LINE])
    assert len(http.calls) == 2  # um heartbeat por amostra
