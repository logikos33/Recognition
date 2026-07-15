"""Shared fixtures for the edge-sync-agent test suite."""

import time

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _generate_rsa_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture(scope="session")
def rsa_keypair() -> tuple[str, str]:
    """(private_pem, public_pem) — stands in for the cloud's evidence-trust keypair."""
    return _generate_rsa_keypair()


@pytest.fixture(scope="session")
def other_rsa_keypair() -> tuple[str, str]:
    """A second, unrelated keypair — proves verification actually checks the key,
    not just that *some* signature is present."""
    return _generate_rsa_keypair()


@pytest.fixture
def make_evidence_token(rsa_keypair):
    private_pem, _ = rsa_keypair

    def _make(
        tenant_id: str = "11111111-1111-1111-1111-111111111111",
        site_id: str = "22222222-2222-2222-2222-222222222222",
        sub: str = "cloud-proxy",
        scopes: list[str] | None = None,
        expires_in: int = 300,
        issued_offset: int = 0,
        signing_key: str | None = None,
        omit_claim: str | None = None,
    ) -> str:
        now = int(time.time()) + issued_offset
        payload = {
            "tenant_id": tenant_id,
            "site_id": site_id,
            "sub": sub,
            "scopes": scopes if scopes is not None else ["evidence:read", "evidence:stream"],
            "iat": now,
            "exp": now + expires_in,
        }
        if omit_claim:
            payload.pop(omit_claim, None)
        key = signing_key if signing_key is not None else private_pem
        return pyjwt.encode(payload, key, algorithm="RS256")

    return _make
