"""Tests for OnvifRecorderClient: SOAP envelope wiring against mocked HTTP,
RecordingSegment→RecorderEvent conversion, channel_map enforcement, and
network-error → RecorderError translation.

No real ONVIF device is exercised (none available) — this proves the SOAP
parsing/building logic and the RecorderClient contract, per the same
"spec-compliant, not hardware-validated" discipline as the ported monolith
source (services/api/app/infrastructure/nvr/onvif_client.py).
"""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.onvif_recorder_client import OnvifRecorderClient
from app.recorder_client import RecorderClient, RecorderError

_NOW = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
_CAMERA_ID = "11111111-1111-1111-1111-111111111111"
_CHANNEL_MAP = {_CAMERA_ID: 3}

_FIND_RECORDINGS_RESPONSE = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <tse:FindRecordingsResponse xmlns:tse="http://www.onvif.org/ver10/search/wsdl">
      <SearchToken>token-abc-123</SearchToken>
    </tse:FindRecordingsResponse>
  </s:Body>
</s:Envelope>"""

_SEARCH_RESULTS_RESPONSE = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <tse:GetRecordingSearchResultsResponse xmlns:tse="http://www.onvif.org/ver10/search/wsdl">
      <ResultList>
        <RecordingInformation>
          <Time>2026-07-15T11:55:00Z</Time>
        </RecordingInformation>
        <RecordingInformation>
          <Time>2026-07-15T09:00:00Z</Time>
        </RecordingInformation>
      </ResultList>
    </tse:GetRecordingSearchResultsResponse>
  </s:Body>
</s:Envelope>"""

_REPLAY_URI_RESPONSE = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <trp:GetReplayUriResponse xmlns:trp="http://www.onvif.org/ver10/replay/wsdl">
      <Uri>rtsp://10.0.0.5:554/replay?token=abc</Uri>
    </trp:GetReplayUriResponse>
  </s:Body>
</s:Envelope>"""


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


class _FakeHttpClient:
    """Returns queued responses in order, one per .post() call; records calls."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def post(self, url, content=None, headers=None, timeout=None):
        self.calls.append((url, content))
        if not self._responses:
            raise AssertionError("no more fake responses queued")
        return _FakeResponse(self._responses.pop(0))


class _RaisingHttpClient:
    def post(self, *args, **kwargs):
        raise httpx.ConnectError("connection refused")


def _make_client(http_client):
    return OnvifRecorderClient(
        host="10.0.0.5",
        port=8080,
        username="admin",
        password="secret",
        channel_map=_CHANNEL_MAP,
        http_client=http_client,
    )


def test_satisfies_recorder_client_protocol():
    assert isinstance(_make_client(_FakeHttpClient([])), RecorderClient)


def test_health_ok_on_successful_ping():
    client = _make_client(_FakeHttpClient(["<GetSystemDateAndTimeResponse/>"]))
    health = client.health()
    assert health.reachable is True


def test_health_reports_unreachable_on_network_error():
    client = _make_client(_RaisingHttpClient())
    health = client.health()
    assert health.reachable is False
    assert health.detail


def test_list_events_parses_recordings_within_window():
    http_client = _FakeHttpClient([_FIND_RECORDINGS_RESPONSE, _SEARCH_RESULTS_RESPONSE])
    client = _make_client(http_client)

    events = client.list_events(_CAMERA_ID, _NOW - timedelta(hours=1), _NOW)

    assert len(events) == 1  # only the marker inside [start, end] survives
    assert events[0].camera_id == _CAMERA_ID
    assert events[0].event_type == "recording"
    assert events[0].started_at == datetime(2026, 7, 15, 11, 55, 0, tzinfo=timezone.utc)


def test_list_events_uses_search_token_from_find_response():
    http_client = _FakeHttpClient([_FIND_RECORDINGS_RESPONSE, _SEARCH_RESULTS_RESPONSE])
    client = _make_client(http_client)

    client.list_events(_CAMERA_ID, _NOW - timedelta(hours=1), _NOW)

    _, second_body = http_client.calls[1]
    assert "token-abc-123" in second_body


def test_list_events_unmapped_camera_raises_recorder_error():
    client = _make_client(_FakeHttpClient([]))
    with pytest.raises(RecorderError):
        client.list_events("unmapped-camera", _NOW - timedelta(hours=1), _NOW)


def test_list_events_network_error_raises_recorder_error():
    client = _make_client(_RaisingHttpClient())
    with pytest.raises(RecorderError):
        client.list_events(_CAMERA_ID, _NOW - timedelta(hours=1), _NOW)


def test_stream_clip_resolves_replay_uri_and_pulls_bytes(monkeypatch):
    http_client = _FakeHttpClient([_REPLAY_URI_RESPONSE])
    client = _make_client(http_client)

    captured = {}

    def _fake_stream_rtsp_clip(url, duration_seconds):
        captured["url"] = url
        captured["duration"] = duration_seconds
        yield b"clip-bytes"

    monkeypatch.setattr(
        "app.onvif_recorder_client.stream_rtsp_clip", _fake_stream_rtsp_clip
    )

    chunks = list(client.stream_clip(_CAMERA_ID, _NOW - timedelta(seconds=30), _NOW))

    assert chunks == [b"clip-bytes"]
    assert captured["url"] == "rtsp://10.0.0.5:554/replay?token=abc"
    assert captured["duration"] == 30.0


def test_get_replay_uri_missing_uri_raises_recorder_error():
    http_client = _FakeHttpClient(["<GetReplayUriResponse/>"])
    client = _make_client(http_client)
    with pytest.raises(RecorderError):
        list(client.stream_clip(_CAMERA_ID, _NOW - timedelta(seconds=30), _NOW))
