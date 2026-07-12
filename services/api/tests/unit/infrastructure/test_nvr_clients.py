"""
Tests: infrastructure/nvr/ — clients ONVIF/Hikvision ISAPI/RTSP genérico
(WS-B1, ADR-0034). Requests sempre mockadas — sem hardware disponível
(ver docstring de infrastructure/nvr/__init__.py).
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.core.exceptions import ValidationError
from app.infrastructure.nvr.base import RecordingSegment
from app.infrastructure.nvr.factory import get_nvr_client
from app.infrastructure.nvr.generic_rtsp_client import GenericRtspPlaybackClient
from app.infrastructure.nvr.hikvision_isapi_client import HikvisionIsapiClient
from app.infrastructure.nvr.onvif_client import OnvifClient


class TestHikvisionIsapiClient:
    def _client(self):
        return HikvisionIsapiClient(host="10.0.0.5", port=80, username="admin", password="pw")

    def test_test_connection_true_on_200(self):
        client = self._client()
        mock_resp = MagicMock(status_code=200)
        with patch("requests.get", return_value=mock_resp):
            assert client.test_connection() is True

    def test_test_connection_false_on_network_error(self):
        client = self._client()
        with patch("requests.get", side_effect=requests.ConnectionError("unreachable")):
            assert client.test_connection() is False

    def test_search_recordings_parses_namespaced_xml(self):
        client = self._client()
        xml = (
            '<?xml version="1.0"?>'
            '<CMSearchResult xmlns="http://www.hikvision.com/ver20/XMLSchema">'
            "<matchList><searchMatchItem>"
            "<timeSpan>"
            "<startTime>2026-07-10T10:00:00Z</startTime>"
            "<endTime>2026-07-10T10:05:00Z</endTime>"
            "</timeSpan>"
            "</searchMatchItem></matchList>"
            "</CMSearchResult>"
        )
        mock_resp = MagicMock(text=xml)
        mock_resp.raise_for_status.return_value = None
        with patch("requests.post", return_value=mock_resp):
            segments = client.search_recordings(
                1, datetime(2026, 7, 10, 9), datetime(2026, 7, 10, 11)
            )
        assert len(segments) == 1
        assert segments[0].channel == 1
        assert segments[0].start == datetime(2026, 7, 10, 10, 0, 0)
        assert segments[0].end == datetime(2026, 7, 10, 10, 5, 0)

    def test_search_recordings_parses_xml_without_namespace(self):
        """Alguns firmwares devolvem sem namespace declarado explicitamente."""
        client = self._client()
        xml = (
            "<CMSearchResult><matchList><searchMatchItem>"
            "<timeSpan><startTime>2026-07-10T10:00:00Z</startTime>"
            "<endTime>2026-07-10T10:05:00Z</endTime></timeSpan>"
            "</searchMatchItem></matchList></CMSearchResult>"
        )
        mock_resp = MagicMock(text=xml)
        mock_resp.raise_for_status.return_value = None
        with patch("requests.post", return_value=mock_resp):
            segments = client.search_recordings(
                1, datetime(2026, 7, 10, 9), datetime(2026, 7, 10, 11)
            )
        assert len(segments) == 1

    def test_search_recordings_malformed_xml_returns_empty(self):
        client = self._client()
        mock_resp = MagicMock(text="not xml at all <<<")
        mock_resp.raise_for_status.return_value = None
        with patch("requests.post", return_value=mock_resp):
            segments = client.search_recordings(
                1, datetime(2026, 7, 10, 9), datetime(2026, 7, 10, 11)
            )
        assert segments == []

    def test_build_playback_url_includes_timespan(self):
        client = self._client()
        segment = RecordingSegment(
            channel=1, start=datetime(2026, 7, 10, 10), end=datetime(2026, 7, 10, 10, 5),
            playback_ref="x",
        )
        url = client.build_playback_url(segment)
        assert url.startswith("rtsp://10.0.0.5:554/Streaming/tracks/101")
        assert "starttime=2026-07-10T10:00:00Z" in url
        assert "endtime=2026-07-10T10:05:00Z" in url


class TestOnvifClient:
    def _client(self):
        return OnvifClient(host="10.0.0.6", port=8000, username="admin", password="pw")

    def test_test_connection_true_on_success(self):
        client = self._client()
        mock_resp = MagicMock(text="<Envelope/>")
        mock_resp.raise_for_status.return_value = None
        with patch("requests.post", return_value=mock_resp):
            assert client.test_connection() is True

    def test_test_connection_false_on_network_error(self):
        client = self._client()
        with patch("requests.post", side_effect=requests.ConnectionError("down")):
            assert client.test_connection() is False

    def test_search_recordings_filters_by_requested_window(self):
        client = self._client()
        find_resp = MagicMock(
            text='<Envelope><Body><FindRecordingsResponse>'
                 '<SearchToken>tok-123</SearchToken>'
                 '</FindRecordingsResponse></Body></Envelope>'
        )
        find_resp.raise_for_status.return_value = None
        results_resp = MagicMock(
            text=(
                "<Envelope><Body>"
                "<RecordingInformation><Time>2026-07-10T10:02:00Z</Time></RecordingInformation>"
                "<RecordingInformation><Time>2026-07-10T08:00:00Z</Time></RecordingInformation>"
                "</Body></Envelope>"
            )
        )
        results_resp.raise_for_status.return_value = None
        with patch("requests.post", side_effect=[find_resp, results_resp]):
            segments = client.search_recordings(
                2, datetime(2026, 7, 10, 9), datetime(2026, 7, 10, 11)
            )
        # só o registro dentro da janela 09:00-11:00 deve sobreviver
        assert len(segments) == 1
        assert segments[0].start == datetime(2026, 7, 10, 10, 2, 0)

    def test_build_playback_url_extracts_uri(self):
        client = self._client()
        resp = MagicMock(
            text='<Envelope><Body><GetReplayUriResponse>'
                 '<Uri>rtsp://10.0.0.6:554/replay?token=abc</Uri>'
                 '</GetReplayUriResponse></Body></Envelope>'
        )
        resp.raise_for_status.return_value = None
        segment = RecordingSegment(
            channel=1, start=datetime(2026, 7, 10, 10), end=datetime(2026, 7, 10, 10, 5),
            playback_ref="x",
        )
        with patch("requests.post", return_value=resp):
            url = client.build_playback_url(segment)
        assert url == "rtsp://10.0.0.6:554/replay?token=abc"

    def test_build_playback_url_raises_when_uri_missing(self):
        client = self._client()
        resp = MagicMock(text="<Envelope><Body><Fault/></Body></Envelope>")
        resp.raise_for_status.return_value = None
        segment = RecordingSegment(
            channel=1, start=datetime(2026, 7, 10, 10), end=datetime(2026, 7, 10, 10, 5),
            playback_ref="x",
        )
        with patch("requests.post", return_value=resp):
            with pytest.raises(RuntimeError, match="GetReplayUri"):
                client.build_playback_url(segment)


class TestGenericRtspPlaybackClient:
    def _client(self):
        return GenericRtspPlaybackClient(host="10.0.0.7", port=554, username="admin", password="pw")

    def test_test_connection_true_when_socket_connects(self):
        client = self._client()
        with patch("socket.create_connection", return_value=MagicMock()):
            assert client.test_connection() is True

    def test_test_connection_false_when_socket_fails(self):
        client = self._client()
        with patch("socket.create_connection", side_effect=OSError("refused")):
            assert client.test_connection() is False

    def test_search_recordings_returns_single_segment_covering_window(self):
        client = self._client()
        start, end = datetime(2026, 7, 10, 9), datetime(2026, 7, 10, 11)
        segments = client.search_recordings(3, start, end)
        assert len(segments) == 1
        assert segments[0].start == start
        assert segments[0].end == end
        assert segments[0].channel == 3

    def test_build_playback_url_encodes_credentials(self):
        client = GenericRtspPlaybackClient(
            host="10.0.0.7", port=554, username="ad min", password="p@ss"
        )
        segment = RecordingSegment(
            channel=1, start=datetime(2026, 7, 10, 10), end=datetime(2026, 7, 10, 10, 5),
            playback_ref="x",
        )
        url = client.build_playback_url(segment)
        assert "ad%20min" in url
        assert "p%40ss" in url
        assert "channel=1" in url


class TestNvrClientFactory:
    def test_onvif_protocol_returns_onvif_client(self):
        recorder = {"host": "10.0.0.5", "port": 80, "username": "admin", "protocol": "onvif"}
        client = get_nvr_client(recorder, "pw")
        assert isinstance(client, OnvifClient)

    def test_hikvision_protocol_returns_isapi_client(self):
        recorder = {"host": "10.0.0.5", "port": 80, "username": "admin", "protocol": "hikvision"}
        client = get_nvr_client(recorder, "pw")
        assert isinstance(client, HikvisionIsapiClient)

    def test_dahua_intelbras_rtsp_fall_back_to_generic(self):
        for protocol in ("dahua", "intelbras", "rtsp"):
            recorder = {"host": "10.0.0.5", "port": 554, "username": "a", "protocol": protocol}
            client = get_nvr_client(recorder, "pw")
            assert isinstance(client, GenericRtspPlaybackClient)

    def test_unknown_protocol_falls_back_to_generic(self):
        recorder = {"host": "10.0.0.5", "port": 554, "username": "a", "protocol": "made-up"}
        client = get_nvr_client(recorder, "pw")
        assert isinstance(client, GenericRtspPlaybackClient)


class TestRTSPUrlValidatorIntegration:
    """SSRF/injection guard — clients devem recusar host malicioso."""

    def test_hikvision_test_connection_rejects_loopback(self):
        client = HikvisionIsapiClient(host="127.0.0.1", port=80, username="a", password="b")
        with pytest.raises(ValidationError):
            client.test_connection()

    def test_generic_rtsp_build_playback_url_rejects_command_injection(self):
        client = GenericRtspPlaybackClient(host="10.0.0.7; rm -rf /", port=554, username="a", password="b")
        segment = RecordingSegment(
            channel=1, start=datetime(2026, 7, 10, 10), end=datetime(2026, 7, 10, 10, 5),
            playback_ref="x",
        )
        with pytest.raises(ValidationError):
            client.build_playback_url(segment)
