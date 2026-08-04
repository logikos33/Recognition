"""Tests for recorder_factory: protocol → RecorderClient selection, and the
env-var driven config path used by app/main.py."""

from unittest.mock import MagicMock

import pytest

from app.config_poller import ConfigPoller
from app.edge_config_cache import write_channel_map
from app.onvif_recorder_client import OnvifRecorderClient
from app.recorder_client import RecorderError
from app.recorder_factory import (
    build_recorder_client,
    build_recorder_client_from_env,
    resolve_channel_map,
)
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


def test_build_from_env_defaults_stream_subtype_to_zero():
    env = _base_env(RECORDER_PROTOCOL="intelbras")
    client = build_recorder_client_from_env(env)
    assert client._stream_subtype == 0


def test_build_from_env_stream_subtype_override():
    env = _base_env(RECORDER_PROTOCOL="intelbras", RECORDER_STREAM_SUBTYPE="1")
    client = build_recorder_client_from_env(env)
    assert client._stream_subtype == 1


def test_build_from_env_invalid_stream_subtype_raises():
    with pytest.raises(RecorderError):
        build_recorder_client_from_env(
            _base_env(RECORDER_PROTOCOL="intelbras", RECORDER_STREAM_SUBTYPE="not-a-number")
        )


# ── ADR-0058: resolve_channel_map — cloud-polled cache prefeceded over .env ──
#
# fail-before/pass-after: antes desta ADR, build_recorder_client_from_env só
# olhava RECORDER_CHANNEL_MAP; um EDGE_CONFIG_CACHE_PATH presente e válido
# tinha zero efeito (a função nem sabia que ele existia).

def test_cache_present_wins_over_env_channel_map(tmp_path):
    """A config polled da nuvem é preferida — mesmo com RECORDER_CHANNEL_MAP
    também setado no .env (transição: os dois podem coexistir por um tempo)."""
    cache_path = str(tmp_path / "config_cache.json")
    write_channel_map(cache_path, {"cloud-cam-1": 5, "cloud-cam-2": 6}, "cfgver123")

    env = _base_env(
        EDGE_CONFIG_CACHE_PATH=cache_path,
        RECORDER_CHANNEL_MAP='{"env-cam-1": 1}',
    )
    client = build_recorder_client_from_env(env)

    assert isinstance(client, OnvifRecorderClient)
    assert client._channel_map == {"cloud-cam-1": 5, "cloud-cam-2": 6}


def test_resolve_channel_map_reports_cloud_config_source(tmp_path):
    cache_path = str(tmp_path / "config_cache.json")
    write_channel_map(cache_path, {"cam-1": 1}, "v42")

    channel_map, source, config_version = resolve_channel_map(
        {"EDGE_CONFIG_CACHE_PATH": cache_path}
    )

    assert channel_map == {"cam-1": 1}
    assert source == "cloud_config"
    assert config_version == "v42"


def test_no_cache_falls_back_to_env_channel_map(tmp_path):
    """Cache ausente (nuvem nunca respondeu / cold start) — cai pro .env,
    o caminho de compatibilidade explicitamente pedido pela ADR-0058."""
    missing_cache = str(tmp_path / "never-written.json")

    channel_map, source, config_version = resolve_channel_map(
        {"EDGE_CONFIG_CACHE_PATH": missing_cache, "RECORDER_CHANNEL_MAP": '{"cam-1": 3}'}
    )

    assert channel_map == {"cam-1": 3}
    assert source == "env"
    assert config_version == ""


def test_no_cache_and_no_env_reports_none_source(tmp_path):
    missing_cache = str(tmp_path / "never-written.json")

    channel_map, source, config_version = resolve_channel_map(
        {"EDGE_CONFIG_CACHE_PATH": missing_cache}
    )

    assert channel_map == {}
    assert source == "none"


def test_build_from_env_raises_when_neither_cache_nor_env_available(tmp_path):
    missing_cache = str(tmp_path / "never-written.json")
    env = _base_env(EDGE_CONFIG_CACHE_PATH=missing_cache)
    del env["RECORDER_CHANNEL_MAP"]

    with pytest.raises(RecorderError):
        build_recorder_client_from_env(env)


def test_empty_cloud_channel_map_is_authoritative_not_a_fallback_trigger(tmp_path):
    """Cache presente mas vazio (nuvem diz 'zero câmeras ativas') NÃO cai pro
    .env — cair silenciosamente pro .env aqui reintroduziria a divergência
    que esta ADR fecha (config/poll diz N câmeras, o box usa outro N)."""
    cache_path = str(tmp_path / "config_cache.json")
    write_channel_map(cache_path, {}, "v1")

    channel_map, source, _ = resolve_channel_map(
        {"EDGE_CONFIG_CACHE_PATH": cache_path, "RECORDER_CHANNEL_MAP": '{"stale-env-cam": 1}'}
    )

    assert channel_map == {}
    assert source == "cloud_config"


def test_explicit_empty_env_channel_map_is_accepted_no_cache(tmp_path):
    """Preserva o comportamento anterior a esta ADR: RECORDER_CHANNEL_MAP='{}'
    presente e explicitamente vazio não é tratado como ausente."""
    missing_cache = str(tmp_path / "never-written.json")
    env = _base_env(EDGE_CONFIG_CACHE_PATH=missing_cache, RECORDER_CHANNEL_MAP="{}")

    client = build_recorder_client_from_env(env)

    assert client._channel_map == {}


def test_cache_write_then_read_round_trips_through_recorder_client(tmp_path):
    """Ponta a ponta: ConfigPoller grava, build_recorder_client_from_env lê —
    prova que os dois lados concordam no formato do arquivo sem se importar
    (o teste de config_poller cobre a escrita; este cobre a leitura pelo
    consumidor real, não só read_channel_map isolado)."""
    cache_path = str(tmp_path / "config_cache.json")
    http = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "cameras": [{"id": "44444444-4444-4444-4444-444444444444", "channel": 7}],
        "config_version": "roundtrip1",
    }
    resp.headers = {"ETag": '"roundtrip1"'}
    http.get.return_value = resp

    poller = ConfigPoller(
        http_client=http,
        cloud_url="http://cloud.test",
        device_id="dev-1",
        token="tok",
        cache_path=cache_path,
    )
    poller._poll_once()

    env = _base_env(EDGE_CONFIG_CACHE_PATH=cache_path)
    del env["RECORDER_CHANNEL_MAP"]
    client = build_recorder_client_from_env(env)

    assert client._channel_map == {"44444444-4444-4444-4444-444444444444": 7}
