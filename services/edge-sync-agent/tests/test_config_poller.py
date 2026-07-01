"""Tests for ConfigPoller: apply config in memory, model manifest, stop_event."""

import threading
import time
from unittest.mock import MagicMock

from app.config_poller import ConfigPoller, ModelManifest


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_poller(http, *, poll_interval_s=0.0):
    return ConfigPoller(
        http_client=http,
        cloud_url="http://cloud.test",
        device_id="dev-001",
        token="tok",
        poll_interval_s=poll_interval_s,
    )


def _http_ok(body: dict):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = body
    return resp


def _http_err(status: int = 503):
    resp = MagicMock()
    resp.status_code = status
    return resp


# ── cameras / rules / scenario ───────────────────────────────────────────────

def test_applies_cameras_from_response():
    http = MagicMock()
    cameras = [{"id": "c1", "name": "Entry"}]
    http.get.return_value = _http_ok({"cameras": cameras})
    p = _make_poller(http)

    p._poll_once()

    assert p.get_cameras() == cameras


def test_applies_rules_from_response():
    http = MagicMock()
    rules = [{"id": "r1", "type": "epi"}]
    http.get.return_value = _http_ok({"rules": rules})
    p = _make_poller(http)

    p._poll_once()

    assert p.get_rules() == rules


def test_applies_scenario_from_response():
    http = MagicMock()
    scenario = {"module": "epi", "zones": []}
    http.get.return_value = _http_ok({"scenario": scenario})
    p = _make_poller(http)

    p._poll_once()

    assert p.get_scenario() == scenario


def test_partial_update_preserves_existing_cameras():
    """Second poll with only rules must not wipe previously received cameras."""
    http = MagicMock()
    cameras = [{"id": "c1"}]
    http.get.side_effect = [
        _http_ok({"cameras": cameras}),
        _http_ok({"rules": [{"id": "r99"}]}),
    ]
    p = _make_poller(http)

    p._poll_once()
    p._poll_once()

    assert p.get_cameras() == cameras  # cameras must survive second poll
    assert p.get_rules() == [{"id": "r99"}]


# ── model manifest ───────────────────────────────────────────────────────────

def test_sets_pending_model_when_sha256_differs():
    http = MagicMock()
    http.get.return_value = _http_ok(
        {"model": {"sha256": "abc123", "url": "https://r2.example/m.pt", "engine_type": "pt"}}
    )
    p = _make_poller(http)

    p._poll_once()

    m = p.get_model_manifest()
    assert isinstance(m, ModelManifest)
    assert m.sha256 == "abc123"
    assert m.engine_type == "pt"


def test_no_pending_model_when_sha256_is_same():
    http = MagicMock()
    sha = "deadbeef"
    http.get.return_value = _http_ok(
        {"model": {"sha256": sha, "url": "https://r2.example/m.pt", "engine_type": "pt"}}
    )
    p = _make_poller(http)
    p._state.current_model_sha256 = sha  # already on this model

    p._poll_once()

    assert p.get_model_manifest() is None


def test_no_pending_model_when_model_key_absent():
    http = MagicMock()
    http.get.return_value = _http_ok({"cameras": []})
    p = _make_poller(http)

    p._poll_once()

    assert p.get_model_manifest() is None


def test_no_pending_model_when_model_is_null():
    http = MagicMock()
    http.get.return_value = _http_ok({"model": None})
    p = _make_poller(http)

    p._poll_once()

    assert p.get_model_manifest() is None


# ── ack_model_applied ────────────────────────────────────────────────────────

def test_ack_model_applied_clears_pending_and_updates_sha256():
    http = MagicMock()
    http.get.return_value = _http_ok(
        {"model": {"sha256": "newsha", "url": "https://r2/m.pt", "engine_type": "pt"}}
    )
    p = _make_poller(http)
    p._poll_once()
    assert p.get_model_manifest() is not None

    p.ack_model_applied("newsha")

    assert p.get_model_manifest() is None
    assert p.get_current_model_sha256() == "newsha"


def test_ack_prevents_redundant_re_download_on_next_poll():
    """After ack, next poll with same sha256 should not set pending model again."""
    sha = "stablesha"
    http = MagicMock()
    http.get.return_value = _http_ok(
        {"model": {"sha256": sha, "url": "https://r2/m.pt", "engine_type": "pt"}}
    )
    p = _make_poller(http)

    p._poll_once()
    p.ack_model_applied(sha)

    # same sha in next poll
    p._poll_once()

    assert p.get_model_manifest() is None


# ── error resilience ─────────────────────────────────────────────────────────

def test_poll_error_preserves_existing_state():
    http = MagicMock()
    cameras = [{"id": "c1"}]
    http.get.side_effect = [
        _http_ok({"cameras": cameras}),
        _http_err(503),
    ]
    p = _make_poller(http)

    p._poll_once()  # success
    p._poll_once()  # failure — state must not be wiped

    assert p.get_cameras() == cameras


def test_network_exception_preserves_state():
    http = MagicMock()
    cameras = [{"id": "c2"}]
    http.get.side_effect = [
        _http_ok({"cameras": cameras}),
        OSError("timeout"),
    ]
    p = _make_poller(http)

    p._poll_once()
    result = p._poll_once()

    assert result is False
    assert p.get_cameras() == cameras


# ── request params ───────────────────────────────────────────────────────────

def test_poll_sends_device_id_and_current_sha256():
    http = MagicMock()
    http.get.return_value = _http_ok({})
    p = _make_poller(http)
    p._state.current_model_sha256 = "currentsha"

    p._poll_once()

    _, kwargs = http.get.call_args
    assert kwargs["params"]["device_id"] == "dev-001"
    assert kwargs["params"]["current_model_sha256"] == "currentsha"


# ── run() loop ───────────────────────────────────────────────────────────────

def test_run_exits_when_stop_event_set():
    http = MagicMock()
    http.get.return_value = _http_ok({})
    p = _make_poller(http)
    stop = threading.Event()
    stop.set()  # already set

    p.run(stop)  # must return without blocking


def test_run_applies_config_before_stopping():
    cameras = [{"id": "c3"}]
    http = MagicMock()
    http.get.return_value = _http_ok({"cameras": cameras})
    p = _make_poller(http)
    stop = threading.Event()

    def _run():
        p.run(stop)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    deadline = time.time() + 3.0
    while not p.get_cameras() and time.time() < deadline:
        time.sleep(0.01)
    stop.set()
    t.join(timeout=2.0)

    assert p.get_cameras() == cameras
    assert not t.is_alive()
