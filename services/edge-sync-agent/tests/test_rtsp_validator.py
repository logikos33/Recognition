"""Tests for RTSPUrlValidator — the SSRF/command-injection guard ported from
services/api/app/core/validators.py for use by the recorder clients."""

import pytest

from app.recorder_client import RecorderError
from app.rtsp_validator import RTSPUrlValidator


def test_valid_rtsp_url_passes_through():
    url = "rtsp://user:pass@192.168.1.10:554/cam/playback?channel=1&starttime=x"
    assert RTSPUrlValidator.validate(url) == url


def test_valid_http_url_passes_through():
    url = "http://192.168.1.10:80/onvif/device_service"
    assert RTSPUrlValidator.validate(url) == url


def test_empty_url_rejected():
    with pytest.raises(RecorderError):
        RTSPUrlValidator.validate("")


def test_oversized_url_rejected():
    url = "rtsp://10.0.0.1:554/" + ("a" * 3000)
    with pytest.raises(RecorderError):
        RTSPUrlValidator.validate(url)


@pytest.mark.parametrize("bad_char", [";", "|", "$", "`", "\n", "\r"])
def test_dangerous_characters_rejected(bad_char):
    url = f"rtsp://10.0.0.1:554/cam{bad_char}rm -rf /"
    with pytest.raises(RecorderError):
        RTSPUrlValidator.validate(url)


def test_ampersand_is_allowed_query_separator():
    url = "rtsp://10.0.0.1:554/cam/playback?channel=1&subtype=0"
    assert RTSPUrlValidator.validate(url) == url


def test_disallowed_scheme_rejected():
    with pytest.raises(RecorderError):
        RTSPUrlValidator.validate("ftp://10.0.0.1/cam")


def test_missing_hostname_rejected():
    with pytest.raises(RecorderError):
        RTSPUrlValidator.validate("rtsp:///cam")


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "169.254.1.1", "224.0.0.1", "0.0.0.0"],
)
def test_forbidden_ip_classes_rejected(host):
    with pytest.raises(RecorderError):
        RTSPUrlValidator.validate(f"rtsp://{host}:554/cam")


def test_hostname_non_ip_is_allowed():
    assert RTSPUrlValidator.validate("rtsp://nvr.local:554/cam") == "rtsp://nvr.local:554/cam"


def test_port_out_of_range_rejected():
    with pytest.raises(RecorderError):
        RTSPUrlValidator.validate("rtsp://10.0.0.1:70000/cam")
