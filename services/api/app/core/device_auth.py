"""
CORE device_auth.py — Claim codes e enrollment tokens para dispositivos edge.

Layer: core
Pattern: Utility (stateless — persistência via DeviceClaimRepository)

Fluxo plug-and-play (embrião):
  1. Admin do tenant gera claim code curto (POST /api/devices/claim-codes).
     - 8 chars, alfabeto sem ambíguos (sem 0/O/1/I/L), expira em 15 min, single-use.
     - Apenas o hash SHA-256 vai para o banco (public.device_claim_codes).
  2. Instalador digita o código no dispositivo.
  3. Dispositivo chama POST /api/devices/claim (público, rate-limited) e troca
     o código por um enrollment token vinculado ao tenant.

Key exports:
  - generate_claim_code(): código de 8 chars legível para humanos
  - hash_claim_code(code): SHA-256 hex (64 chars) — nunca armazenar plaintext
  - generate_enrollment_token(tenant_id, claim_id): JWT one-time-purpose com
    claims {token_type: device_enrollment, tenant_id, claim_id}, TTL 1h

TODO (GAP — documentado conforme combinado):
  - O enrollment token usa HS256 com o JWT_SECRET_KEY compartilhado da API
    (flask-jwt-extended). O plano de plataforma prevê RS256 com par de chaves
    assimétrico para que serviços edge validem tokens sem possuir o segredo.
    Migrar quando o device-registry/edge-sync-agent consumir este token.
  - Não existe ainda registro de devices (tabela devices) — o enrollment token
    é o handshake; o provisioning completo (mTLS/credencial permanente) virá
    na fase 2 do plug-and-play.

Related: app/api/v1/devices/routes.py,
         app/infrastructure/database/repositories/device_claim_repository.py,
         infra/migrations/051_platform_limits_claim_codes.sql
"""
import hashlib
import secrets
from datetime import timedelta

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
