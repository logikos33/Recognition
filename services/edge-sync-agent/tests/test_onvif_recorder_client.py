"""Tests for OnvifRecorderClient: SOAP envelope wiring against mocked HTTP,
RecordingSegment→RecorderEvent conversion, channel_map enforcement,
network-error → RecorderError translation, and WS-Security UsernameToken/
PasswordDigest authentication (found broken — `_post_soap` sent zero auth —
while validating ADR-0052 against real hardware, an Intelbras iNVD 3032).

No real ONVIF device is exercised (none available) — this proves the SOAP
parsing/building logic and the RecorderClient contract, per the same
"spec-compliant, not hardware-validated" discipline as the ported monolith
source (services/api/app/infrastructure/nvr/onvif_client.py). The PasswordDigest
auth *algorithm* itself is verified against a fixed nonce/created/password
vector, independently cross-checked with `openssl dgst -sha1 | openssl base64`
outside this codebase (see `test_password_digest_matches_known_vector`).
"""

import base64
import hashlib
import re
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.onvif_recorder_client import (
    OnvifRecorderClient,
    _password_digest,
    _ws_security_header,
)
from app.recorder_client import RecorderAuthError, RecorderClient, RecorderError

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

_STREAM_URI_RESPONSE = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <trt:GetStreamUriResponse xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
      <MediaUri><Uri>rtsp://10.0.0.5:554/live?token=abc</Uri></MediaUri>
    </trt:GetStreamUriResponse>
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


def test_capture_frame_resolves_stream_uri_and_pulls_bytes(monkeypatch):
    http_client = _FakeHttpClient([_STREAM_URI_RESPONSE])
    client = _make_client(http_client)

    captured = {}

    def _fake_capture_still_frame(url):
        captured["url"] = url
        return b"jpeg-bytes"

    monkeypatch.setattr(
        "app.onvif_recorder_client.capture_still_frame", _fake_capture_still_frame
    )

    result = client.capture_frame(_CAMERA_ID)

    assert result == b"jpeg-bytes"
    assert captured["url"] == "rtsp://10.0.0.5:554/live?token=abc"


def test_capture_frame_unmapped_camera_raises_recorder_error():
    client = _make_client(_FakeHttpClient([]))
    with pytest.raises(RecorderError):
        client.capture_frame("unmapped-camera")


def test_get_stream_uri_missing_uri_raises_recorder_error():
    http_client = _FakeHttpClient(["<GetStreamUriResponse/>"])
    client = _make_client(http_client)
    with pytest.raises(RecorderError):
        client.capture_frame(_CAMERA_ID)


# ── get_snapshot (D-85: ONVIF GetSnapshotUri + RTSP-frame fallback) ─────────

_SNAPSHOT_URI_RESPONSE = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <trt:GetSnapshotUriResponse xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
      <MediaUri><Uri>http://10.0.0.5:8080/onvif-http/snapshot?ch=3</Uri></MediaUri>
    </trt:GetSnapshotUriResponse>
  </s:Body>
