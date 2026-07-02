"""
Domain service: integration_service — credenciais de integrações externas.

Responsabilidades:
  - Fernet encrypt/decrypt usando env CAMERA_SECRET_KEY (reutiliza chave existente)
  - save_integration: cifra secret, persiste via repo, retorna view mascarada
  - get_integration_secret: descriptografa para uso interno (nunca expor na API)
  - test_r2_connection / test_vast_connection / test_generic_connection
  - audit_log em toda mutação (via public.audit_log)

Fonte da chave: env CAMERA_SECRET_KEY (32 bytes url-safe base64).
Precedência credentials: integration store > env var.
"""
import json
import logging
import os
from typing import Any
from uuid import UUID

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError as BotoClientError
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]
    BotoCoreError = Exception  # type: ignore[assignment,misc]
    BotoClientError = Exception  # type: ignore[assignment]

from cryptography.fernet import Fernet, InvalidToken

from app.core.exceptions import ValidationError
from app.infrastructure.database.repositories.integration_repository import (
    IntegrationRepository,
)

logger = logging.getLogger(__name__)

_ALLOWED_TYPES = frozenset(
    {"r2", "vast_ai", "generic_gpu", "notification", "byo_db"}
)


def _get_fernet() -> Fernet:
    key = os.environ.get("CAMERA_SECRET_KEY", "")
    if not key:
        raise ValidationError("CAMERA_SECRET_KEY não configurada")
    return Fernet(key.encode() if isinstance(key, str) else key)


def _encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception) as exc:
        logger.error("integration_decrypt_failed: %s", exc)
        return ""


