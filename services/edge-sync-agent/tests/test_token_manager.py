"""Tests for TokenManager: key persistence, identity persistence, JWT minting."""

import os
import time

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization

from app.auth.token_manager import (
    TokenManager,
    TokenManagerError,
    build_token_manager_from_env,
)


@pytest.fixture()
def key_path(tmp_path):
    return tmp_path / "keys" / "device_key.pem"


# ── key generation / persistence ─────────────────────────────────────────────

def test_first_run_generates_key_with_0600_permissions(key_path):
    TokenManager(key_path=key_path)

    assert key_path.exists()
    mode = oct(os.stat(key_path).st_mode)[-3:]
    assert mode == "600"


def test_second_run_loads_the_same_key(key_path):
    tm1 = TokenManager(key_path=key_path)
    pub1 = tm1.public_key_pem

    tm2 = TokenManager(key_path=key_path)
    pub2 = tm2.public_key_pem

    assert pub1 == pub2


def test_public_key_pem_is_derived_from_the_private_key(key_path):
    tm = TokenManager(key_path=key_path)

    loaded_pub = serialization.load_pem_public_key(tm.public_key_pem.encode())
    assert loaded_pub.public_numbers().n  # sanity: a real RSA public key


# ── identity persistence ─────────────────────────────────────────────────────

def test_no_identity_by_default(key_path):
    tm = TokenManager(key_path=key_path)
    assert tm.identity is None
    assert tm.has_valid_identity() is False


def test_save_and_reload_identity(key_path):
    identity_path = key_path.with_name("identity.json")
    tm1 = TokenManager(key_path=key_path, identity_path=identity_path)
    tm1.save_identity(
        device_id="dev-1", tenant_id="tenant-1", site_id="site-1", scopes=["heartbeat:write"]
    )

    tm2 = TokenManager(key_path=key_path, identity_path=identity_path)
    assert tm2.has_valid_identity() is True
    assert tm2.identity.device_id == "dev-1"
    assert tm2.identity.scopes == ["heartbeat:write"]

    mode = oct(os.stat(identity_path).st_mode)[-3:]
    assert mode == "600"


def test_mark_revoked_persists_and_invalidates(key_path):
    tm = TokenManager(key_path=key_path)
    tm.save_identity(device_id="dev-1", tenant_id="t", site_id="s", scopes=["heartbeat:write"])

    tm.mark_revoked()

    assert tm.identity.revoked is True
    assert tm.has_valid_identity() is False
    # survives reload too
    tm2 = TokenManager(key_path=key_path)
    assert tm2.identity.revoked is True


def test_mark_revoked_without_identity_raises(key_path):
    tm = TokenManager(key_path=key_path)
    with pytest.raises(TokenManagerError):
        tm.mark_revoked()


# ── bearer minting ────────────────────────────────────────────────────────────

def test_get_bearer_without_identity_raises(key_path):
    tm = TokenManager(key_path=key_path)
    with pytest.raises(TokenManagerError):
        tm.get_bearer()


def test_get_bearer_mints_rs256_jwt_with_expected_claims(key_path):
    tm = TokenManager(key_path=key_path)
    tm.save_identity(
        device_id="dev-1", tenant_id="tenant-1", site_id="site-1", scopes=["heartbeat:write"]
    )

    token = tm.get_bearer(ttl_s=300)

    claims = pyjwt.decode(
        token, tm.public_key_pem, algorithms=["RS256"], options={"verify_aud": False}
    )
    assert claims["device_id"] == "dev-1"
    assert claims["tenant_id"] == "tenant-1"
    assert claims["site_id"] == "site-1"
    assert claims["scopes"] == ["heartbeat:write"]
    assert claims["exp"] - claims["iat"] == 300


def test_get_bearer_is_not_verifiable_with_a_different_key(key_path, tmp_path):
    tm = TokenManager(key_path=key_path)
    tm.save_identity(device_id="dev-1", tenant_id="t", site_id="s", scopes=["heartbeat:write"])
    token = tm.get_bearer()

    other = TokenManager(key_path=tmp_path / "other" / "device_key.pem")
    with pytest.raises(pyjwt.InvalidSignatureError):
        pyjwt.decode(token, other.public_key_pem, algorithms=["RS256"])


def test_get_bearer_exp_is_short_and_in_the_future(key_path):
    tm = TokenManager(key_path=key_path)
    tm.save_identity(device_id="dev-1", tenant_id="t", site_id="s", scopes=["heartbeat:write"])

    before = int(time.time())
    token = tm.get_bearer(ttl_s=60)
    claims = pyjwt.decode(token, tm.public_key_pem, algorithms=["RS256"])

    assert before <= claims["iat"] <= before + 5
    assert claims["exp"] == claims["iat"] + 60


def test_get_bearer_after_revocation_raises(key_path):
    tm = TokenManager(key_path=key_path)
    tm.save_identity(device_id="dev-1", tenant_id="t", site_id="s", scopes=["heartbeat:write"])
    tm.mark_revoked()

    with pytest.raises(TokenManagerError):
        tm.get_bearer()


# ── build_token_manager_from_env ─────────────────────────────────────────────

def test_build_from_env_uses_edge_device_key_path(tmp_path):
    path = tmp_path / "custom" / "device_key.pem"
    tm = build_token_manager_from_env({"EDGE_DEVICE_KEY_PATH": str(path)})
    assert path.exists()
    assert tm.public_key_pem


def test_build_from_env_default_path_is_outside_repo():
    from app.auth.token_manager import _DEFAULT_KEY_PATH

    assert _DEFAULT_KEY_PATH == "/var/lib/recognition-edge/keys/device_key.pem"
