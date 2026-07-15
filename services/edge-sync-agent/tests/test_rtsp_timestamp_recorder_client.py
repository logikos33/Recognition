"""Tests for RtspTimestampRecorderClient: the no-search-API RTSP fallback
used for Intelbras/Dahua/generic gravadores (RVB's actual hardware,
CLAUDE.md). No timeline index exists in this protocol — tests assert the
documented "one synthetic event per window" behavior, not a real search.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.recorder_client import RecorderClient, RecorderError
from app.rtsp_timestamp_recorder_client import RtspTimestampRecorderClient

_NOW = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
_CAMERA_ID = "cam-1"
_CHANNEL_MAP = {_CAMERA_ID: 2}


def _make_client() -> RtspTimestampRecorderClient:
    return RtspTimestampRecorderClient(
        host="10.0.0.9",
        port=554,
        username="admin",
        password="s3cr3t",
        channel_map=_CHANNEL_MAP,
    )


def test_satisfies_recorder_client_protocol():
    assert isinstance(_make_client(), RecorderClient)


def test_list_events_returns_one_synthetic_event_covering_window():
    client = _make_client()
    start = _NOW - timedelta(minutes=10)
    events = client.list_events(_CAMERA_ID, start, _NOW)

    assert len(events) == 1
    assert events[0].camera_id == _CAMERA_ID
    assert events[0].started_at == start
    assert events[0].ended_at == _NOW
    assert events[0].description is not None  # documents the "no real index" limitation


def test_list_events_unmapped_camera_raises():
    client = _make_client()
    with pytest.raises(RecorderError):
        client.list_events("unmapped", _NOW - timedelta(minutes=10), _NOW)


def test_health_reports_reachable_when_port_accepts_connection(monkeypatch):
    class _FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "app.rtsp_timestamp_recorder_client.socket.create_connection",
        lambda addr, timeout: _FakeSocket(),
    )
    client = _make_client()
    health = client.health()
    assert health.reachable is True


def test_health_reports_unreachable_on_connection_error(monkeypatch):
    def _raise(addr, timeout):
        raise OSError("refused")

    monkeypatch.setattr(
        "app.rtsp_timestamp_recorder_client.socket.create_connection", _raise
    )
    client = _make_client()
    health = client.health()
    assert health.reachable is False


def test_stream_clip_builds_dahua_style_timestamp_url(monkeypatch):
    client = _make_client()
    start = datetime(2026, 7, 15, 11, 30, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 15, 11, 30, 30, tzinfo=timezone.utc)

    captured = {}

    def _fake_stream_rtsp_clip(url, duration_seconds):
        captured["url"] = url
        captured["duration"] = duration_seconds
        yield b"clip-bytes"

    monkeypatch.setattr(
        "app.rtsp_timestamp_recorder_client.stream_rtsp_clip", _fake_stream_rtsp_clip
    )

    chunks = list(client.stream_clip(_CAMERA_ID, start, end))

    assert chunks == [b"clip-bytes"]
    assert captured["duration"] == 30.0
    assert "starttime=2026_07_15_11_30_00" in captured["url"]
    assert "endtime=2026_07_15_11_30_30" in captured["url"]
    assert "channel=2" in captured["url"]


def test_stream_clip_unmapped_camera_raises_before_building_url():
    client = _make_client()
    with pytest.raises(RecorderError):
        list(client.stream_clip("unmapped", _NOW - timedelta(seconds=10), _NOW))
