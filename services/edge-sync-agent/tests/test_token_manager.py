"""Tests for TokenManager: key persistence, identity persistence, JWT minting."""

import os
import time

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization

from app.auth.token_manager import (
    _ALL_DEVICE_SCOPES,
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
    # scopes = união identity ∪ código implantado (ver _effective_scopes):
    # o persistido vem primeiro, o resto do enum conhecido pelo código segue.
    assert claims["scopes"][0] == "heartbeat:write"
    assert set(claims["scopes"]) == {"heartbeat:write", *_ALL_DEVICE_SCOPES}
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


# ── união de escopos: identity ∪ código implantado (_effective_scopes) ───────
#
# O servidor não persiste grants por device (enroll devolve o enum inteiro;
# a autorização lê os claims do token auto-assinado) — o identity.json é só
# um cache da lista do enum na época do enrollment. A união faz deploy de
# código novo propagar escopo novo pra devices já enrolados, sem reenroll.


def test_old_identity_without_snapshot_write_still_mints_it(key_path):
    """Device enrolado ANTES do escopo snapshot:write existir (Bloco A):
    o token mintado hoje carrega o escopo mesmo assim — sem reenroll."""
    tm = TokenManager(key_path=key_path)
    old_enrollment_scopes = [s for s in _ALL_DEVICE_SCOPES if s != "snapshot:write"]
    tm.save_identity(
        device_id="dev-1", tenant_id="t", site_id="s", scopes=old_enrollment_scopes
    )

    token = tm.get_bearer()
    claims = pyjwt.decode(token, tm.public_key_pem, algorithms=["RS256"])

    assert "snapshot:write" in claims["scopes"]
    assert set(claims["scopes"]) == set(_ALL_DEVICE_SCOPES)


def test_extra_persisted_scopes_are_never_lost(key_path):
    """União, não substituição: um escopo concedido por um enrollment futuro
    que este código ainda não conhece continua no token."""
    tm = TokenManager(key_path=key_path)
    tm.save_identity(
        device_id="dev-1", tenant_id="t", site_id="s",
        scopes=["heartbeat:write", "future:scope"],
    )

    token = tm.get_bearer()
    claims = pyjwt.decode(token, tm.public_key_pem, algorithms=["RS256"])

    assert "future:scope" in claims["scopes"]
    assert set(claims["scopes"]) == {"future:scope", *_ALL_DEVICE_SCOPES}


def test_union_does_not_duplicate_scopes(key_path):
    tm = TokenManager(key_path=key_path)
    tm.save_identity(
        device_id="dev-1", tenant_id="t", site_id="s", scopes=list(_ALL_DEVICE_SCOPES)
    )

    token = tm.get_bearer()
    claims = pyjwt.decode(token, tm.public_key_pem, algorithms=["RS256"])

    assert len(claims["scopes"]) == len(set(claims["scopes"]))
    assert set(claims["scopes"]) == set(_ALL_DEVICE_SCOPES)


def test_union_does_not_rewrite_the_persisted_identity(key_path):
    """A união acontece só na hora de assinar — o identity.json continua
    sendo o retrato fiel do que o enrollment devolveu (cache, não grant)."""
    tm = TokenManager(key_path=key_path)
    tm.save_identity(device_id="dev-1", tenant_id="t", site_id="s", scopes=["heartbeat:write"])

    tm.get_bearer()

    tm2 = TokenManager(key_path=key_path)
    assert tm2.identity is not None
    assert tm2.identity.scopes == ["heartbeat:write"]


def test_all_device_scopes_mirror_matches_shared_enum():
    """Tranca a paridade do espelho manual `_ALL_DEVICE_SCOPES` com
    `recognition_shared.enums.DeviceTokenScope` — só roda no layout do
    monorepo (onde shared/python existe); num deploy standalone do agente o
    arquivo não está presente e o teste é pulado (a paridade é garantida
    pelo CI do monorepo, não pelo box)."""
    import importlib.util
    from pathlib import Path

    enums_path = (
        Path(__file__).resolve().parents[3] / "shared" / "python"
        / "recognition_shared" / "enums.py"
    )
    if not enums_path.exists():
        pytest.skip("layout standalone — shared/python não presente")

    spec = importlib.util.spec_from_file_location("_shared_enums_mirror_check", enums_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    shared_values = [s.value for s in module.DeviceTokenScope]
    assert list(_ALL_DEVICE_SCOPES) == shared_values, (
        "espelho _ALL_DEVICE_SCOPES divergiu de recognition_shared.enums."
        "DeviceTokenScope — sincronize os dois (ver comentário no espelho)"
    )


# ── build_token_manager_from_env ─────────────────────────────────────────────

def test_build_from_env_uses_edge_device_key_path(tmp_path):
    path = tmp_path / "custom" / "device_key.pem"
    tm = build_token_manager_from_env({"EDGE_DEVICE_KEY_PATH": str(path)})
    assert path.exists()
    assert tm.public_key_pem


def test_build_from_env_default_path_is_outside_repo():
    from app.auth.token_manager import _DEFAULT_KEY_PATH

    assert _DEFAULT_KEY_PATH == "/var/lib/recognition-edge/keys/device_key.pem"
