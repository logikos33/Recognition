"""Tests for recorder_factory: protocol → RecorderClient selection, the
env-var driven config path used by app/main.py, and the fail-fast checks
around RECORDER_PROTOCOL=onvif (credentials at build time, single auth
liveness check at boot — found missing while validating ADR-0052 against
real hardware, an Intelbras iNVD 3032)."""

from unittest.mock import MagicMock

import pytest

from app.config_poller import ConfigPoller
from app.edge_config_cache import write_channel_map
from app.onvif_recorder_client import OnvifRecorderClient
from app.recorder_client import InMemoryRecorderClient, RecorderError, RecorderHealth
from app.recorder_factory import (
    build_recorder_client,
    build_recorder_client_from_env,
    resolve_channel_map,
    validate_onvif_boot_or_raise,
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


def test_build_from_env_rtsp_fallback_defaults_username_password_to_empty():
    """Non-onvif (RTSP fallback) protocols keep the old behavior: some
    gravadores accept anonymous RTSP, so missing RECORDER_USERNAME/PASSWORD
    is not fatal for `dahua`/`intelbras`/`rtsp`."""
    env = _base_env(RECORDER_PROTOCOL="intelbras")
    del env["RECORDER_USERNAME"]
    del env["RECORDER_PASSWORD"]
    client = build_recorder_client_from_env(env)
    assert isinstance(client, RtspTimestampRecorderClient)


# ── fail-fast: RECORDER_PROTOCOL=onvif requires credentials (found broken —
# `_post_soap` sent zero auth — while validating ADR-0052 against real
# hardware). Turning the flag on without credentials must abort the boot with
# a clear message, never build a client that silently sends no auth. ────────


def test_build_from_env_onvif_without_username_raises():
    env = _base_env()
    del env["RECORDER_USERNAME"]
    with pytest.raises(RecorderError):
        build_recorder_client_from_env(env)


def test_build_from_env_onvif_without_password_raises():
    env = _base_env()
    del env["RECORDER_PASSWORD"]
    with pytest.raises(RecorderError):
        build_recorder_client_from_env(env)


def test_build_from_env_onvif_without_any_credential_raises():
    env = _base_env()
    del env["RECORDER_USERNAME"]
    del env["RECORDER_PASSWORD"]
    with pytest.raises(RecorderError):
        build_recorder_client_from_env(env)


def test_build_from_env_onvif_with_credentials_passes():
    env = _base_env()  # RECORDER_USERNAME/RECORDER_PASSWORD already set
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


# ── validate_onvif_boot_or_raise: single boot-time auth check, no retry ────
#
# fail-before/pass-after: before this, RECORDER_PROTOCOL=onvif with wrong/
# missing credentials on the real gravador built a client fine and only blew
# up obscurely on the first real request from evidence_api/live_view/
# collector — no signal at boot at all.


class _RespondingHttpClient:
    """Minimal fake matching OnvifRecorderClient._http.post(...) — returns a
    canned 200 (auth "succeeds") or raises (auth/network "fails")."""

    def __init__(self, *, raises: bool = False) -> None:
        self._raises = raises

    def post(self, url, content=None, headers=None, timeout=None):
        if self._raises:
            import httpx

            raise httpx.ConnectError("connection refused")

        class _Resp:
            text = "<GetSystemDateAndTimeResponse/>"

            def raise_for_status(self) -> None:
                return None

        return _Resp()


def _onvif_client(*, reachable: bool) -> OnvifRecorderClient:
    return OnvifRecorderClient(
        host="10.0.0.5",
        port=8080,
        username="admin",
        password="secret",
        channel_map=_CHANNEL_MAP,
        http_client=_RespondingHttpClient(raises=not reachable),
    )


def test_validate_onvif_boot_or_raise_passes_when_auth_check_succeeds():
    client = _onvif_client(reachable=True)
    validate_onvif_boot_or_raise(client)  # must not raise


def test_validate_onvif_boot_or_raise_raises_when_auth_check_fails():
    client = _onvif_client(reachable=False)
    with pytest.raises(RecorderError):
        validate_onvif_boot_or_raise(client)


def test_validate_onvif_boot_or_raise_calls_health_exactly_once():
    """No retry, ever — the gravador can lock out on repeated failed auth
    attempts (CLAUDE.md anti-brute-force note)."""
    client = MagicMock(spec=OnvifRecorderClient)
    client.health.return_value = RecorderHealth(reachable=False, detail="401")

    with pytest.raises(RecorderError):
        validate_onvif_boot_or_raise(client)

    client.health.assert_called_once()


def test_validate_onvif_boot_or_raise_is_noop_for_non_onvif_client():
    """A RECORDER_PROTOCOL=intelbras (RTSP fallback) client has no ONVIF auth
    to validate — must never be probed, even if it happens to be
    'unreachable' (there's no single cheap auth call defined for it here)."""
    client = InMemoryRecorderClient(reachable=False)
    validate_onvif_boot_or_raise(client)  # must not raise
