"""Repository: public.device_claim_codes (migration 051).

Claim codes single-use para enrollment de dispositivos edge.
Armazenado apenas o hash SHA-256 — nunca o código em plaintext.
"""
from typing import Any, Optional

from app.infrastructure.database.repositories.base import BaseRepository


class DeviceClaimRepository(BaseRepository):
    """Queries SQL para public.device_claim_codes."""

    def create(
        self,
        tenant_id: str,
        code_hash: str,
        created_by: Optional[str],
        ttl_minutes: int,
    ) -> dict[str, Any]:
        """Cria claim code (hash). Retorna id + expires_at."""
        return self._execute_mutation(
            """
            INSERT INTO public.device_claim_codes
              (tenant_id, code_hash, created_by, expires_at)
            VALUES (%s, %s, %s, NOW() + make_interval(mins => %s))
            RETURNING id, tenant_id, expires_at, created_at
            """,
            (str(tenant_id), code_hash, str(created_by) if created_by else None, ttl_minutes),
        )  # type: ignore[return-value]

    def redeem(self, code_hash: str, device_name: Optional[str]) -> Optional[dict[str, Any]]:
        """Resgata claim code de forma atômica (single-use).

        UPDATE condicional: só marca used_at se ainda não usado E não expirado.
        Retorna a row (id, tenant_id) quando o resgate teve sucesso; None se
        código inexistente, já usado ou expirado.
        """
        return self._execute_mutation(
            """
            UPDATE public.device_claim_codes
            SET used_at = NOW(), used_by_device = %s
            WHERE code_hash = %s
              AND used_at IS NULL
              AND expires_at > NOW()
            RETURNING id, tenant_id
            """,
            (device_name, code_hash),
        )

    def get_status(self, code_hash: str) -> Optional[dict[str, Any]]:
        """Status do código (debug/auditoria) — nunca expor na API pública."""
        return self._execute_one(
            """
            SELECT id, tenant_id, expires_at, used_at, created_at
            FROM public.device_claim_codes
            WHERE code_hash = %s
            """,
            (code_hash,),
        )
