"""Tests dos artefatos de estado entre processos (status_file.py) e dos hooks
do LiveViewLoop + heartbeat que os alimentam."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.heartbeat import HeartbeatLoop
from app.monitoring.status_file import (
    LiveViewStatus,
    write_json_atomic,
    write_net_status,
)

# ── escrita atômica ──────────────────────────────────────────────────────────


def test_write_json_atomic_roundtrip(tmp_path):
    path = tmp_path / "sub" / "status.json"
    assert write_json_atomic(path, {"ok": True}) is True
    assert json.loads(path.read_text()) == {"ok": True}


def test_write_json_atomic_failure_returns_false(tmp_path):
    blocker = tmp_path / "arquivo"
    blocker.write_text("x")
    # parent é um ARQUIVO → mkdir falha → False, sem levantar
    assert write_json_atomic(blocker / "status.json", {}) is False


# ── LiveViewStatus ───────────────────────────────────────────────────────────


def test_live_view_status_percentiles_and_rate(tmp_path):
    status = LiveViewStatus(tmp_path / "lv.json", write_interval_s=0.0)
    for ms in (10.0, 20.0, 30.0, 40.0, 1000.0):
        status.record_push_ok("cam-1", ms)
    status.record_push_fail("cam-1")
    status.record_ffmpeg_state("cam-1", running=True, wanted=True)
    status.maybe_write()

    data = json.loads((tmp_path / "lv.json").read_text())
    cam = data["cameras"]["cam-1"]
    assert cam["push_fail_total"] == 1
    assert cam["ffmpeg_alive"] is True
    assert cam["state"] == "streaming"
    assert cam["push_p50_ms"] == 30.0
    assert cam["push_p95_ms"] == 1000.0
    assert cam["segments_per_min"] == 5.0
    assert cam["last_push_age_s"] >= 0
    assert "ts" in data


def test_live_view_status_idle_camera(tmp_path):
    status = LiveViewStatus(tmp_path / "lv.json", write_interval_s=0.0)
    status.record_ffmpeg_state("cam-2", running=False, wanted=False)
    status.maybe_write()
    cam = json.loads((tmp_path / "lv.json").read_text())["cameras"]["cam-2"]
    assert cam["state"] == "idle"
    assert cam["segments_per_min"] == 0.0


def test_live_view_status_restart_counter(tmp_path):
    status = LiveViewStatus(tmp_path / "lv.json", write_interval_s=0.0)
    status.record_restart("cam-1")
    status.record_restart("cam-1")
    status.maybe_write()
    cam = json.loads((tmp_path / "lv.json").read_text())["cameras"]["cam-1"]
    assert cam["restarts_total"] == 2


def test_live_view_status_throttles_writes(tmp_path):
    status = LiveViewStatus(tmp_path / "lv.json", write_interval_s=3600.0)
    status.record_push_ok("cam-1", 5.0)
    status.maybe_write()  # 1ª escrita passa
    (tmp_path / "lv.json").unlink()
    status.maybe_write()  # dentro do intervalo: não reescreve
    assert not (tmp_path / "lv.json").exists()


# ── heartbeat alimenta o net.json (RTT de carona, zero egress novo) ─────────


def _resp(status_code: int):
    resp = MagicMock()
    resp.status_code = status_code
    return resp


def _token_source():
    ts = MagicMock()
    ts.get_bearer.return_value = "tok"
    return ts


def test_heartbeat_writes_net_status_on_success(tmp_path):
    net_path = tmp_path / "net.json"
    http = MagicMock()
    http.post.return_value = _resp(201)
    loop = HeartbeatLoop(
        http_client=http,
        cloud_url="http://cloud.test",
        device_id="dev-1",
        token_source=_token_source(),
        sample_provider=lambda: MagicMock(
            cpu_pct=None, ram_pct=None, gpu_pct=None, gpu_temp_c=None, cpu_temp_c=None
        ),
        net_status_path=str(net_path),
    )
    assert loop.send_once() is True
    data = json.loads(net_path.read_text())
    assert data["ok"] is True
    assert data["api_rtt_ms"] >= 0


def test_heartbeat_writes_net_status_on_network_error(tmp_path):
    net_path = tmp_path / "net.json"
    http = MagicMock()
    http.post.side_effect = ConnectionError("offline")
    loop = HeartbeatLoop(
        http_client=http,
        cloud_url="http://cloud.test",
        device_id="dev-1",
        token_source=_token_source(),
        sample_provider=lambda: MagicMock(
            cpu_pct=None, ram_pct=None, gpu_pct=None, gpu_temp_c=None, cpu_temp_c=None
        ),
        net_status_path=str(net_path),
    )
    assert loop.send_once() is False
    data = json.loads(net_path.read_text())
    assert data["ok"] is False
    assert data["api_rtt_ms"] is None


def test_write_net_status_shape(tmp_path):
    p = tmp_path / "net.json"
    write_net_status(p, rtt_ms=123.4, ok=True)
    data = json.loads(p.read_text())
    assert data["api_rtt_ms"] == 123.4
    assert data["ok"] is True
    assert data["ts"] > 0
