"""
CORE device_auth.py — Claim codes, enrollment tokens e verificação de device tokens.

Layer: core
Pattern: Utility (stateless — persistência via DeviceClaimRepository)

Fluxo plug-and-play:
  1. Admin do tenant gera claim code curto (POST /api/devices/claim-codes).
     - 8 chars, alfabeto sem ambíguos (sem 0/O/1/I/L), expira em 15 min, single-use.
     - Apenas o hash SHA-256 vai para o banco (public.device_claim_codes).
  2. Instalador digita o código no dispositivo.
  3. Dispositivo chama POST /api/devices/claim (público, rate-limited) e troca
     o código por um enrollment token (HS256 JWT com tenant_id + token_type).
  4. Dispositivo usa o enrollment token como device token em X-Device-Token
     para endpoints autenticados por dispositivo (ex: evidence-upload).

Key exports:
  - generate_claim_code(): código de 8 chars legível para humanos
  - hash_claim_code(code): SHA-256 hex (64 chars) — nunca armazenar plaintext
  - generate_enrollment_token(tenant_id, claim_id): JWT device_enrollment
  - verify_device_token(token): valida JWT e retorna claims (tenant_id, etc.)

Note: HS256 nesta branch. Migrar para RS256 quando edge-sync-agent consumir.

Related: app/api/v1/devices/routes.py,
         app/infrastructure/database/repositories/device_claim_repository.py,
         infra/migrations/051_platform_limits_claim_codes.sql
"""
import hashlib
import logging
import secrets
from datetime import timedelta

from app.core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

# Sem caracteres ambíguos (0/O, 1/I/L) — código será digitado por humanos
_CLAIM_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CLAIM_CODE_LENGTH = 8
CLAIM_CODE_TTL_MINUTES = 15
ENROLLMENT_TOKEN_TTL_HOURS = 1


def generate_claim_code() -> str:
    """Gera claim code curto de 8 chars (alfabeto sem ambíguos)."""
    return "".join(secrets.choice(_CLAIM_ALPHABET) for _ in range(CLAIM_CODE_LENGTH))


def hash_claim_code(code: str) -> str:
    """SHA-256 hex do código normalizado (uppercase, sem espaços/hífens)."""
    normalized = code.strip().upper().replace("-", "").replace(" ", "")
    return hashlib.sha256(normalized.encode()).hexdigest()


def generate_enrollment_token(tenant_id: str, claim_id: str) -> str:
    """Gera enrollment token JWT vinculado ao tenant (TTL 1h).

    Identity = claim_id (rastreável ao claim code que o originou).
    Claims extras marcam o propósito — APIs de usuário devem rejeitar
    tokens com token_type=device_enrollment.
    """
    from flask_jwt_extended import create_access_token

    return create_access_token(
        identity=str(claim_id),
        additional_claims={
            "token_type": "device_enrollment",
            "tenant_id": str(tenant_id),
        },
        expires_delta=timedelta(hours=ENROLLMENT_TOKEN_TTL_HOURS),
    )


def verify_device_token(token: str) -> dict:
    """Valida enrollment token (HS256 JWT) e retorna claims.

    Levanta AuthenticationError se o token for inválido, expirado ou
    não for do tipo device_enrollment.

    Retorna dict com pelo menos: tenant_id, token_type, sub.
    Zero log de conteúdo de token (C-05 — sem PII em logs).
    """
    try:
        from flask_jwt_extended import decode_token
        decoded = decode_token(token)
    except Exception as exc:
        logger.warning("verify_device_token: decode failed")
        raise AuthenticationError("Token de dispositivo inválido ou expirado") from exc

    token_type = decoded.get("token_type")
    if token_type != "device_enrollment":
        logger.warning("verify_device_token: wrong token_type=%s", token_type)
        raise AuthenticationError("Token não é de dispositivo")

    tenant_id = decoded.get("tenant_id")
    if not tenant_id:
        raise AuthenticationError("tenant_id ausente no token")

    return decoded
