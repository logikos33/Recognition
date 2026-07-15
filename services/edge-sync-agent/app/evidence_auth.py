"""Auth for the local evidence API — RS256, same key-pair family as ADR-0019.

Design decision (documented in full in the task-090 PR): ADR-0019 has the
device *sign* its own JWTs with a private key it never shares, and the cloud
verifies them with the public key handed over at enrollment. That pattern
only authenticates edge→cloud calls; it says nothing about who is allowed to
call *into* the edge (this task's problem — local LAN client or cloud
proxying a request over the WireGuard tunnel, ADR-0020).

Rather than inventing a new crypto scheme, this module reuses the exact same
mechanism in reverse: a trust-anchor keypair whose PRIVATE half stays on the
cloud (used to mint short-lived, narrowly-scoped "evidence access" JWTs) and
whose PUBLIC half is handed to the edge device at enrollment time — mirroring
how the device's own public key is handed to the cloud. The edge never signs
these tokens, only verifies them, so no new private key material needs to
live on the device beyond what the WireGuard tunnel already protects.

Both the local (LAN) and remote (cloud→tunnel) access paths use the SAME
token type and the SAME verification code path here — the only difference is
the network path the request took to reach the API, which the WireGuard
overlay + bind-address restriction (see evidence_api.validate_bind_host)
enforces, not this module. A local operator tool obtains a token from the
cloud while online and may cache it for brief offline windows; indefinite
purely-offline local issuance is a known gap, left for a follow-up (noted in
the PR, not invented here to avoid growing the crypto surface unreviewed).

Minting (cloud-side, private key holder) is explicitly OUT OF SCOPE for this
task — services/edge-sync-agent only ever verifies. The claims shape below is
the contract the (future) cloud-side minting endpoint must produce.

No fallback: any failure (missing header, malformed token, bad signature,
expired, wrong tenant/site, missing scope) is a hard 401. Never log token
contents (same discipline as services/api/app/core/device_auth.py).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable

import jwt
from flask import g, jsonify, request

logger = logging.getLogger(__name__)


class EvidenceScope(str, Enum):
    """Scopes carried by an evidence access token (mirrors DeviceTokenScope's shape,
    kept as its own enum since it authorizes a different direction of traffic)."""

    evidence_read = "evidence:read"
    evidence_stream = "evidence:stream"


class EvidenceAuthError(Exception):
    """Any authentication/authorization failure for the evidence API."""


@dataclass(frozen=True)
class EvidenceClaims:
    """Verified claims of an evidence access token."""

    tenant_id: str
    site_id: str
    sub: str  # who requested this token: "cloud-proxy" or an operator/device identifier
    scopes: list[str]
    iat: int
    exp: int

    def has_scope(self, scope: EvidenceScope) -> bool:
        return scope.value in self.scopes


_REQUIRED_CLAIM_KEYS = ("tenant_id", "site_id", "sub", "scopes", "iat", "exp")


def verify_evidence_token(token: str, trust_public_key_pem: str) -> EvidenceClaims:
    """Verifies an RS256 evidence access token against the trust-anchor public key.

    Raises EvidenceAuthError on any invalid/expired/malformed token. Never
    returns partial/unverified claims.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            trust_public_key_pem,
            algorithms=["RS256"],
            options={"verify_exp": True, "require": list(_REQUIRED_CLAIM_KEYS)},
        )
    except jwt.ExpiredSignatureError as exc:
        raise EvidenceAuthError("Token de evidência expirado") from exc
    except jwt.MissingRequiredClaimError as exc:
        raise EvidenceAuthError(f"Claim obrigatório ausente: {exc}") from exc
    except jwt.InvalidSignatureError as exc:
        raise EvidenceAuthError("Assinatura do token inválida") from exc
    except jwt.PyJWTError as exc:
        raise EvidenceAuthError("Token inválido") from exc

    scopes = payload.get("scopes")
    if not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
        raise EvidenceAuthError("Claim 'scopes' malformado")

    try:
        return EvidenceClaims(
            tenant_id=str(payload["tenant_id"]),
            site_id=str(payload["site_id"]),
            sub=str(payload["sub"]),
            scopes=list(scopes),
            iat=int(payload["iat"]),
            exp=int(payload["exp"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EvidenceAuthError(f"Claims inválidos: {exc}") from exc


class TrustAnchor:
    """Holds the trust-anchor public key + this device's own tenant/site identity.

    tenant_id/site_id come from local enrollment state (this device belongs to
    exactly one tenant/site — set at enrollment, never inferred from the
    request). A token whose claims don't match is rejected — defense in
    depth against a stolen/misdirected token, same discipline as
    device_auth.get_device_context's claims-match check on the cloud side.
    """

    def __init__(self, public_key_pem: str, tenant_id: str, site_id: str) -> None:
        if not public_key_pem or not public_key_pem.strip():
            raise ValueError(
                "TrustAnchor requer public_key_pem não vazio — sem fallback silencioso"
            )
        if not tenant_id or not site_id:
            raise ValueError("TrustAnchor requer tenant_id e site_id do enrollment local")
        self._public_key_pem = public_key_pem
        self._tenant_id = str(tenant_id)
        self._site_id = str(site_id)

    def verify(self, token: str, required_scope: EvidenceScope) -> EvidenceClaims:
        claims = verify_evidence_token(token, self._public_key_pem)
        if claims.tenant_id != self._tenant_id or claims.site_id != self._site_id:
            logger.warning(
                "evidence_auth_tenant_mismatch sub=%s claims_tenant=%s claims_site=%s",
                claims.sub,
                claims.tenant_id,
                claims.site_id,
            )
            raise EvidenceAuthError("Token não corresponde a este dispositivo")
        if not claims.has_scope(required_scope):
            logger.warning(
                "evidence_auth_scope_denied sub=%s required=%s has=%s",
                claims.sub,
                required_scope.value,
                claims.scopes,
            )
            raise EvidenceAuthError("Escopo insuficiente")
        return claims


def require_evidence_scope(scope: EvidenceScope) -> Callable:
    """Flask route decorator: every route MUST use this — no open endpoints.

    Expects `current_app.config["TRUST_ANCHOR"]` (a TrustAnchor instance) to be
    set by evidence_api.create_app. On success, stores claims in flask.g.claims.
    On any failure: 401 with a generic message (no detail leak about why).
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from flask import current_app  # noqa: PLC0415 — avoid app-context import at load time

            trust_anchor: TrustAnchor | None = current_app.config.get("TRUST_ANCHOR")
            if trust_anchor is None:
                logger.error("evidence_auth_misconfigured: TRUST_ANCHOR ausente")
                return jsonify({"status": "error", "error": "not_configured"}), 500

            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"status": "error", "error": "unauthorized"}), 401
            token = auth_header.removeprefix("Bearer ")

            try:
                claims = trust_anchor.verify(token, scope)
            except EvidenceAuthError:
                return jsonify({"status": "error", "error": "unauthorized"}), 401

            g.evidence_claims = claims
            return fn(*args, **kwargs)

        return wrapper

    return decorator
