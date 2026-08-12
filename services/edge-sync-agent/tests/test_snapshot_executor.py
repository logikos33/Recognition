"""Tests for SnapshotExecutor: recorder capture + multipart upload, and the
anti-lockout circuit breaker (a 401/403 from the recorder must suspend ALL
future capture_snapshot attempts until process restart — CLAUDE.md, the
gravador applies anti-brute-force lockout to repeated failed-auth attempts).
"""
from unittest.mock import MagicMock

from app.recorder_client import RecorderAuthError, RecorderError
from app.snapshot_executor import SnapshotExecutor


def _http_ok():
    resp = MagicMock()
    resp.status_code = 201
    return resp


def _http_rejected(status=500):
    resp = MagicMock()
    resp.status_code = status
    resp.text = "upstream rejected"
    return resp


def _make_executor(recorder, http=None):
    return SnapshotExecutor(
        recorder_client=recorder,
        http_client=http or MagicMock(),
        cloud_url="http://cloud.test",
        token="tok",
    )


# ── happy path ───────────────────────────────────────────────────────────────

def test_capture_and_upload_success():
    recorder = MagicMock()
    recorder.get_snapshot.return_value = b"jpeg-bytes"
    http = MagicMock()
    http.post.return_value = _http_ok()
    executor = _make_executor(recorder, http)

    result = executor.capture_and_upload("cam-1", channel=3)

    assert result == {"ok": True}
    recorder.get_snapshot.assert_called_once_with("cam-1")
    url, kwargs = http.post.call_args
    assert url[0] == "http://cloud.test/api/v1/edge/cameras/cam-1/snapshot"
    assert kwargs["headers"]["Authorization"] == "Bearer tok"
    assert kwargs["files"]["file"][0] == "snapshot.jpg"
    assert kwargs["files"]["file"][1] == b"jpeg-bytes"


def test_capture_and_upload_strips_trailing_slash_from_cloud_url():
    recorder = MagicMock()
    recorder.get_snapshot.return_value = b"x"
    http = MagicMock()
    http.post.return_value = _http_ok()
    executor = SnapshotExecutor(recorder, http, cloud_url="http://cloud.test/", token="t")

    executor.capture_and_upload("cam-1")

    url = http.post.call_args[0][0]
    assert url == "http://cloud.test/api/v1/edge/cameras/cam-1/snapshot"


# ── non-auth capture failures: continue, never trip the breaker ────────────

def test_capture_timeout_returns_reason_timeout_and_does_not_trip_breaker():
    recorder = MagicMock()
    recorder.get_snapshot.side_effect = RecorderError("ffmpeg não respondeu em 10.0s")
    executor = _make_executor(recorder)

    result = executor.capture_and_upload("cam-1")

    assert result["ok"] is False
    assert result["reason"] == "timeout"
    assert executor.circuit_open is False


def test_capture_no_signal_returns_generic_reason():
    recorder = MagicMock()
    recorder.get_snapshot.side_effect = RecorderError("canal sem sinal")
    executor = _make_executor(recorder)

    result = executor.capture_and_upload("cam-1")

    assert result["ok"] is False
    assert result["reason"] == "sem sinal no canal"
    assert executor.circuit_open is False


def test_capture_unexpected_exception_never_raises_out():
    recorder = MagicMock()
    recorder.get_snapshot.side_effect = RuntimeError("boom")
    executor = _make_executor(recorder)

    result = executor.capture_and_upload("cam-1")

    assert result["ok"] is False
    assert result["reason"] == "capture_failed"


# ── upload failures ──────────────────────────────────────────────────────────

def test_upload_rejected_returns_upload_failed_reason():
    recorder = MagicMock()
    recorder.get_snapshot.return_value = b"jpeg"
    http = MagicMock()
    http.post.return_value = _http_rejected(500)
    executor = _make_executor(recorder, http)

    result = executor.capture_and_upload("cam-1")

    assert result["ok"] is False
    assert result["reason"] == "upload_failed"


def test_upload_network_error_returns_upload_failed_reason():
    recorder = MagicMock()
    recorder.get_snapshot.return_value = b"jpeg"
    http = MagicMock()
    http.post.side_effect = ConnectionError("offline")
    executor = _make_executor(recorder, http)

    result = executor.capture_and_upload("cam-1")

    assert result["ok"] is False
    assert result["reason"] == "upload_failed"


# ── anti-lockout circuit breaker ─────────────────────────────────────────────

def test_auth_failure_trips_circuit_and_reports_reason_auth():
    recorder = MagicMock()
    recorder.get_snapshot.side_effect = RecorderAuthError("onvif_soap_auth_failed status=401")
    executor = _make_executor(recorder)

    result = executor.capture_and_upload("cam-1")

    assert result == {"ok": False, "reason": "auth", "detail": "onvif_soap_auth_failed status=401"}
    assert executor.circuit_open is True
    assert "401" in executor.circuit_reason


def test_circuit_open_short_circuits_without_touching_recorder_again():
    recorder = MagicMock()
    recorder.get_snapshot.side_effect = RecorderAuthError("status=401")
    executor = _make_executor(recorder)

    executor.capture_and_upload("cam-1")  # trips the breaker
    recorder.get_snapshot.reset_mock()

    result = executor.capture_and_upload("cam-2")  # a DIFFERENT camera

    assert result["ok"] is False
    assert result["reason"] == "auth"
    recorder.get_snapshot.assert_not_called()  # never touches the recorder again


def test_circuit_survives_across_many_cameras_until_reset():
    recorder = MagicMock()
    recorder.get_snapshot.side_effect = RecorderAuthError("status=403")
    executor = _make_executor(recorder)

    executor.capture_and_upload("cam-1")
    for cam in ("cam-2", "cam-3", "cam-4"):
        result = executor.capture_and_upload(cam)
        assert result["reason"] == "auth"

    assert recorder.get_snapshot.call_count == 1  # only the FIRST attempt ever hit the recorder


def test_reset_circuit_allows_capture_again():
    recorder = MagicMock()
    recorder.get_snapshot.side_effect = [RecorderAuthError("status=401"), b"jpeg-bytes"]
    http = MagicMock()
    http.post.return_value = _http_ok()
    executor = _make_executor(recorder, http)

    executor.capture_and_upload("cam-1")
    assert executor.circuit_open is True

    executor.reset_circuit()
    result = executor.capture_and_upload("cam-1")

    assert executor.circuit_open is False
    assert result == {"ok": True}
