"""Tests for the PR-C orchestrator: _supervise, _start_loop_threads,
_AutoAuthHttpClient, build_sync_loops_from_env, signal handling, run_daemon
wiring. Loops/http/token_manager are always mocked — no real network."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from app import main as main_module
from app.heartbeat import HeartbeatLoop
from app.main import (
    _AutoAuthHttpClient,
    _make_signal_handler,
    _start_loop_threads,
    _supervise,
    build_sync_loops_from_env,
)


def _pubkey_file(tmp_path):
    key_file = tmp_path / "trust_public_key.pem"
    key_file.write_text("-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----\n")
    return key_file


# ── _supervise ────────────────────────────────────────────────────────────────

def test_supervise_never_calls_run_if_stop_already_set():
    loop = MagicMock()
    stop = threading.Event()
    stop.set()

    _supervise("x", loop, stop)

    loop.run.assert_not_called()


def test_supervise_restarts_after_exception_with_backoff():
    stop = threading.Event()
    calls = []

    def _run(_stop_event):
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("boom")
        stop.set()

    loop = MagicMock()
    loop.run.side_effect = _run

    _supervise("x", loop, stop, backoff_steps=(0.01, 0.01))

    assert loop.run.call_count == 3


def test_supervise_restarts_after_clean_return_if_stop_not_set():
    """A loop returning on its own (not a crash) is still treated as needing
    a restart unless the daemon itself is stopping — matches HeartbeatLoop
    giving up after a 403 and the daemon wanting that to keep being visible,
    not silently go idle."""
    stop = threading.Event()
    calls = []

    def _run(_stop_event):
        calls.append(1)
        if len(calls) >= 2:
            stop.set()

    loop = MagicMock()
    loop.run.side_effect = _run

    _supervise("heartbeat", loop, stop, backoff_steps=(0.01,))

    assert loop.run.call_count == 2


def test_supervise_does_not_restart_once_stop_event_is_set():
    stop = threading.Event()

    def _run(_stop_event):
        stop.set()

    loop = MagicMock()
    loop.run.side_effect = _run

    _supervise("x", loop, stop, backoff_steps=(0.01,))

    assert loop.run.call_count == 1


# ── _start_loop_threads ──────────────────────────────────────────────────────

def test_start_loop_threads_starts_one_thread_per_loop_named_after_it():
    stop = threading.Event()
    stop.set()
    loops = {"a": MagicMock(), "b": MagicMock(), "c": MagicMock()}

    threads = _start_loop_threads(loops, stop)

    assert {t.name for t in threads} == set(loops)
    for t in threads:
        t.join(timeout=2.0)
        assert not t.is_alive()


def test_start_loop_threads_each_loop_runs_until_stopped():
    stop = threading.Event()
    ran = threading.Event()

    def _run(stop_event):
        ran.set()
        stop_event.wait()  # honors the shared stop_event, like the real loops do

    loop = MagicMock()
    loop.run.side_effect = _run

    threads = _start_loop_threads({"a": loop}, stop)
    assert ran.wait(timeout=2.0)

    stop.set()
    threads[0].join(timeout=2.0)
    assert not threads[0].is_alive()


# ── _AutoAuthHttpClient ───────────────────────────────────────────────────────

def test_auto_auth_get_injects_fresh_bearer():
    inner = MagicMock()
    tm = MagicMock()
    tm.get_bearer.return_value = "tok-1"
    client = _AutoAuthHttpClient(inner, tm)

    client.get("http://x", params={"a": 1}, timeout=15.0)

    tm.get_bearer.assert_called_once()
    _, kwargs = inner.get.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer tok-1"
    assert kwargs["params"] == {"a": 1}


def test_auto_auth_overrides_stale_authorization_header():
    inner = MagicMock()
    tm = MagicMock()
    tm.get_bearer.return_value = "fresh"
    client = _AutoAuthHttpClient(inner, tm)

    client.post("http://x", json={}, headers={"Authorization": "Bearer STALE"})

    _, kwargs = inner.post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer fresh"


def test_auto_auth_patch_also_gets_a_fresh_bearer():
    inner = MagicMock()
    tm = MagicMock()
    tm.get_bearer.return_value = "tok-2"
    client = _AutoAuthHttpClient(inner, tm)

    client.patch("http://x", json={"status": "done"})

    _, kwargs = inner.patch.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer tok-2"


def test_auto_auth_mints_a_new_token_on_every_call():
    inner = MagicMock()
    tm = MagicMock()
    tm.get_bearer.side_effect = ["tok-a", "tok-b"]
    client = _AutoAuthHttpClient(inner, tm)

    client.get("http://x")
    client.get("http://x")

    assert tm.get_bearer.call_count == 2
    calls = inner.get.call_args_list
    assert calls[0].kwargs["headers"]["Authorization"] == "Bearer tok-a"
    assert calls[1].kwargs["headers"]["Authorization"] == "Bearer tok-b"


# ── build_sync_loops_from_env ────────────────────────────────────────────────

def test_build_sync_loops_returns_all_four_wired_together(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_BUFFER_PATH", str(tmp_path / "buf.db"))
    http = MagicMock()
    tm = MagicMock()
    tm.get_bearer.return_value = "tok"

    loops = build_sync_loops_from_env(http, tm, device_id="dev-1", cloud_url="http://cloud.test")

    assert set(loops) == {"config_poller", "command_poller", "uploader", "heartbeat"}
    assert loops["command_poller"]._config_poller is loops["config_poller"]
    assert isinstance(loops["heartbeat"], HeartbeatLoop)


def test_build_sync_loops_wraps_the_three_static_token_loops_in_auto_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_BUFFER_PATH", str(tmp_path / "buf.db"))
    http = MagicMock()
    tm = MagicMock()
    tm.get_bearer.return_value = "tok"

    loops = build_sync_loops_from_env(http, tm, device_id="dev-1", cloud_url="http://cloud.test")

    assert isinstance(loops["config_poller"]._http, _AutoAuthHttpClient)
    assert isinstance(loops["command_poller"]._http, _AutoAuthHttpClient)
    assert isinstance(loops["uploader"]._http, _AutoAuthHttpClient)


def test_build_sync_loops_respects_upload_batch_size_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_BUFFER_PATH", str(tmp_path / "buf.db"))
    monkeypatch.setenv("UPLOAD_BATCH_SIZE", "42")
    http = MagicMock()
    tm = MagicMock()

    loops = build_sync_loops_from_env(http, tm, device_id="dev-1", cloud_url="http://cloud.test")

    assert loops["uploader"]._batch_size == 42


# ── signal handling ──────────────────────────────────────────────────────────

def test_signal_handler_sets_stop_event():
    stop = threading.Event()
    handler = _make_signal_handler(stop)

    handler(15, None)  # SIGTERM's numeric value — avoids importing `signal` just for this

    assert stop.is_set()


# ── run_daemon wiring ────────────────────────────────────────────────────────

def test_run_daemon_wires_enrolled_identity_into_all_four_loops(monkeypatch, tmp_path):
    monkeypatch.setenv("RECORDER_PROTOCOL", "onvif")
    monkeypatch.setenv("RECORDER_HOST", "10.0.0.5")
    monkeypatch.setenv("RECORDER_PORT", "8080")
    monkeypatch.setenv("RECORDER_CHANNEL_MAP", "{}")
    monkeypatch.setenv("EVIDENCE_TRUST_PUBLIC_KEY_PATH", str(_pubkey_file(tmp_path)))
    monkeypatch.setenv("TENANT_ID", "t1")
    monkeypatch.setenv("SITE_ID", "s1")
    monkeypatch.setenv("SQLITE_BUFFER_PATH", str(tmp_path / "buf.db"))
    monkeypatch.setenv("DEVICE_ID", "dev-1")
    monkeypatch.setenv("EDGE_DEVICE_KEY_PATH", str(tmp_path / "device_key.pem"))

    fake_identity = SimpleNamespace(
        device_id="dev-1", tenant_id="t1", site_id="s1", scopes=[], revoked=False
    )
    monkeypatch.setattr(
        main_module, "ensure_enrolled", lambda *a, **k: fake_identity
    )
    monkeypatch.setattr(main_module, "run_server", lambda *a, **k: None)

    captured = {}

    def _fake_start(loops, stop_event):
        captured["loops"] = loops
        stop_event.set()  # let run_daemon's stop_event.wait() return immediately
        return []

    monkeypatch.setattr(main_module, "_start_loop_threads", _fake_start)

    main_module.run_daemon()

    assert set(captured["loops"]) == {"config_poller", "command_poller", "uploader", "heartbeat"}
    assert captured["loops"]["config_poller"]._device_id == "dev-1"
