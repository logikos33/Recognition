"""Tests dos handlers monitoring.* (app/monitoring/handlers.py).

O crítico aqui: logtail com whitelist FECHADA e redação aplicada NO BOX antes
de qualquer byte sair (credencial de câmera vive nesses logs)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.monitoring.handlers import MonitoringCommandHandler, tail_lines
from app.monitoring.store import MetricsStore

# ── query / snapshot ─────────────────────────────────────────────────────────


def _handler_with_data(tmp_path) -> MonitoringCommandHandler:
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    import time

    now = int(time.time())
    for i in range(10):
        store.insert_sample(now - (10 - i) * 10, {"hw": {"cpu_pct": float(i)}})
    store.close()
    return MonitoringCommandHandler(db)


def test_query_returns_samples_and_collector_status(tmp_path):
    handler = _handler_with_data(tmp_path)
    result = handler.handle("monitoring.query", {"window": "2h"})
    assert result["schema"] == 1
    assert result["resolution"] == "10s"
    assert len(result["samples"]) == 10
    assert result["collector"]["status"] == "ok"


def test_query_no_args_path_unchanged(tmp_path):
    """Sem layers e sem max_points: amostras inteiras, todas as camadas."""
    handler = _handler_with_data(tmp_path)
    result = handler.handle("monitoring.query", {"window": "2h"})
    assert len(result["samples"]) == 10
    assert all("hw" in s for s in result["samples"])
    assert result["layers"] is None


def test_query_honors_layers_filter(tmp_path):
    """payload.layers chega ao box e filtra cada amostra (só ts + camadas
    pedidas)."""
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    import time

    now = int(time.time())
    for i in range(10):
        store.insert_sample(
            now - (10 - i) * 10,
            {"hw": {"cpu_pct": float(i)}, "net": {"tx_kbps": 1.0}, "svc": {"x": 1}},
        )
    store.close()
    handler = MonitoringCommandHandler(db)
    result = handler.handle("monitoring.query", {"window": "2h", "layers": ["hw"]})
    assert result["layers"] == ["hw"]
    assert all(set(s.keys()) == {"ts", "hw"} for s in result["samples"])


def test_query_honors_max_points(tmp_path):
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    import time

    now = int(time.time())
    for i in range(400):
        store.insert_sample(now - (400 - i) * 10, {"hw": {"cpu_pct": float(i % 30)}})
    store.close()
    handler = MonitoringCommandHandler(db)
    result = handler.handle(
        "monitoring.query", {"window": "2h", "max_points": 50}
    )
    assert len(result["samples"]) <= 50
    assert result["downsample"]["method"] == "stride+extrema"


def test_query_without_db_reports_collector_down(tmp_path):
    handler = MonitoringCommandHandler(tmp_path / "missing.db")
    result = handler.handle("monitoring.query", {"window": "2h"})
    assert result["samples"] == []
    assert result["collector"]["status"] == "down"


def test_query_invalid_window_raises_value_error(tmp_path):
    handler = _handler_with_data(tmp_path)
    with pytest.raises(ValueError):
        handler.handle("monitoring.query", {"window": "9h"})


def test_snapshot_returns_single_latest_sample(tmp_path):
    handler = _handler_with_data(tmp_path)
    result = handler.handle("monitoring.snapshot", {})
    assert len(result["samples"]) == 1
    assert result["samples"][0]["hw"]["cpu_pct"] == 9.0


def test_unknown_monitoring_command_raises(tmp_path):
    handler = _handler_with_data(tmp_path)
    with pytest.raises(ValueError):
        handler.handle("monitoring.reboot", {})


def test_can_handle_prefix():
    handler = MonitoringCommandHandler("/nonexistent.db")
    assert handler.can_handle("monitoring.query") is True
    assert handler.can_handle("update_camera_config") is False


# ── logtail ──────────────────────────────────────────────────────────────────


def _handler_with_log(tmp_path, lines: list[str]) -> MonitoringCommandHandler:
    log = tmp_path / "edge-live-view.log"
    log.write_text("\n".join(lines) + "\n")
    registry = {"edge-live-view": [log]}
    return MonitoringCommandHandler(tmp_path / "metrics.db", log_registry=registry)


def test_logtail_redacts_credentials_on_box():
    """🔴 A linha com senha RTSP sai REDIGIDA — a redação acontece no box,
    nunca na nuvem."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        handler = _handler_with_log(
            Path(tmp),
            [
                "linha normal",
                "ffmpeg falhou em rtsp://admin:s3nha_secreta@192.168.35.99:554/ch1",
            ],
        )
        result = handler.handle("monitoring.logtail", {"unit": "edge-live-view", "lines": 10})
    joined = "\n".join(result["lines"])
    assert "s3nha_secreta" not in joined
    assert "rtsp://admin:***@192.168.35.99:554/ch1" in joined


def test_logtail_unit_outside_whitelist_raises(tmp_path):
    handler = _handler_with_log(tmp_path, ["x"])
    with pytest.raises(ValueError):
        handler.handle("monitoring.logtail", {"unit": "../../etc/passwd", "lines": 10})


def test_logtail_missing_file_reports_reason(tmp_path):
    registry = {"edge-live-view": [tmp_path / "nao-existe.log"]}
    handler = MonitoringCommandHandler(tmp_path / "m.db", log_registry=registry)
    result = handler.handle("monitoring.logtail", {"unit": "edge-live-view", "lines": 10})
    assert result["lines"] == []
    assert "não existe" in result["reason"]


def test_logtail_caps_lines(tmp_path):
    handler = _handler_with_log(tmp_path, [f"linha {i}" for i in range(100)])
    result = handler.handle("monitoring.logtail", {"unit": "edge-live-view", "lines": 5})
    assert len(result["lines"]) == 5
    assert result["lines"][-1] == "linha 99"


def test_logtail_lines_clamped_to_max(tmp_path):
    handler = _handler_with_log(tmp_path, ["x"] * 10)
    # pedir 99999 não estoura o teto interno (500)
    result = handler.handle("monitoring.logtail", {"unit": "edge-live-view", "lines": 99999})
    assert len(result["lines"]) == 10


def test_tail_lines_reads_only_file_end(tmp_path):
    log = tmp_path / "big.log"
    log.write_text("\n".join(f"linha {i}" for i in range(10_000)) + "\n")
    lines, _truncated = tail_lines(log, 3, max_bytes=1024)
    assert lines == ["linha 9997", "linha 9998", "linha 9999"]
