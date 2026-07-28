"""TokenManager: device identity (RSA keypair) + self-signed RS256 bearer tokens.

The device is the key owner: it generates an RSA-2048 keypair on first run,
persists the private key to disk (chmod 600), and later mints its own short
JWTs by signing with that key — the cloud only ever sees the public key (at
enroll) and verifies the JWT signature (at heartbeat/upload). No token is
ever issued by the cloud (ADR-0019 S7; see `scripts/edge_artery_probe.py`,
the proven reference contract this reproduces in production code).

`TokenProvider` is the narrow interface (`get_bearer() -> str`) that PR-B
(heartbeat) and PR-C (orchestrator → uploader/config_poller/command_poller)
consume — those loops receive a token by parameter today; wiring a live
provider instead of a static string is their concern, not this one's.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Protocol

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)

_DEFAULT_KEY_PATH = "/var/lib/recognition-edge/keys/device_key.pem"
_DEFAULT_BEARER_TTL_S = 300


class TokenManagerError(Exception):
    """Raised for identity/key persistence errors and signing without an identity."""


class TokenProvider(Protocol):
    def get_bearer(self, ttl_s: int = _DEFAULT_BEARER_TTL_S) -> str: ...


@dataclass(frozen=True)
class DeviceIdentity:
    device_id: str
    tenant_id: str
    site_id: str
    scopes: list[str]
    revoked: bool = False


class TokenManager:
    """Owns the device's RSA keypair and enrollment identity.

    Two files, both `chmod 600`, dono = usuário do serviço:
      - `key_path`: private key PEM (PKCS8, unencrypted — the file's own
        permissions are the protection, matching `edge_artery_probe.py`'s
        `--key-file`).
      - `identity_path` (default: `identity.json` next to the key): the
        enroll response — device_id/tenant_id/site_id/scopes — plus a
        `revoked` flag. Not secret by itself, but colocated with the key.

    Rotation/revocation of the key itself is out of scope for PR-A (registered
    as future work, not implemented) — only the `revoked` identity flag exists
    today, so `get_bearer()` can refuse to sign for a revoked device.
    """

    def __init__(self, key_path: str | Path, identity_path: str | Path | None = None) -> None:
        self._key_path = Path(key_path)
        self._identity_path = Path(identity_path) if identity_path else self._key_path.with_name(
            "identity.json"
        )
        self._private_key_pem = self._load_or_generate_key()
        self._public_key_pem = self._derive_public_key_pem(self._private_key_pem)
        self._identity = self._load_identity()

    # ── key management ───────────────────────────────────────────────────────

    def _load_or_generate_key(self) -> str:
        if self._key_path.exists():
            return self._key_path.read_text(encoding="utf-8")

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        self._key_path.write_text(pem, encoding="utf-8")
        os.chmod(self._key_path, 0o600)
        logger.info("device_key_generated path=%s", self._key_path)
        return pem

    @staticmethod
    def _derive_public_key_pem(private_key_pem: str) -> str:
        key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
        return key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    @property
    def public_key_pem(self) -> str:
        return self._public_key_pem

    # ── identity management ──────────────────────────────────────────────────

    def _load_identity(self) -> DeviceIdentity | None:
        if not self._identity_path.exists():
            return None
        try:
            data = json.loads(self._identity_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TokenManagerError(
                f"identidade corrompida em {self._identity_path}: {exc}"
            ) from exc
        return DeviceIdentity(**data)

    def _persist_identity(self, identity: DeviceIdentity) -> None:
        self._identity_path.parent.mkdir(parents=True, exist_ok=True)
        self._identity_path.write_text(json.dumps(asdict(identity)), encoding="utf-8")
        os.chmod(self._identity_path, 0o600)
        self._identity = identity

    @property
    def identity(self) -> DeviceIdentity | None:
        return self._identity

    def has_valid_identity(self) -> bool:
        return self._identity is not None and not self._identity.revoked

    def save_identity(
        self, *, device_id: str, tenant_id: str, site_id: str, scopes: list[str]
    ) -> DeviceIdentity:
        identity = DeviceIdentity(
            device_id=device_id, tenant_id=tenant_id, site_id=site_id, scopes=list(scopes)
        )
        self._persist_identity(identity)
        return identity

    def mark_revoked(self) -> None:
        if self._identity is None:
            raise TokenManagerError("sem identidade para revogar — enroll nunca ocorreu")
        self._persist_identity(replace(self._identity, revoked=True))
        logger.warning("device_marked_revoked device_id=%s", self._identity.device_id)

    # ── bearer minting ───────────────────────────────────────────────────────

    def get_bearer(self, ttl_s: int = _DEFAULT_BEARER_TTL_S) -> str:
        """Mints a short RS256 JWT signed with the device's own private key.

        Claims match `recognition_shared.device.DeviceClaims` exactly, as
        verified server-side: {tenant_id, site_id, device_id, scopes, iat, exp}.
        """
        if self._identity is None:
            raise TokenManagerError("sem identidade — enroll antes de assinar um token")
        if self._identity.revoked:
            raise TokenManagerError("device revogado — não é possível assinar token")

        now = int(time.time())
        claims = {
            "tenant_id": self._identity.tenant_id,
            "site_id": self._identity.site_id,
            "device_id": self._identity.device_id,
            "scopes": self._identity.scopes,
            "iat": now,
            "exp": now + ttl_s,
        }
        return jwt.encode(claims, self._private_key_pem, algorithm="RS256")


def build_token_manager_from_env(env: dict[str, str] | None = None) -> TokenManager:
    """Reads EDGE_DEVICE_KEY_PATH (default: /var/lib/recognition-edge/keys/device_key.pem)."""
    source = env if env is not None else os.environ
    key_path = source.get("EDGE_DEVICE_KEY_PATH", _DEFAULT_KEY_PATH)
    return TokenManager(key_path=key_path)
