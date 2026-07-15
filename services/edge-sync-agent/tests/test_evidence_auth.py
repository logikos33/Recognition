"""Tests for evidence_auth: RS256 verification of inbound evidence access tokens."""

import time

import pytest

from app.evidence_auth import (
    EvidenceAuthError,
    EvidenceScope,
    TrustAnchor,
    verify_evidence_token,
)

TENANT = "11111111-1111-1111-1111-111111111111"
SITE = "22222222-2222-2222-2222-222222222222"


# ── verify_evidence_token ────────────────────────────────────────────────────


def test_valid_token_round_trips(rsa_keypair, make_evidence_token):
    _, public_pem = rsa_keypair
    token = make_evidence_token()

    claims = verify_evidence_token(token, public_pem)

    assert claims.tenant_id == TENANT
    assert claims.site_id == SITE
    assert claims.sub == "cloud-proxy"
    assert claims.has_scope(EvidenceScope.evidence_read)
    assert claims.has_scope(EvidenceScope.evidence_stream)


def test_expired_token_rejected(rsa_keypair, make_evidence_token):
    _, public_pem = rsa_keypair
    token = make_evidence_token(issued_offset=-1000, expires_in=1)

    with pytest.raises(EvidenceAuthError):
        verify_evidence_token(token, public_pem)


def test_wrong_signing_key_rejected(rsa_keypair, other_rsa_keypair, make_evidence_token):
    """Signature was produced with a key OTHER than the trust anchor — must fail,
    proving the check is a real signature verification, not just shape validation."""
    _, public_pem = rsa_keypair
    _, other_public_pem = other_rsa_keypair
    token = make_evidence_token()

    with pytest.raises(EvidenceAuthError):
        verify_evidence_token(token, other_public_pem)


def test_token_signed_by_unrelated_key_rejected(
    other_rsa_keypair, rsa_keypair, make_evidence_token
):
    other_private_pem, _ = other_rsa_keypair
    _, trust_public_pem = rsa_keypair
    forged = make_evidence_token(signing_key=other_private_pem)

    with pytest.raises(EvidenceAuthError):
        verify_evidence_token(forged, trust_public_pem)


def test_malformed_token_rejected(rsa_keypair):
    _, public_pem = rsa_keypair

    with pytest.raises(EvidenceAuthError):
        verify_evidence_token("not-a-jwt", public_pem)


@pytest.mark.parametrize("missing", ["tenant_id", "site_id", "sub", "scopes", "iat", "exp"])
def test_missing_required_claim_rejected(rsa_keypair, make_evidence_token, missing):
    _, public_pem = rsa_keypair
    token = make_evidence_token(omit_claim=missing)

    with pytest.raises(EvidenceAuthError):
        verify_evidence_token(token, public_pem)


def test_scopes_must_be_list_of_strings(rsa_keypair):
    import jwt as pyjwt

    private_pem, public_pem = rsa_keypair
    now = int(time.time())
    payload = {
        "tenant_id": TENANT,
        "site_id": SITE,
        "sub": "cloud-proxy",
        "scopes": "evidence:read",  # not a list — malformed
        "iat": now,
        "exp": now + 300,
    }
    token = pyjwt.encode(payload, private_pem, algorithm="RS256")

    with pytest.raises(EvidenceAuthError):
        verify_evidence_token(token, public_pem)


# ── TrustAnchor ──────────────────────────────────────────────────────────────


def test_trust_anchor_rejects_empty_public_key():
    with pytest.raises(ValueError):
        TrustAnchor(public_key_pem="", tenant_id=TENANT, site_id=SITE)


def test_trust_anchor_rejects_missing_tenant_or_site(rsa_keypair):
    _, public_pem = rsa_keypair
    with pytest.raises(ValueError):
        TrustAnchor(public_key_pem=public_pem, tenant_id="", site_id=SITE)
    with pytest.raises(ValueError):
        TrustAnchor(public_key_pem=public_pem, tenant_id=TENANT, site_id="")


def test_trust_anchor_verify_success(rsa_keypair, make_evidence_token):
    _, public_pem = rsa_keypair
    anchor = TrustAnchor(public_key_pem=public_pem, tenant_id=TENANT, site_id=SITE)
    token = make_evidence_token()

    claims = anchor.verify(token, EvidenceScope.evidence_read)

    assert claims.tenant_id == TENANT


def test_trust_anchor_rejects_tenant_mismatch(rsa_keypair, make_evidence_token):
    _, public_pem = rsa_keypair
    anchor = TrustAnchor(public_key_pem=public_pem, tenant_id="other-tenant", site_id=SITE)
    token = make_evidence_token()

    with pytest.raises(EvidenceAuthError):
        anchor.verify(token, EvidenceScope.evidence_read)


def test_trust_anchor_rejects_site_mismatch(rsa_keypair, make_evidence_token):
    _, public_pem = rsa_keypair
    anchor = TrustAnchor(public_key_pem=public_pem, tenant_id=TENANT, site_id="other-site")
    token = make_evidence_token()

    with pytest.raises(EvidenceAuthError):
        anchor.verify(token, EvidenceScope.evidence_read)


def test_trust_anchor_rejects_missing_scope(rsa_keypair, make_evidence_token):
    _, public_pem = rsa_keypair
    anchor = TrustAnchor(public_key_pem=public_pem, tenant_id=TENANT, site_id=SITE)
    token = make_evidence_token(scopes=["evidence:read"])  # no evidence:stream

    with pytest.raises(EvidenceAuthError):
        anchor.verify(token, EvidenceScope.evidence_stream)
