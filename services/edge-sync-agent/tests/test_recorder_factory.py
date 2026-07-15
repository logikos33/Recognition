"""Tests for recorder_factory: protocol → RecorderClient selection, and the
env-var driven config path used by app/main.py."""

import pytest

from app.onvif_recorder_client import OnvifRecorderClient
from app.recorder_client import RecorderError
from app.recorder_factory import build_recorder_client, build_recorder_client_from_env
from app.rtsp_timestamp_recorder_client import RtspTimestampRecorderClient

_CHANNEL_MAP = {"cam-1": 1}


@pytest.mark.parametrize("protocol", ["onvif", "ONVIF", " onvif "])
def test_onvif_protocol_builds_onvif_client(protocol):
    client = build_recorder_client(
        protocol=protocol,
        host="10.0.0.5",
        port=80,
        username="admin",
        password="pw",
        channel_map=_CHANNEL_MAP,
    )
    assert isinstance(client, OnvifRecorderClient)


@pytest.mark.parametrize("protocol", ["dahua", "intelbras", "rtsp"])
def test_rtsp_fallback_protocols_build_rtsp_timestamp_client(protocol):
    client = build_recorder_client(
        protocol=protocol,
        host="10.0.0.9",
        port=554,
        username="admin",
        password="pw",
        channel_map=_CHANNEL_MAP,
    )
    assert isinstance(client, RtspTimestampRecorderClient)


def test_unsupported_protocol_raises_recorder_error():
    with pytest.raises(RecorderError):
        build_recorder_client(
            protocol="hikvision",
            host="10.0.0.5",
            port=80,
            username="",
            password="",
            channel_map=_CHANNEL_MAP,
        )


def test_empty_protocol_raises_recorder_error():
    with pytest.raises(RecorderError):
        build_recorder_client(
            protocol="",
            host="10.0.0.5",
            port=80,
            username="",
            password="",
            channel_map=_CHANNEL_MAP,
        )


def _base_env(**overrides) -> dict:
    env = {
        "RECORDER_PROTOCOL": "onvif",
        "RECORDER_HOST": "10.0.0.5",
        "RECORDER_PORT": "8080",
        "RECORDER_USERNAME": "admin",
        "RECORDER_PASSWORD": "secret",
        "RECORDER_CHANNEL_MAP": '{"cam-1": 1, "cam-2": 2}',
    }
    env.update(overrides)
    return env


def test_build_from_env_happy_path():
    client = build_recorder_client_from_env(_base_env())
    assert isinstance(client, OnvifRecorderClient)


def test_build_from_env_missing_protocol_raises():
    env = _base_env()
    del env["RECORDER_PROTOCOL"]
    with pytest.raises(RecorderError):
        build_recorder_client_from_env(env)


def test_build_from_env_missing_host_raises():
    env = _base_env()
    del env["RECORDER_HOST"]
    with pytest.raises(RecorderError):
        build_recorder_client_from_env(env)


def test_build_from_env_invalid_port_raises():
    with pytest.raises(RecorderError):
        build_recorder_client_from_env(_base_env(RECORDER_PORT="not-a-number"))


def test_build_from_env_missing_channel_map_raises():
    env = _base_env()
    del env["RECORDER_CHANNEL_MAP"]
    with pytest.raises(RecorderError):
        build_recorder_client_from_env(env)


def test_build_from_env_malformed_channel_map_json_raises():
    with pytest.raises(RecorderError):
        build_recorder_client_from_env(_base_env(RECORDER_CHANNEL_MAP="not-json"))


def test_build_from_env_channel_map_must_be_object():
    with pytest.raises(RecorderError):
        build_recorder_client_from_env(_base_env(RECORDER_CHANNEL_MAP="[1, 2, 3]"))


def test_build_from_env_channel_map_non_integer_value_raises():
    with pytest.raises(RecorderError):
        build_recorder_client_from_env(
            _base_env(RECORDER_CHANNEL_MAP='{"cam-1": "not-an-int"}')
        )


def test_build_from_env_defaults_username_password_to_empty():
    env = _base_env()
    del env["RECORDER_USERNAME"]
    del env["RECORDER_PASSWORD"]
    client = build_recorder_client_from_env(env)
    assert isinstance(client, OnvifRecorderClient)