class IntegrationService:
    """Use-cases de integrações externas (storage, GPU, notificações)."""

    def __init__(self, repo: IntegrationRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------ save

    def save_integration(
        self,
        tenant_id: UUID,
        integration_type: str,
        label: str,
        config: dict[str, Any],
        plaintext_secret: str | None = None,
    ) -> dict[str, Any]:
        """Cifra o secret e persiste. Retorna view mascarada (sem plaintext)."""
        if integration_type not in _ALLOWED_TYPES:
            raise ValidationError(
                f"integration_type inválido: {integration_type}. "
                f"Permitidos: {sorted(_ALLOWED_TYPES)}"
            )
        if not label or not label.strip():
            raise ValidationError("label é obrigatório")

        secret_encrypted: str | None = None
        last4: str | None = None

        if plaintext_secret:
            secret_encrypted = _encrypt(plaintext_secret)
            last4 = plaintext_secret[-4:] if len(plaintext_secret) >= 4 else plaintext_secret

        row = self._repo.upsert_integration(
            tenant_id=tenant_id,
            integration_type=integration_type,
            label=label,
            config=config,
            secret_encrypted=secret_encrypted,
            last4=last4,
        )
        return _mask_row(row)

    # ------------------------------------------------------------------ read

    def list_integrations(self, tenant_id: UUID) -> list[dict[str, Any]]:
        """Lista integrações mascaradas do tenant."""
        rows = self._repo.list_integrations(tenant_id)
        return [_mask_row(r) for r in rows]

    def get_integration(
        self, tenant_id: UUID, integration_type: str
    ) -> dict[str, Any] | None:
        """Retorna integração mascarada ou None."""
        row = self._repo.get_integration(tenant_id, integration_type)
        return _mask_row(row) if row else None

    # ----------------------------------------------------------------- secret (interno)

    def get_integration_secret(
        self, tenant_id: UUID, integration_type: str
    ) -> str:
        """Descriptografa e retorna secret. USO INTERNO APENAS.
        Fonte: Fernet(secret_encrypted) da integration store.
        """
        enc = self._repo.get_secret_encrypted(tenant_id, integration_type)
        if not enc:
            return ""
        return _decrypt(enc)

    # --------------------------------------------------------------- test

    def test_r2_connection(self, tenant_id: UUID) -> dict[str, Any]:
        """Testa conectividade com Cloudflare R2.
        Carrega credenciais do integration store (tenant_id).
        Fonte: env > integration store conforme ADR de precedência.
        """
        row = self._repo.get_integration(tenant_id, "r2")
        if not row:
            return {"ok": False, "error": "Integração R2 não configurada"}

        config = row.get("config") or {}
        endpoint = config.get("endpoint") or os.environ.get("R2_ENDPOINT", "")
        bucket = config.get("bucket") or os.environ.get("R2_BUCKET", "")
        access_key = os.environ.get("R2_ACCESS_KEY_ID") or self.get_integration_secret(tenant_id, "r2")

        secret_row = self._repo.get_secret_encrypted(tenant_id, "r2")
        secret_key = _decrypt(secret_row) if secret_row else os.environ.get("R2_SECRET_ACCESS_KEY", "")

        if not all([endpoint, bucket, access_key, secret_key]):
            return {"ok": False, "error": "Credenciais R2 incompletas (endpoint, bucket, key)"}

        if boto3 is None:
            return {"ok": False, "error": "boto3 não instalado"}

        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="auto",
            )
            s3.head_bucket(Bucket=bucket)
            self._repo.update_status(str(row["id"]), "ok")
            return {"ok": True, "error": None}
        except (BotoClientError, BotoCoreError, Exception) as exc:
            msg = str(exc)
            self._repo.update_status(str(row["id"]), "error", msg[:500])
            return {"ok": False, "error": msg}

    def test_vast_connection(self, tenant_id: UUID) -> dict[str, Any]:
        """Testa conectividade com Vast.ai API.
        GET https://console.vast.ai/api/v0/ com Bearer token.
        """
        import requests  # noqa: PLC0415

        row = self._repo.get_integration(tenant_id, "vast_ai")
        if not row:
            return {"ok": False, "error": "Integração Vast.ai não configurada"}

        secret_enc = self._repo.get_secret_encrypted(tenant_id, "vast_ai")
        api_key = _decrypt(secret_enc) if secret_enc else os.environ.get("VAST_API_KEY", "")

        if not api_key:
            return {"ok": False, "error": "API key Vast.ai não configurada"}

        try:
            resp = requests.get(
                "https://console.vast.ai/api/v0/",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            if resp.status_code < 400:
                self._repo.update_status(str(row["id"]), "ok")
                return {"ok": True, "error": None}
            msg = f"HTTP {resp.status_code}"
            self._repo.update_status(str(row["id"]), "error", msg)
            return {"ok": False, "error": msg}
        except Exception as exc:
            msg = str(exc)
            self._repo.update_status(str(row["id"]), "error", msg[:500])
            return {"ok": False, "error": msg}

    def test_generic_connection(
        self, tenant_id: UUID, integration_type: str
    ) -> dict[str, Any]:
        """Teste genérico: verifica se integração existe e tem secret configurado."""
        row = self._repo.get_integration(tenant_id, integration_type)
        if not row:
            return {"ok": False, "error": f"Integração {integration_type} não configurada"}

        has_secret = bool(self._repo.get_secret_encrypted(tenant_id, integration_type))
        if not has_secret:
            return {"ok": False, "error": "Secret não configurado"}

        self._repo.update_status(str(row["id"]), "ok")
        return {"ok": True, "error": None}

    # --------------------------------------------------------------- audit

    def audit_log(
        self,
        tenant_id: UUID,
        user_id: UUID,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Registra ação em public.audit_log (best-effort)."""
        try:
            from flask import request as _req  # noqa: PLC0415
            ip = _req.remote_addr if _req else None
            ua = (_req.headers.get("User-Agent", "") if _req else "")[:500]
        except Exception:
            ip = None
            ua = None

        try:
            from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
            pool = DatabasePool.get_instance()
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO public.audit_log
                      (actor_id, actor_role, tenant_id, target_type, target_id,
                       action, new_value, ip_address, user_agent)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(user_id),
                        "superadmin",
                        str(tenant_id),
                        "integration",
                        None,
                        action,
                        json.dumps(details) if details else None,
                        ip,
                        ua,
                    ),
                )
        except Exception as exc:
            logger.error("integration_audit_log_failed: action=%s err=%s", action, exc)


# --------------------------------------------------------------------------- helpers

def _mask_row(row: dict[str, Any]) -> dict[str, Any]:
    """Remove secret_encrypted e compõe display_secret a partir de last4."""
    r = {k: v for k, v in row.items() if k != "secret_encrypted"}
    last4 = r.get("last4")
    r["secret_display"] = f"••••{last4}" if last4 else None
    return r
