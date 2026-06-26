"""Tests: probe_handler.py pure functions — _check_ip_ssrf, _resolve_and_pin,
_ffprobe_stream, _check_gateway_available."""
import ipaddress
import json
import socket
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ValidationError


# ---------------------------------------------------------------------------
# _check_ip_ssrf
# ---------------------------------------------------------------------------

class TestCheckIpSsrf:

    def _call(self, ip_str):
        from app.api.v1.cameras.probe_handler import _check_ip_ssrf
        _check_ip_ssrf(ipaddress.ip_address(ip_str))

    def test_loopback_raises_validation_error(self):
        with pytest.raises(ValidationError, match="loopback"):
            self._call("127.0.0.1")

    def test_ipv6_loopback_raises_validation_error(self):
        with pytest.raises(ValidationError, match="loopback"):
            self._call("::1")

    def test_link_local_raises_validation_error(self):
        with pytest.raises(ValidationError, match="link-local"):
            self._call("169.254.1.1")

    def test_ipv6_link_local_raises_validation_error(self):
        with pytest.raises(ValidationError, match="link-local"):
            self._call("fe80::1")

    def test_valid_private_ip_does_not_raise(self):
        self._call("192.168.1.100")  # RFC1918 — cameras live on LAN

    def test_valid_public_ip_does_not_raise(self):
        self._call("8.8.8.8")

    def test_private_10_network_does_not_raise(self):
        self._call("10.0.0.1")

    def test_private_172_network_does_not_raise(self):
        self._call("172.16.0.1")


# ---------------------------------------------------------------------------
# _resolve_and_pin
# ---------------------------------------------------------------------------

class TestResolveAndPin:

    def test_literal_valid_ip_returns_same(self):
        from app.api.v1.cameras.probe_handler import _resolve_and_pin
        assert _resolve_and_pin("192.168.1.50") == "192.168.1.50"

    def test_literal_loopback_raises(self):
        from app.api.v1.cameras.probe_handler import _resolve_and_pin
        with pytest.raises(ValidationError):
            _resolve_and_pin("127.0.0.1")

    def test_literal_link_local_raises(self):
        from app.api.v1.cameras.probe_handler import _resolve_and_pin
        with pytest.raises(ValidationError):
            _resolve_and_pin("169.254.0.1")

    def test_hostname_dns_resolution_mocked(self):
        from app.api.v1.cameras.probe_handler import _resolve_and_pin
        mock_records = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.50", 0))
        ]
        with patch("socket.getaddrinfo", return_value=mock_records):
            result = _resolve_and_pin("camera.local")
        assert result == "192.168.1.50"

    def test_hostname_dns_failure_raises_validation_error(self):
        from app.api.v1.cameras.probe_handler import _resolve_and_pin
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("not found")):
            with pytest.raises(ValidationError, match="não pôde ser resolvido"):
                _resolve_and_pin("nonexistent.camera")

    def test_hostname_empty_records_raises(self):
        from app.api.v1.cameras.probe_handler import _resolve_and_pin
        with patch("socket.getaddrinfo", return_value=[]):
            with pytest.raises(ValidationError, match="não retornou endereços"):
                _resolve_and_pin("empty.camera")

    def test_hostname_resolves_to_loopback_raises(self):
        from app.api.v1.cameras.probe_handler import _resolve_and_pin
        mock_records = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))
        ]
        with patch("socket.getaddrinfo", return_value=mock_records):
            with pytest.raises(ValidationError):
                _resolve_and_pin("evil.camera")


# ---------------------------------------------------------------------------
# _ffprobe_stream
# ---------------------------------------------------------------------------

