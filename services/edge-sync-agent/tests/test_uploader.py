"""Tests for Uploader: backoff, idempotency, event safety, stop_event."""

import threading
import time
from unittest.mock import MagicMock

import pytest

from app.sqlite_buffer import SQLiteBuffer
from app.uploader import Uploader, _batch_id


# ── helpers ──────────────────────────────────────────────────────────────────

def _ok_response():
    r = MagicMock()
    r.status_code = 200
    return r


def _err_response(status: int = 503):
    r = MagicMock()
    r.status_code = status
    return r


def _make_uploader(buf, http, *, backoff_steps=(1.0, 2.0, 4.0, 8.0)):
    return Uploader(
        buffer=buf,
        http_client=http,
        cloud_url="http://cloud.test",
        device_id="dev-001",
        token="tok",
        batch_size=500,
        upload_interval_s=0.0,
        backoff_steps=backoff_steps,
    )


@pytest.fixture()
def buf(tmp_path):
    b = SQLiteBuffer(str(tmp_path / "up.db"))
    yield b
    b.close()


# ── batch_id determinism ─────────────────────────────────────────────────────

def test_batch_id_is_deterministic():
    assert _batch_id([3, 1, 2]) == _batch_id([1, 2, 3])


def test_batch_id_differs_for_different_ids():
    assert _batch_id([1, 2]) != _batch_id([1, 3])


def test_batch_id_is_32_hex_chars():
    bid = _batch_id([10, 20, 30])
    assert len(bid) == 32
    assert all(c in "0123456789abcdef" for c in bid)


# ── success path ─────────────────────────────────────────────────────────────

def test_successful_upload_marks_sent(buf):
    buf.enqueue("detection", "cam1", {"x": 1})
    http = MagicMock()
    http.post.return_value = _ok_response()
    up = _make_uploader(buf, http)

    result = up._try_upload(buf.dequeue_batch())

    assert result is True
    assert buf.count_unsent() == 0


def test_successful_upload_resets_backoff(buf):
    buf.enqueue("detection", "cam1", {})
    http = MagicMock()
    http.post.return_value = _err_response()
    up = _make_uploader(buf, http)
    up._try_upload(buf.dequeue_batch())  # fail → advance backoff
    assert up.current_backoff() == 2.0

    # make next call succeed
    buf.enqueue("detection", "cam1", {})
    http.post.return_value = _ok_response()
    up._try_upload(buf.dequeue_batch())
    assert up.current_backoff() == 1.0  # reset


def test_x_batch_id_header_is_sent(buf):
    buf.enqueue("detection", "cam1", {})
    http = MagicMock()
    http.post.return_value = _ok_response()
    up = _make_uploader(buf, http)

    batch = buf.dequeue_batch()
    up._try_upload(batch)

    _, kwargs = http.post.call_args
    assert "X-Batch-Id" in kwargs["headers"]
    expected = _batch_id([e["id"] for e in batch])
    assert kwargs["headers"]["X-Batch-Id"] == expected


# ── failure / backoff ────────────────────────────────────────────────────────

def test_failed_upload_keeps_events_in_buffer(buf):
    buf.enqueue("detection", "cam1", {})
    http = MagicMock()
    http.post.return_value = _err_response()
    up = _make_uploader(buf, http)

    result = up._try_upload(buf.dequeue_batch())

    assert result is False
    assert buf.count_unsent() == 1


def test_backoff_grows_on_consecutive_failures(buf):
    http = MagicMock()
    http.post.return_value = _err_response()
    up = _make_uploader(buf, http, backoff_steps=(1.0, 2.0, 4.0, 8.0))

    assert up.current_backoff() == 1.0

    for expected in (2.0, 4.0, 8.0, 8.0):  # capped at last step
        buf.enqueue("detection", "cam1", {})
        up._try_upload(buf.dequeue_batch())
        assert up.current_backoff() == expected


def test_network_error_treated_as_failure(buf):
    buf.enqueue("detection", "cam1", {})
    http = MagicMock()
    http.post.side_effect = OSError("connection refused")
    up = _make_uploader(buf, http)

    result = up._try_upload(buf.dequeue_batch())

    assert result is False
    assert buf.count_unsent() == 1
    assert up.current_backoff() == 2.0  # advanced


# ── idempotency on retry ─────────────────────────────────────────────────────

def test_retry_sends_identical_x_batch_id(buf):
    """Same events in buffer → same X-Batch-Id on every retry attempt."""
    buf.enqueue("detection", "cam1", {"n": 1})
    buf.enqueue("detection", "cam1", {"n": 2})

    http = MagicMock()
    http.post.side_effect = [_err_response(), _err_response(), _ok_response()]
    up = _make_uploader(buf, http)

    sent_ids: list[str] = []
    for _ in range(3):
        batch = buf.dequeue_batch()
        up._try_upload(batch)
        _, kwargs = http.post.call_args
        sent_ids.append(kwargs["headers"]["X-Batch-Id"])

    # All three attempts must carry the same batch id
    assert sent_ids[0] == sent_ids[1] == sent_ids[2]


def test_no_event_lost_after_multiple_failures(buf):
    n = 10
    for i in range(n):
        buf.enqueue("detection", "cam1", {"i": i})

    http = MagicMock()
    http.post.return_value = _err_response()
    up = _make_uploader(buf, http)

    for _ in range(3):
        up._try_upload(buf.dequeue_batch())

    assert buf.count_unsent() == n


# ── run() loop ───────────────────────────────────────────────────────────────

def test_run_exits_when_stop_event_set(buf):
    http = MagicMock()
    http.post.return_value = _ok_response()
    up = _make_uploader(buf, http)
    stop = threading.Event()
    stop.set()  # already set — loop must exit immediately

    up.run(stop)  # should return without blocking


def test_run_uploads_all_events_then_stops(buf):
    for i in range(3):
        buf.enqueue("detection", "cam1", {"i": i})

    http = MagicMock()
    http.post.return_value = _ok_response()
    up = _make_uploader(buf, http)
    stop = threading.Event()

    def _run():
        up.run(stop)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    # Wait until buffer is drained, then stop
    deadline = time.time() + 5.0
    while buf.count_unsent() > 0 and time.time() < deadline:
        time.sleep(0.01)
    stop.set()
    t.join(timeout=2.0)

    assert buf.count_unsent() == 0
    assert not t.is_alive()
