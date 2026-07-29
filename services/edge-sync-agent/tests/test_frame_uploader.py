"""Tests for upload_frame: multipart request wiring against a fake http_client."""

from datetime import datetime, timezone

import pytest

from app.collector.frame_uploader import FrameUploadError, upload_frame

_CAPTURED_AT = datetime(2026, 7, 27, 10, 0, 0, tzinfo=timezone.utc)


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json_body = json_body or {}
        self.text = text

    def json(self):
        return self._json_body


class _FakeHttpClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[dict] = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self._response


class _RaisingHttpClient:
    def post(self, *args, **kwargs):
        raise ConnectionError("connection refused")


def test_successful_upload_returns_frame_id():
    client = _FakeHttpClient(_FakeResponse(201, {"data": {"frame_id": "frame-abc"}}))

    result = upload_frame(
        client, "https://api.example", "bearer-token", "cam-1", "rec-1",
        b"jpeg-bytes", "epi", _CAPTURED_AT,
    )

    assert result == "frame-abc"


def test_request_targets_frames_endpoint_with_auth_header():
    client = _FakeHttpClient(_FakeResponse(201, {"data": {"frame_id": "f1"}}))

    upload_frame(
        client, "https://api.example/", "bearer-token", "cam-1", "rec-1",
        b"jpeg-bytes", "epi", _CAPTURED_AT,
    )

    call = client.calls[0]
    assert call["url"] == "https://api.example/api/v1/edge/frames"
    assert call["headers"]["Authorization"] == "Bearer bearer-token"
    assert call["data"]["camera_id"] == "cam-1"
    assert call["data"]["recorder_id"] == "rec-1"
    assert call["data"]["module_code"] == "epi"
    assert call["data"]["captured_at"] == _CAPTURED_AT.isoformat()
    assert call["files"]["file"] == ("frame.jpg", b"jpeg-bytes", "image/jpeg")


def test_non_201_response_raises_frame_upload_error():
    client = _FakeHttpClient(_FakeResponse(422, text="Extensão não suportada"))

    with pytest.raises(FrameUploadError, match="422"):
        upload_frame(
            client, "https://api.example", "bearer-token", "cam-1", "rec-1",
            b"jpeg-bytes", "epi", _CAPTURED_AT,
        )


def test_network_error_raises_frame_upload_error():
    with pytest.raises(FrameUploadError):
        upload_frame(
            _RaisingHttpClient(), "https://api.example", "bearer-token", "cam-1", "rec-1",
            b"jpeg-bytes", "epi", _CAPTURED_AT,
        )
