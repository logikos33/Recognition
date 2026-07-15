"""Tests for the RecorderClient abstraction: interface, fail-loud default, mock stub."""

from datetime import datetime, timedelta, timezone

import pytest

from app.recorder_client import (
    InMemoryRecorderClient,
    NotConfiguredRecorderClient,
    RecorderClient,
    RecorderError,
    RecorderEvent,
)

_NOW = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)


def test_not_configured_client_satisfies_protocol():
    assert isinstance(NotConfiguredRecorderClient(), RecorderClient)


def test_in_memory_client_satisfies_protocol():
    assert isinstance(InMemoryRecorderClient(), RecorderClient)


def test_not_configured_list_events_raises():
    client = NotConfiguredRecorderClient()
    with pytest.raises(RecorderError):
        client.list_events("cam-1", _NOW, _NOW)


def test_not_configured_stream_clip_raises_on_first_next():
    client = NotConfiguredRecorderClient()
    gen = client.stream_clip("cam-1", _NOW, _NOW)
    with pytest.raises(RecorderError):
        next(gen)


def test_not_configured_health_reports_unreachable():
    health = NotConfiguredRecorderClient().health()
    assert health.reachable is False
    assert "task-091" in health.detail


def test_in_memory_list_events_filters_by_camera_and_window():
    events = [
        RecorderEvent(
            event_id="evt-1",
            camera_id="cam-1",
            started_at=_NOW,
            ended_at=_NOW + timedelta(seconds=30),
            event_type="motion",
        ),
        RecorderEvent(
            event_id="evt-2",
            camera_id="cam-2",
            started_at=_NOW,
            ended_at=_NOW + timedelta(seconds=30),
            event_type="motion",
        ),
    ]
    client = InMemoryRecorderClient(events=events)

    result = client.list_events("cam-1", _NOW, _NOW + timedelta(minutes=5))

    assert [e.event_id for e in result] == ["evt-1"]


def test_in_memory_stream_clip_yields_configured_chunks():
    client = InMemoryRecorderClient(clip_chunks=[b"a", b"b", b"c"])

    chunks = list(client.stream_clip("cam-1", _NOW, _NOW + timedelta(seconds=1)))

    assert chunks == [b"a", b"b", b"c"]


def test_in_memory_stream_clip_raises_when_unreachable():
    client = InMemoryRecorderClient(reachable=False)

    with pytest.raises(RecorderError):
        list(client.stream_clip("cam-1", _NOW, _NOW + timedelta(seconds=1)))


def test_in_memory_health_reflects_reachable_flag():
    assert InMemoryRecorderClient(reachable=True).health().reachable is True
    assert InMemoryRecorderClient(reachable=False).health().reachable is False