class TestFfprobeStream:

    def test_ffprobe_not_installed_returns_ok_with_warning(self):
        from app.api.v1.cameras.probe_handler import _ffprobe_stream
        with patch("subprocess.run", side_effect=FileNotFoundError("ffprobe not found")):
            result = _ffprobe_stream("rtsp://192.168.1.1/stream")
        assert result["ok"] is True
        assert "ffprobe" in result.get("warning", "")

    def test_timeout_returns_ok_false_with_error(self):
        from app.api.v1.cameras.probe_handler import _ffprobe_stream
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=8)):
            result = _ffprobe_stream("rtsp://192.168.1.1/stream")
        assert result["ok"] is False
        assert "Timeout" in result["error"]

    def test_returncode_nonzero_401_returns_auth_error(self):
        from app.api.v1.cameras.probe_handler import _ffprobe_stream
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = b"401 Unauthorized"
        with patch("subprocess.run", return_value=mock_proc):
            result = _ffprobe_stream("rtsp://192.168.1.1/stream")
        assert result["ok"] is False
        assert "senha" in result["error"] or "Autenticação" in result["error"]

    def test_returncode_nonzero_connection_refused(self):
        from app.api.v1.cameras.probe_handler import _ffprobe_stream
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = b"Connection refused"
        with patch("subprocess.run", return_value=mock_proc):
            result = _ffprobe_stream("rtsp://192.168.1.1/stream")
        assert result["ok"] is False
        assert "recusou" in result["error"] or "refused" in result["error"].lower()

    def test_returncode_nonzero_404(self):
        from app.api.v1.cameras.probe_handler import _ffprobe_stream
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = b"404 Not Found"
        with patch("subprocess.run", return_value=mock_proc):
            result = _ffprobe_stream("rtsp://192.168.1.1/stream")
        assert result["ok"] is False

    def test_returncode_nonzero_generic_error(self):
        from app.api.v1.cameras.probe_handler import _ffprobe_stream
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = b"Unknown error"
        with patch("subprocess.run", return_value=mock_proc):
            result = _ffprobe_stream("rtsp://192.168.1.1/stream")
        assert result["ok"] is False

    def test_returncode_zero_with_video_stream(self):
        from app.api.v1.cameras.probe_handler import _ffprobe_stream
        stream_info = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "25/1",
            }]
        }
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(stream_info).encode()
        with patch("subprocess.run", return_value=mock_proc):
            result = _ffprobe_stream("rtsp://192.168.1.1/stream")
        assert result["ok"] is True
        assert result["codec"] == "h264"
        assert result["resolution"] == "1920x1080"
        assert result["fps"] == 25.0

    def test_returncode_zero_no_video_stream(self):
        from app.api.v1.cameras.probe_handler import _ffprobe_stream
        stream_info = {"streams": [{"codec_type": "audio"}]}
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(stream_info).encode()
        with patch("subprocess.run", return_value=mock_proc):
            result = _ffprobe_stream("rtsp://192.168.1.1/stream")
        assert result["ok"] is True
        assert result["codec"] is None

    def test_returncode_zero_invalid_json(self):
        from app.api.v1.cameras.probe_handler import _ffprobe_stream
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"not-json"
        with patch("subprocess.run", return_value=mock_proc):
            result = _ffprobe_stream("rtsp://192.168.1.1/stream")
        assert result["ok"] is True
        assert result["codec"] is None

    def test_fps_zero_denominator_returns_none(self):
        from app.api.v1.cameras.probe_handler import _ffprobe_stream
        stream_info = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 640,
                "height": 480,
                "r_frame_rate": "0/0",
            }]
        }
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(stream_info).encode()
        with patch("subprocess.run", return_value=mock_proc):
            result = _ffprobe_stream("rtsp://192.168.1.1/stream")
        assert result["fps"] is None


# ---------------------------------------------------------------------------
# _check_gateway_available
# ---------------------------------------------------------------------------

class TestCheckGatewayAvailable:

    def test_pool_none_returns_false(self):
        from app.api.v1.cameras.probe_handler import _check_gateway_available
        with patch("app.infrastructure.database.connection.DatabasePool") as mock_cls:
            mock_cls.get_instance.return_value = None
            assert _check_gateway_available("tenant-1") is False

    def test_exception_returns_false(self):
        from app.api.v1.cameras.probe_handler import _check_gateway_available
        with patch("app.infrastructure.database.connection.DatabasePool") as mock_cls:
            mock_cls.get_instance.side_effect = Exception("DB error")
            assert _check_gateway_available("tenant-1") is False

    def test_gateway_found_returns_true(self):
        from contextlib import contextmanager
        from app.api.v1.cameras.probe_handler import _check_gateway_available

        @contextmanager
        def _conn_ctx():
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.__enter__ = MagicMock(return_value=mock_cur)
            mock_cur.__exit__ = MagicMock(return_value=False)
            mock_cur.fetchone.return_value = {"1": 1}
            mock_conn.cursor.return_value = mock_cur
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _conn_ctx

        with patch("app.infrastructure.database.connection.DatabasePool") as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            assert _check_gateway_available("tenant-1") is True

    def test_no_gateway_returns_false(self):
        from contextlib import contextmanager
        from app.api.v1.cameras.probe_handler import _check_gateway_available

        @contextmanager
        def _conn_ctx():
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.__enter__ = MagicMock(return_value=mock_cur)
            mock_cur.__exit__ = MagicMock(return_value=False)
            mock_cur.fetchone.return_value = None
            mock_conn.cursor.return_value = mock_cur
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _conn_ctx

        with patch("app.infrastructure.database.connection.DatabasePool") as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            assert _check_gateway_available("tenant-1") is False
