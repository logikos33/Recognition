"""
CORE device_auth.py — RS256 device token verification for edge devices.

Layer: core
Pattern: Pure utility — no DB access (caller handles lookup and revoked check)

Key exports:
  - extract_device_id_unverified: reads device_id from JWT without verifying signature
  - verify_device_token: verifies RS256 + expiry, returns DeviceClaims
  - generate_claim_code: random single-use claim code for device enrollment
  - hash_claim_code: SHA256 digest of claim code for safe storage
  - generate_enrollment_token: short-lived JWT for edge device enrollment

Constraints:
  - Caller must check revoked=False BEFORE calling verify_device_token
  - Never log token contents (zero PII in logs — C-05)
"""
import hashlib
import logging
import secrets
from datetime import timedelta

import jwt
from flask_jwt_extended import create_access_token
from recognition_shared.device import DeviceClaims

from app.core.exceptions import AuthenticationError

_CLAIM_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CLAIM_CODE_LENGTH = 8
CLAIM_CODE_TTL_MINUTES = 15
ENROLLMENT_TOKEN_TTL_HOURS = 24


def generate_claim_code() -> str:
    return "".join(secrets.choice(_CLAIM_ALPHABET) for _ in range(CLAIM_CODE_LENGTH))


def hash_claim_code(code: str) -> str:
    normalized = code.upper().replace("-", "").replace(" ", "")
    return hashlib.sha256(normalized.encode()).hexdigest()


def generate_enrollment_token(tenant_id: str, claim_id: str) -> str:
    return create_access_token(
        identity=claim_id,
        additional_claims={"token_type": "device_enrollment", "tenant_id": tenant_id},
        expires_delta=timedelta(hours=ENROLLMENT_TOKEN_TTL_HOURS),
    )

logger = logging.getLogger(__name__)


def extract_device_id_unverified(token: str) -> str:
    """Reads device_id claim from JWT without verifying signature.

    Used solely for DB key lookup — claims are NOT trusted until
    verify_device_token succeeds.
    """
    try:
        payload = jwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=["RS256"],
        )
    except jwt.DecodeError as exc:
        raise AuthenticationError("Token malformado") from exc

    device_id = payload.get("device_id")
    if not device_id:
        raise AuthenticationError("Token sem device_id")
    return str(device_id)


def verify_device_token(token: str, public_key_pem: str) -> DeviceClaims:
    """Verifies RS256 JWT against public_key_pem and returns DeviceClaims.

    Raises AuthenticationError on invalid signature, expired token, or bad claims.
    """
    try:
        payload = jwt.decode(
            token,
            public_key_pem,
            algorithms=["RS256"],
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token de dispositivo expirado") from exc
    except jwt.InvalidSignatureError as exc:
        raise AuthenticationError("Assinatura do token inválida") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Token inválido") from exc

    try:
        return DeviceClaims(**payload)
    except Exception as exc:
        raise AuthenticationError(f"Claims inválidos: {exc}") from exc
