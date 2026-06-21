"""Tests: Validators (RTSP, Upload, HLS)."""
import pytest

from app.core.exceptions import ValidationError
from app.core.validators import (
    HLSFilenameValidator,
    RTSPUrlValidator,
    VideoUploadValidator,
)


class TestVideoUploadValidator:
    """Testes para VideoUploadValidator."""

    def test_valid_mp4(self) -> None:
        assert VideoUploadValidator.validate_extension("video.mp4") == "mp4"

    def test_valid_avi(self) -> None:
        assert VideoUploadValidator.validate_extension("video.avi") == "avi"

    def test_valid_mov(self) -> None:
        assert VideoUploadValidator.validate_extension("video.mov") == "mov"

    def test_invalid_extension(self) -> None:
        with pytest.raises(ValidationError, match="não permitida"):
            VideoUploadValidator.validate_extension("video.exe")

    def test_no_extension(self) -> None:
        with pytest.raises(ValidationError, match="extensão"):
            VideoUploadValidator.validate_extension("video")

    def test_empty_filename(self) -> None:
        with pytest.raises(ValidationError):
            VideoUploadValidator.validate_extension("")

    def test_case_insensitive(self) -> None:
        assert VideoUploadValidator.validate_extension("video.MP4") == "mp4"

    def test_sanitize_removes_dangerous_chars(self) -> None:
        result = VideoUploadValidator.sanitize_filename('video<test>.mp4')
        assert "<" not in result
        assert ">" not in result

    def test_sanitize_empty_raises(self) -> None:
        with pytest.raises(ValidationError, match="vazio"):
            VideoUploadValidator.sanitize_filename("")

    def test_sanitize_long_filename(self) -> None:
        long_name = "a" * 300 + ".mp4"
        result = VideoUploadValidator.sanitize_filename(long_name)
        assert len(result) <= 255


class TestRTSPUrlValidator:
    """Testes para RTSPUrlValidator."""

    def test_valid_rtsp_url(self) -> None:
        url = "rtsp://admin:pass@192.168.1.100:554/stream"
        assert RTSPUrlValidator.validate(url) == url

    def test_valid_rtsps_url(self) -> None:
        url = "rtsps://user:pass@10.0.0.1:554/cam"
        assert RTSPUrlValidator.validate(url) == url

    def test_empty_url(self) -> None:
        with pytest.raises(ValidationError, match="vazia"):
            RTSPUrlValidator.validate("")

    def test_invalid_scheme(self) -> None:
        with pytest.raises(ValidationError, match="Scheme"):
            RTSPUrlValidator.validate("http://192.168.1.100:554/stream")

    def test_no_hostname(self) -> None:
        with pytest.raises(ValidationError, match="hostname"):
            RTSPUrlValidator.validate("rtsp://")

    def test_loopback_rejected(self) -> None:
        with pytest.raises(ValidationError, match="loopback"):
            RTSPUrlValidator.validate("rtsp://admin:pass@127.0.0.1:554/stream")

    def test_command_injection_semicolon(self) -> None:
        with pytest.raises(ValidationError, match="caracteres"):
            RTSPUrlValidator.validate("rtsp://admin:pass@192.168.1.1:554/stream;ls")

    def test_command_injection_pipe(self) -> None:
        with pytest.raises(ValidationError, match="caracteres"):
            RTSPUrlValidator.validate("rtsp://admin:pass@192.168.1.1:554/stream|cat")

    def test_command_injection_backtick(self) -> None:
        with pytest.raises(ValidationError, match="caracteres"):
            RTSPUrlValidator.validate("rtsp://admin:pass@192.168.1.1:554/`whoami`")

    def test_url_too_long(self) -> None:
        url = "rtsp://admin:pass@192.168.1.1:554/" + "a" * 2100
        with pytest.raises(ValidationError, match="tamanho"):
            RTSPUrlValidator.validate(url)

    def test_hostname_valid(self) -> None:
        url = "rtsp://admin:pass@camera.local:554/stream"
        assert RTSPUrlValidator.validate(url) == url

    def test_multicast_rejected(self) -> None:
        with pytest.raises(ValidationError, match="multicast"):
            RTSPUrlValidator.validate("rtsp://admin:pass@224.0.0.1:554/stream")

    def test_port_out_of_range(self) -> None:
        with pytest.raises(ValidationError, match="malformada|Porta"):
            RTSPUrlValidator.validate("rtsp://admin:pass@192.168.1.1:70000/stream")

    def test_link_local_rejected(self) -> None:
        with pytest.raises(ValidationError, match="link-local"):
            RTSPUrlValidator.validate("rtsp://admin:pass@169.254.169.254:554/stream")

    def test_link_local_ipv6_rejected(self) -> None:
        with pytest.raises(ValidationError, match="link-local"):
            RTSPUrlValidator.validate("rtsp://admin:pass@[fe80::1]:554/stream")


class TestHLSFilenameValidator:
    """Testes para HLSFilenameValidator."""

    def test_valid_m3u8(self) -> None:
        assert HLSFilenameValidator.validate("stream.m3u8") == "stream.m3u8"

    def test_valid_ts(self) -> None:
        assert HLSFilenameValidator.validate("segment_001.ts") == "segment_001.ts"

    def test_path_traversal(self) -> None:
        with pytest.raises(ValidationError, match="traversal"):
            HLSFilenameValidator.validate("../etc/passwd")

    def test_slash_rejected(self) -> None:
        with pytest.raises(ValidationError, match="traversal"):
            HLSFilenameValidator.validate("dir/file.ts")

    def test_invalid_extension(self) -> None:
        with pytest.raises(ValidationError, match="inválido"):
            HLSFilenameValidator.validate("file.mp4")

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValidationError, match="vazio"):
            HLSFilenameValidator.validate("")

    def test_spaces_rejected(self) -> None:
        with pytest.raises(ValidationError, match="inválido"):
            HLSFilenameValidator.validate("my file.ts")
