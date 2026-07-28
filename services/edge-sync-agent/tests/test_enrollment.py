"""Tests for enrollment: idempotency, error handling, backoff on network failure."""

from unittest.mock import MagicMock

import pytest

from app.auth.enrollment import (
    EnrollmentConfig,
    EnrollmentError,
    build_enrollment_config_from_env,
    ensure_enrolled,
)
from app.auth.token_manager import TokenManager


@pytest.fixture()
def token_manager(tmp_path):
    return TokenManager(key_path=tmp_path / "device_key.pem")


@pytest.fixture()
def config():
    return EnrollmentConfig(
        api_url="http://cloud.test",
        enrollment_token="one-time-token",
        device_id="dev-1",
        device_name="Device One",
    )


def _response(status_code, data=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = {"data": data} if data is not None else {}
    r.text = text
    return r


# ── idempotency ───────────────────────────────────────────────────────────────

def test_skips_enroll_when_valid_identity_already_persisted(token_manager, config):
    token_manager.save_identity(
        device_id="dev-1", tenant_id="t1", site_id="s1", scopes=["heartbeat:write"]
    )
    http = MagicMock()

    identity = ensure_enrolled(token_manager, config, http)

    http.post.assert_not_called()
    assert identity.device_id == "dev-1"


def test_enrolls_when_identity_is_revoked(token_manager, config):
    token_manager.save_identity(
        device_id="dev-1", tenant_id="t1", site_id="s1", scopes=["heartbeat:write"]
    )
    token_manager.mark_revoked()
    http = MagicMock()
    http.post.return_value = _response(
        201,
        data={
            "tenant_id": "t2",
            "site_id": "s2",
            "device_id": "dev-1",
            "scopes": ["heartbeat:write"],
        },
    )

    identity = ensure_enrolled(token_manager, config, http)

    http.post.assert_called_once()
    assert identity.revoked is False
    assert identity.tenant_id == "t2"


# ── happy path ───────────────────────────────────────────────────────────────

def test_successful_enroll_persists_identity_and_sends_public_key(token_manager, config):
    http = MagicMock()
    http.post.return_value = _response(
        201,
        data={
            "tenant_id": "tenant-1",
            "site_id": "site-1",
            "device_id": "dev-1",
            "scopes": ["heartbeat:write", "detection:write"],
        },
    )

    identity = ensure_enrolled(token_manager, config, http)

    assert identity.tenant_id == "tenant-1"
    assert identity.site_id == "site-1"
    assert identity.scopes == ["heartbeat:write", "detection:write"]
    assert token_manager.has_valid_identity() is True

    _, kwargs = http.post.call_args
    assert kwargs["json"]["enrollment_token"] == "one-time-token"
    assert kwargs["json"]["device_id"] == "dev-1"
    assert kwargs["json"]["public_key_pem"] == token_manager.public_key_pem


# ── terminal errors: no retry ───────────────────────────────────────────────

def test_401_raises_immediately_without_retry(token_manager, config):
    http = MagicMock()
    http.post.return_value = _response(401)

    with pytest.raises(EnrollmentError, match="inválido|expirado|utilizado"):
        ensure_enrolled(token_manager, config, http, sleep=lambda _s: None)

    assert http.post.call_count == 1


def test_409_raises_immediately_without_retry(token_manager, config):
    http = MagicMock()
    http.post.return_value = _response(409)

    with pytest.raises(EnrollmentError, match="já cadastrado"):
        ensure_enrolled(token_manager, config, http, sleep=lambda _s: None)

    assert http.post.call_count == 1


def test_missing_enrollment_token_raises_without_calling_http(token_manager):
    http = MagicMock()
    bad_config = EnrollmentConfig(
        api_url="http://cloud.test", enrollment_token="", device_id="dev-1", device_name="Device"
    )

    with pytest.raises(EnrollmentError, match="ENROLLMENT_TOKEN"):
        ensure_enrolled(token_manager, bad_config, http)

    http.post.assert_not_called()


def test_response_missing_required_field_raises(token_manager, config):
    http = MagicMock()
    http.post.return_value = _response(201, data={"tenant_id": "t1", "site_id": "s1"})

    with pytest.raises(EnrollmentError, match="campo"):
        ensure_enrolled(token_manager, config, http, sleep=lambda _s: None)


# ── network failure: retries with backoff, then gives up ───────────────────

def test_network_error_retries_then_succeeds(token_manager, config):
    http = MagicMock()
    http.post.side_effect = [
        ConnectionError("boom"),
        ConnectionError("boom"),
        _response(
            201,
            data={"tenant_id": "t1", "site_id": "s1", "device_id": "dev-1", "scopes": []},
        ),
    ]
    sleeps = []

    identity = ensure_enrolled(
        token_manager, config, http, sleep=sleeps.append, backoff_steps=(1.0, 2.0, 3.0)
    )

    assert identity.device_id == "dev-1"
    assert http.post.call_count == 3
    assert sleeps == [1.0, 2.0]


def test_network_error_exhausts_retries_and_raises(token_manager, config):
    http = MagicMock()
    http.post.side_effect = ConnectionError("boom")

    with pytest.raises(EnrollmentError, match="falha de rede"):
        ensure_enrolled(
            token_manager, config, http, sleep=lambda _s: None, backoff_steps=(1.0, 2.0)
        )

    assert http.post.call_count == 3  # initial + 2 backoff retries


# ── build_enrollment_config_from_env ─────────────────────────────────────────

def test_build_config_from_env_reads_all_fields():
    env = {
        "EDGE_API_URL": "https://api.test/",
        "ENROLLMENT_TOKEN": "tok",
        "DEVICE_ID": "dev-9",
        "DEVICE_NAME": "Nine",
    }
    cfg = build_enrollment_config_from_env(env)
    assert cfg.api_url == "https://api.test"  # trailing slash stripped
    assert cfg.enrollment_token == "tok"
    assert cfg.device_id == "dev-9"
    assert cfg.device_name == "Nine"


def test_build_config_from_env_defaults_to_dev_api_url():
    cfg = build_enrollment_config_from_env({"DEVICE_ID": "dev-9"})
    assert "desenvolvimento" in cfg.api_url
    assert "production" not in cfg.api_url


def test_build_config_from_env_defaults_device_name_to_device_id():
    cfg = build_enrollment_config_from_env({"DEVICE_ID": "dev-9"})
    assert cfg.device_name == "dev-9"


def test_build_config_from_env_requires_device_id():
    with pytest.raises(EnrollmentError, match="DEVICE_ID"):
        build_enrollment_config_from_env({})
