"""Tests for HeartbeatLoop: payload, 201/403/network handling, backoff, stop_event."""

import threading
import time
from unittest.mock import MagicMock

import pytest

from app.heartbeat import (
    DeviceRevokedError,
    HeartbeatLoop,
    build_heartbeat_loop_from_env,
    read_tegrastats_sample,
)
from app.telemetry.tegrastats_parser import TegrastatsSample


def _response(status_code, body=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = body or {}
    return r


def _token_source(bearer="signed-jwt"):
    ts = MagicMock()
    ts.get_bearer.return_value = bearer
    return ts


def _make_loop(http, token_source, *, sample=None, backoff_steps=(1.0, 2.0, 4.0)):
    return HeartbeatLoop(
        http_client=http,
        cloud_url="http://cloud.test",
        device_id="dev-1",
        token_source=token_source,
        sample_provider=lambda: sample if sample is not None else TegrastatsSample(),
        interval_s=0.0,
        backoff_steps=backoff_steps,
    )


# ── send_once: success ───────────────────────────────────────────────────────

def test_successful_send_returns_true_and_resets_backoff():
    http = MagicMock()
    http.post.return_value = _response(201)
    ts = _token_source()
    loop = _make_loop(http, ts)

    assert loop.send_once() is True
    assert loop.current_backoff() == 1.0


def test_send_once_uses_fresh_bearer_and_correct_url():
    http = MagicMock()
    http.post.return_value = _response(201)
    ts = _token_source(bearer="tok-123")
    loop = _make_loop(http, ts)

    loop.send_once()

    ts.get_bearer.assert_called_once()
    args, kwargs = http.post.call_args
    assert args[0] == "http://cloud.test/api/v1/edge/heartbeat"
    assert kwargs["headers"]["Authorization"] == "Bearer tok-123"


def test_payload_maps_real_telemetry_and_omits_camera_fields():
    http = MagicMock()
    http.post.return_value = _response(201)
    ts = _token_source()
    sample = TegrastatsSample(ram_used_mb=500, ram_total_mb=1000, gpu_pct=10)
    loop = _make_loop(http, ts, sample=sample)

    loop.send_once()

    _, kwargs = http.post.call_args
    payload = kwargs["json"]
    assert payload["device_id"] == "dev-1"
    assert payload["gpu_pct"] == 10
    assert payload["mem_pct"] == 50.0
    # Camera/inference fields aren't produced by tegrastats — must be absent, not faked.
    assert "cameras_online" not in payload
    assert "inference_fps" not in payload


# ── send_once: 403 revoked ───────────────────────────────────────────────────

def test_403_marks_revoked_and_raises():
    http = MagicMock()
    http.post.return_value = _response(403)
    ts = _token_source()
    loop = _make_loop(http, ts)

    with pytest.raises(DeviceRevokedError):
        loop.send_once()

    ts.mark_revoked.assert_called_once()


# ── send_once: retryable failures ───────────────────────────────────────────

def test_other_status_is_retryable_not_revoked():
    http = MagicMock()
    http.post.return_value = _response(503)
    ts = _token_source()
    loop = _make_loop(http, ts)

    assert loop.send_once() is False
    ts.mark_revoked.assert_not_called()
    assert loop.current_backoff() == 2.0


def test_network_error_is_retryable():
    http = MagicMock()
    http.post.side_effect = ConnectionError("boom")
    ts = _token_source()
    loop = _make_loop(http, ts)

    assert loop.send_once() is False
    assert loop.current_backoff() == 2.0


def test_backoff_resets_after_success_following_failures():
    http = MagicMock()
    ts = _token_source()
    loop = _make_loop(http, ts, backoff_steps=(1.0, 2.0, 4.0))

    http.post.return_value = _response(503)
    loop.send_once()
    loop.send_once()
    assert loop.current_backoff() == 4.0

    http.post.return_value = _response(201)
    loop.send_once()
    assert loop.current_backoff() == 1.0


# ── run() loop ───────────────────────────────────────────────────────────────

def test_run_exits_immediately_when_stop_event_already_set():
    http = MagicMock()
    http.post.return_value = _response(201)
    loop = _make_loop(http, _token_source())
    stop = threading.Event()
    stop.set()

    loop.run(stop)  # must return without blocking
    http.post.assert_not_called()


def test_run_stops_without_retry_on_revocation():
    http = MagicMock()
    http.post.return_value = _response(403)
    ts = _token_source()
    loop = _make_loop(http, ts)
    stop = threading.Event()

    loop.run(stop)  # must return on its own — revoked, no retry loop

    assert http.post.call_count == 1
    ts.mark_revoked.assert_called_once()


def test_run_sends_multiple_heartbeats_until_stopped():
    http = MagicMock()
    http.post.return_value = _response(201)
    loop = _make_loop(http, _token_source())
    stop = threading.Event()

    t = threading.Thread(target=loop.run, args=(stop,), daemon=True)
    t.start()

    deadline = time.time() + 2.0
    while http.post.call_count < 3 and time.time() < deadline:
        time.sleep(0.01)
    stop.set()
    t.join(timeout=2.0)

    assert http.post.call_count >= 3
    assert not t.is_alive()


# ── read_tegrastats_sample ───────────────────────────────────────────────────

def test_read_tegrastats_sample_missing_binary_returns_empty_sample():
    sample = read_tegrastats_sample(binary="definitely-not-a-real-binary-xyz")
    assert sample.ram_total_mb is None
    assert sample.gpu_pct is None
    assert sample.temps_c == {}


# ── build_heartbeat_loop_from_env ────────────────────────────────────────────

def test_build_from_env_reads_all_fields():
    http = MagicMock()
    ts = _token_source()
    env = {
        "EDGE_API_URL": "https://api.test/",
        "DEVICE_ID": "dev-9",
        "EDGE_VERSION": "1.2.3",
        "EDGE_HEARTBEAT_INTERVAL_S": "20",
    }
    loop = build_heartbeat_loop_from_env(http, ts, env)

    assert loop._url == "https://api.test/api/v1/edge/heartbeat"
    assert loop._device_id == "dev-9"
    assert loop._edge_version == "1.2.3"
    assert loop._interval == 20.0


def test_build_from_env_defaults_to_dev_api_url():
    loop = build_heartbeat_loop_from_env(MagicMock(), _token_source(), {"DEVICE_ID": "dev-1"})
    assert "desenvolvimento" in loop._url
    assert "production" not in loop._url


def test_build_from_env_requires_device_id():
    with pytest.raises(ValueError, match="device_id"):
        build_heartbeat_loop_from_env(MagicMock(), _token_source(), {})


def test_build_from_env_device_id_param_overrides_env():
    loop = build_heartbeat_loop_from_env(
        MagicMock(), _token_source(), {"DEVICE_ID": "from-env"}, device_id="from-param"
    )
    assert loop._device_id == "from-param"


def test_build_from_env_sentinel_path_defaults_to_none():
    loop = build_heartbeat_loop_from_env(MagicMock(), _token_source(), {"DEVICE_ID": "dev-1"})
    assert loop._sentinel_path is None


def test_build_from_env_reads_sentinel_path():
    loop = build_heartbeat_loop_from_env(
        MagicMock(),
        _token_source(),
        {"DEVICE_ID": "dev-1", "EDGE_HEARTBEAT_SENTINEL_PATH": "/tmp/hb.ok"},
    )
    assert loop._sentinel_path == "/tmp/hb.ok"


# ── sentinel file (OTA health-check proof-of-life) ──────────────────────────

def test_successful_send_touches_sentinel_when_configured(tmp_path):
    sentinel = tmp_path / "state" / "heartbeat.ok"
    http = MagicMock()
    http.post.return_value = _response(201)
    loop = HeartbeatLoop(
        http_client=http,
        cloud_url="http://cloud.test",
        device_id="dev-1",
        token_source=_token_source(),
        sample_provider=lambda: TegrastatsSample(),
        sentinel_path=str(sentinel),
    )

    loop.send_once()

    assert sentinel.exists()


def test_sentinel_not_touched_when_not_configured(tmp_path):
    http = MagicMock()
    http.post.return_value = _response(201)
    loop = _make_loop(http, _token_source())  # no sentinel_path

    loop.send_once()  # must not raise / must not try to write anywhere


def test_sentinel_not_touched_on_failed_send(tmp_path):
    sentinel = tmp_path / "heartbeat.ok"
    http = MagicMock()
    http.post.return_value = _response(503)
    loop = HeartbeatLoop(
        http_client=http,
        cloud_url="http://cloud.test",
        device_id="dev-1",
        token_source=_token_source(),
        sample_provider=lambda: TegrastatsSample(),
        sentinel_path=str(sentinel),
    )

    loop.send_once()

    assert not sentinel.exists()


def test_sentinel_write_failure_does_not_break_send(tmp_path, monkeypatch):
    """An unwritable sentinel path (e.g. permissions) must not turn a
    successful heartbeat into a failure — the sentinel is a nice-to-have for
    OTA, not load-bearing for the heartbeat's own contract."""
    http = MagicMock()
    http.post.return_value = _response(201)
    loop = HeartbeatLoop(
        http_client=http,
        cloud_url="http://cloud.test",
        device_id="dev-1",
        token_source=_token_source(),
        sample_provider=lambda: TegrastatsSample(),
        sentinel_path="/root/definitely-not-writable/heartbeat.ok",
    )

    assert loop.send_once() is True
