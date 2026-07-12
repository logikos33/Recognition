"""
Simulador de dispositivo edge — gera par RSA, assina JWT RS256, constrói payloads.

Autocontido: não importa recognition_shared.
"""
import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


class DeviceSim:
    """Dispositivo edge sintético capaz de enrollar e enviar heartbeats."""

    def __init__(self, device_id: str, tenant_id: str | None = None, site_id: str | None = None):
        self.device_id = device_id
        self.tenant_id = tenant_id
        self.site_id = site_id

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.private_key_pem: str = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        self.public_key_pem: str = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def set_enrollment(self, tenant_id: str, site_id: str) -> None:
        """Atualiza tenant_id/site_id após enrollment bem-sucedido."""
        self.tenant_id = tenant_id
        self.site_id = site_id

    def build_token(
        self,
        tenant_id: str | None = None,
        site_id: str | None = None,
        ttl_seconds: int = 3600,
    ) -> str:
        """Gera JWT RS256 com claims de dispositivo.

        Por padrão usa tenant_id/site_id do enrollment.
        Para teste de cross-tenant, passe tenant_id/site_id divergentes.
        """
        tid = tenant_id or self.tenant_id
        sid = site_id or self.site_id
        if not tid or not sid:
            raise ValueError("tenant_id e site_id obrigatórios — chame set_enrollment primeiro")

        now = int(time.time())
        payload = {
            "device_id": self.device_id,
            "tenant_id": str(tid),
            "site_id": str(sid),
            "scopes": [
                "heartbeat:write",
                "events:write",
                "config:read",
                "models:download",
                "streams:report",
            ],
            "iat": now,
            "exp": now + ttl_seconds,
        }
        return jwt.encode(payload, self.private_key_pem, algorithm="RS256")

    def heartbeat_payload(self) -> dict:
        """Payload mínimo válido para POST /api/v1/edge/heartbeat."""
        return {
            "device_id": self.device_id,
            "status": "healthy",
            "cpu_pct": 22.5,
            "mem_pct": 35.0,
            "cameras_online": 1,
            "cameras_total": 1,
            "inference_fps": 5.0,
            "edge_version": "harness-0.1",
        }
