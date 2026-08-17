"""Unit — camera_snapshot_state (Redis cache de miniatura de triagem, Bloco A)."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.domain.services import camera_snapshot_state as snap_state

TENANT = "t1"
CAMERA = "cam-1"


def test_read_state_none_when_key_absent():
    redis_client = MagicMock()
    redis_client.get.return_value = None
    assert snap_state.read_state(redis_client, TENANT, CAMERA) is None


def test_read_state_returns_parsed_json():
    redis_client = MagicMock()
    redis_client.get.return_value = json.dumps({"status": "ready", "r2_key": "x.jpg"})
    state = snap_state.read_state(redis_client, TENANT, CAMERA)
    assert state == {"status": "ready", "r2_key": "x.jpg"}


def test_read_state_corrupt_json_returns_none():
    redis_client = MagicMock()
    redis_client.get.return_value = "not json {{{"
    assert snap_state.read_state(redis_client, TENANT, CAMERA) is None


def test_read_state_redis_error_returns_none_fail_open():
    redis_client = MagicMock()
    redis_client.get.side_effect = ConnectionError("down")
    assert snap_state.read_state(redis_client, TENANT, CAMERA) is None


def test_write_pending_has_no_url_when_never_captured_before():
    redis_client = MagicMock()
    redis_client.get.return_value = None
    snap_state.write_pending(redis_client, TENANT, CAMERA)
    _, _, raw = redis_client.setex.call_args[0]
    state = json.loads(raw)
    assert state["status"] == "pending"
    assert state["r2_key"] is None
    assert state["error_reason"] is None


def test_write_pending_preserves_previous_ready_image():
    """UI pode continuar mostrando a miniatura antiga enquanto uma nova
    captura está em andamento."""
    redis_client = MagicMock()
    redis_client.get.return_value = json.dumps({
        "status": "ready", "r2_key": "old.jpg", "captured_at": "2026-01-01T00:00:00+00:00",
        "error_reason": None,
    })
    snap_state.write_pending(redis_client, TENANT, CAMERA)
    _, _, raw = redis_client.setex.call_args[0]
    state = json.loads(raw)
    assert state["status"] == "pending"
    assert state["r2_key"] == "old.jpg"
    assert state["captured_at"] == "2026-01-01T00:00:00+00:00"


def test_write_ready_stores_status_ready_with_r2_key():
    redis_client = MagicMock()
    snap_state.write_ready(redis_client, TENANT, CAMERA, "snapshots/t1/cam-1/1.jpg")
    key, ttl, raw = redis_client.setex.call_args[0]
    assert key == f"epi:camera_snapshot:{TENANT}:{CAMERA}"
    state = json.loads(raw)
    assert state["status"] == "ready"
    assert state["r2_key"] == "snapshots/t1/cam-1/1.jpg"
    assert state["error_reason"] is None
    assert ttl > 0


def test_write_failed_preserves_previous_ready_image():
    redis_client = MagicMock()
    redis_client.get.return_value = json.dumps({
        "status": "ready", "r2_key": "old.jpg", "captured_at": "2026-01-01T00:00:00+00:00",
        "error_reason": None,
    })
    snap_state.write_failed(redis_client, TENANT, CAMERA, "Canal sem sinal")
    _, _, raw = redis_client.setex.call_args[0]
    state = json.loads(raw)
    assert state["status"] == "failed"
    assert state["r2_key"] == "old.jpg"  # última imagem boa preservada
    assert state["captured_at"] == "2026-01-01T00:00:00+00:00"
    assert state["error_reason"] == "Canal sem sinal"


def test_write_failed_without_previous_state_has_null_image():
    redis_client = MagicMock()
    redis_client.get.return_value = None
    snap_state.write_failed(redis_client, TENANT, CAMERA, "Timeout")
    _, _, raw = redis_client.setex.call_args[0]
    state = json.loads(raw)
    assert state["r2_key"] is None
    assert state["captured_at"] is None


def test_is_fresh_true_within_window():
    state = {
        "status": "ready",
        "captured_at": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
    }
    assert snap_state.is_fresh(state, fresh_minutes=10) is True


def test_is_fresh_false_outside_window():
    state = {
        "status": "ready",
        "captured_at": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
    }
    assert snap_state.is_fresh(state, fresh_minutes=10) is False


def test_is_fresh_false_when_status_is_not_ready():
    state = {
        "status": "failed",
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    assert snap_state.is_fresh(state, fresh_minutes=10) is False


def test_is_fresh_false_when_state_is_none():
    assert snap_state.is_fresh(None, fresh_minutes=10) is False


def test_is_fresh_false_without_captured_at():
    assert snap_state.is_fresh({"status": "ready"}, fresh_minutes=10) is False