</s:Envelope>"""


class _FakeSnapshotResponse:
    def __init__(self, status_code: int = 200, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content
        self.text = content.decode(errors="replace")


class _FakeSnapshotHttpClient:
    """Like _FakeHttpClient (queued .post() responses for SOAP) but also
    supports .get() (queued responses for the snapshot URI fetch)."""

    def __init__(
        self,
        post_responses: list[str],
        get_responses: "list[_FakeSnapshotResponse] | None" = None,
    ) -> None:
        self._post_responses = list(post_responses)
        self._get_responses = list(get_responses or [])
        self.get_calls: list[tuple] = []

    def post(self, url, content=None, headers=None, timeout=None):
        if not self._post_responses:
            raise AssertionError("no more fake POST responses queued")
        return _FakeResponse(self._post_responses.pop(0))

    def get(self, url, timeout=None, auth=None):
        self.get_calls.append((url, auth))
        if not self._get_responses:
            raise AssertionError("no more fake GET responses queued")
        return self._get_responses.pop(0)


def test_get_snapshot_resolves_snapshot_uri_and_fetches_bytes():
    http_client = _FakeSnapshotHttpClient(
        [_SNAPSHOT_URI_RESPONSE],
        [_FakeSnapshotResponse(200, b"jpeg-bytes")],
    )
    client = _make_client(http_client)

    result = client.get_snapshot(_CAMERA_ID)

    assert result == b"jpeg-bytes"
    assert http_client.get_calls[0][0] == "http://10.0.0.5:8080/onvif-http/snapshot?ch=3"


def test_get_snapshot_retries_once_with_digest_auth_on_401():
    http_client = _FakeSnapshotHttpClient(
        [_SNAPSHOT_URI_RESPONSE],
        [_FakeSnapshotResponse(401, b""), _FakeSnapshotResponse(200, b"jpeg-bytes")],
    )
    client = _make_client(http_client)

    result = client.get_snapshot(_CAMERA_ID)

    assert result == b"jpeg-bytes"
    assert len(http_client.get_calls) == 2
    assert http_client.get_calls[0][1] is None  # first attempt: no auth
    assert http_client.get_calls[1][1] is not None  # retry: digest auth


def test_get_snapshot_persistent_401_raises_recorder_auth_error_not_generic():
    http_client = _FakeSnapshotHttpClient(
        [_SNAPSHOT_URI_RESPONSE],
        [_FakeSnapshotResponse(401, b""), _FakeSnapshotResponse(403, b"")],
    )
    client = _make_client(http_client)

    with pytest.raises(RecorderAuthError):
        client.get_snapshot(_CAMERA_ID)


def test_get_snapshot_falls_back_to_capture_frame_when_snapshot_uri_unavailable(monkeypatch):
    """GetSnapshotUri fails for a non-auth reason (e.g. unsupported by this
    NVR firmware) -> falls back to the live-frame RTSP grab, same bytes path
    as capture_frame."""
    http_client = _FakeHttpClient(["<Fault>not supported</Fault>", _STREAM_URI_RESPONSE])
    client = _make_client(http_client)

    def _fake_capture_still_frame(url):
        return b"fallback-frame-bytes"

    monkeypatch.setattr(
        "app.onvif_recorder_client.capture_still_frame", _fake_capture_still_frame
    )

    result = client.get_snapshot(_CAMERA_ID)

    assert result == b"fallback-frame-bytes"


def test_get_snapshot_auth_failure_on_soap_call_does_not_fall_back():
    """A 401/403 resolving GetSnapshotUri (SOAP layer, not the URI fetch)
    must propagate as RecorderAuthError WITHOUT trying capture_frame — reusing
    a rejected credential over RTSP is still hammering the same device."""

    class _AuthFailingHttpClient:
        def post(self, url, content=None, headers=None, timeout=None):
            return _FakeResponse("<Fault/>", status_code=401)

        def get(self, *a, **k):  # pragma: no cover — must never be called
            raise AssertionError("get_snapshot must not fall back after a SOAP auth failure")

    client = _make_client(_AuthFailingHttpClient())

    with pytest.raises(RecorderAuthError):
        client.get_snapshot(_CAMERA_ID)


def test_get_snapshot_missing_uri_falls_back_to_capture_frame(monkeypatch):
    http_client = _FakeHttpClient(["<GetSnapshotUriResponse/>", _STREAM_URI_RESPONSE])
    client = _make_client(http_client)
    monkeypatch.setattr(
        "app.onvif_recorder_client.capture_still_frame", lambda url: b"fallback-bytes"
    )

    assert client.get_snapshot(_CAMERA_ID) == b"fallback-bytes"


def test_get_snapshot_empty_body_raises_recorder_error():
    http_client = _FakeSnapshotHttpClient(
        [_SNAPSHOT_URI_RESPONSE], [_FakeSnapshotResponse(200, b"")]
    )
    client = _make_client(http_client)

    with pytest.raises(RecorderError):
        client.get_snapshot(_CAMERA_ID)


def test_get_snapshot_unmapped_camera_raises_recorder_error():
    client = _make_client(_FakeHttpClient([]))
    with pytest.raises(RecorderError):
        client.get_snapshot("unmapped-camera")


def test_satisfies_recorder_client_protocol_with_get_snapshot():
    assert hasattr(_make_client(_FakeHttpClient([])), "get_snapshot")


# ── WS-Security UsernameToken / PasswordDigest ──────────────────────────────
#
# `_post_soap` sent zero authentication before this fix — turning on
# RECORDER_PROTOCOL=onvif meant every request the gravador received had no
# credential at all, an obscure runtime failure (discovered validating
# ADR-0052 against a real Intelbras iNVD 3032).


def test_password_digest_matches_known_vector():
    """Digest = Base64(SHA1(nonce_octets + created_utf8 + password_utf8)) —
    WS-Security UsernameToken Profile 1.0, the ONVIF-mandated scheme.

    Vector fixed for this test (nonce=b"0123456789abcdef", created=
    "2024-01-01T00:00:00Z", password="sesame") and independently
    cross-checked OUTSIDE this codebase with:
        printf '%s' "$(python3 -c '...')" | openssl dgst -sha1 -binary | openssl base64
    Both computations agree: "fGWfnPzmGng6DI9G3QZ8kU4Dq7c=".
    """
    nonce = b"0123456789abcdef"
    created = "2024-01-01T00:00:00Z"
    password = "sesame"

    digest = _password_digest(nonce, created, password)

    assert digest == "fGWfnPzmGng6DI9G3QZ8kU4Dq7c="
    # Re-derive independently within the test too (belt and suspenders): the
    # production function must implement exactly nonce||created||password,
    # SHA1, then base64 — nothing more, nothing less.
    expected = base64.b64encode(
        hashlib.sha1(nonce + created.encode("utf-8") + password.encode("utf-8")).digest()
    ).decode("ascii")
    assert digest == expected


def test_password_digest_changes_with_any_input():
    base = _password_digest(b"0123456789abcdef", "2024-01-01T00:00:00Z", "sesame")
    assert base != _password_digest(b"fedcba9876543210", "2024-01-01T00:00:00Z", "sesame")
    assert base != _password_digest(b"0123456789abcdef", "2024-01-01T00:00:01Z", "sesame")
    assert base != _password_digest(b"0123456789abcdef", "2024-01-01T00:00:00Z", "other")


def test_ws_security_header_contains_username_token_elements():
    header = _ws_security_header("admin", "supersecret")

    assert "<wsse:Security" in header
    assert "<wsse:UsernameToken" in header
    assert "<wsse:Username>admin</wsse:Username>" in header
    assert 'Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest"' in header  # noqa: E501
    assert "<wsse:Nonce" in header
    assert "<wsu:Created>" in header
    # Password itself never appears in plaintext anywhere in the header.
    assert "supersecret" not in header


def test_ws_security_header_digest_is_internally_consistent():
    """Extracts nonce/created/digest from a generated header and proves the
    digest matches what `_password_digest` computes for those exact values —
    end-to-end proof the header-building and digest math agree."""
    username, password = "admin", "s3cr3t!"
    header = _ws_security_header(username, password)

    nonce_b64 = re.search(r"<wsse:Nonce[^>]*>([^<]+)</wsse:Nonce>", header).group(1)
    created = re.search(r"<wsu:Created>([^<]+)</wsu:Created>", header).group(1)
    digest = re.search(r"<wsse:Password[^>]*>([^<]+)</wsse:Password>", header).group(1)

    nonce = base64.b64decode(nonce_b64)
    assert digest == _password_digest(nonce, created, password)


def test_ws_security_header_generates_fresh_nonce_each_call():
    """Reusing a nonce defeats PasswordDigest's replay defense — some NVR
    firmwares reject a repeated nonce outright. Each call must mint a new one."""
    header_a = _ws_security_header("admin", "secret")
    header_b = _ws_security_header("admin", "secret")

    nonce_a = re.search(r"<wsse:Nonce[^>]*>([^<]+)</wsse:Nonce>", header_a).group(1)
    nonce_b = re.search(r"<wsse:Nonce[^>]*>([^<]+)</wsse:Nonce>", header_b).group(1)
    assert nonce_a != nonce_b


def test_soap_request_body_carries_ws_security_header():
    """End-to-end through `_post_soap`: the SOAP envelope actually posted to
    the gravador contains the UsernameToken, not just that the header
    *function* produces one in isolation."""
    http_client = _FakeHttpClient(["<GetSystemDateAndTimeResponse/>"])
    client = _make_client(http_client)

    client.health()

    url, body = http_client.calls[0]
    assert "<wsse:UsernameToken" in body
    assert "<wsse:Username>admin</wsse:Username>" in body
    assert "secret" not in body  # the fixture password, never sent in the clear


def test_init_rejects_empty_username():
    with pytest.raises(RecorderError):
        OnvifRecorderClient(
            host="10.0.0.5", port=80, username="", password="pw", channel_map=_CHANNEL_MAP
        )


def test_init_rejects_empty_password():
    with pytest.raises(RecorderError):
        OnvifRecorderClient(
            host="10.0.0.5", port=80, username="admin", password="", channel_map=_CHANNEL_MAP
        )


def test_init_rejects_both_empty():
    with pytest.raises(RecorderError):
        OnvifRecorderClient(
            host="10.0.0.5", port=80, username="", password="", channel_map=_CHANNEL_MAP
        )
