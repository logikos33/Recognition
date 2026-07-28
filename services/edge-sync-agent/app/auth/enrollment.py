"""Device enrollment: POST /api/v1/edge/enroll, idempotent.

Contract (from `scripts/edge_artery_probe.py`, the proven reference):
  POST {api_url}/api/v1/edge/enroll
    body: {enrollment_token, device_id, device_name, public_key_pem}
    201  -> envelope {"data": {tenant_id, site_id, device_id, scopes}}
    401  -> token inválido/expirado/já usado (one-time) — não tentar de novo
    409  -> device_id já cadastrado neste tenant — não tentar de novo
The cloud does NOT return a JWT; the device signs its own (see token_manager).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable

from .token_manager import DeviceIdentity, TokenManager

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://api-v3-desenvolvimento.up.railway.app"  # DEV — nunca produção
_DEFAULT_BACKOFF_STEPS: tuple[float, ...] = (5.0, 15.0, 30.0, 60.0)


class EnrollmentError(Exception):
    """Raised for a terminal enrollment failure (bad token, duplicate device, ...)."""


@dataclass(frozen=True)
class EnrollmentConfig:
    api_url: str
    enrollment_token: str
    device_id: str
    device_name: str


def build_enrollment_config_from_env(env: dict[str, str] | None = None) -> EnrollmentConfig:
    """Reads EDGE_API_URL, ENROLLMENT_TOKEN, DEVICE_ID, DEVICE_NAME.

    DEVICE_ID is required (the enroll body needs it even before an identity
    exists). ENROLLMENT_TOKEN may be absent when an identity is already
    persisted (`ensure_enrolled` skips the network call entirely then).
    """
    source = env if env is not None else os.environ
    device_id = source.get("DEVICE_ID", "")
    if not device_id:
        raise EnrollmentError("DEVICE_ID é obrigatório")
    return EnrollmentConfig(
        api_url=(source.get("EDGE_API_URL") or _DEFAULT_API_URL).rstrip("/"),
        enrollment_token=source.get("ENROLLMENT_TOKEN", ""),
        device_id=device_id,
        device_name=source.get("DEVICE_NAME", device_id),
    )


def ensure_enrolled(
    token_manager: TokenManager,
    config: EnrollmentConfig,
    http_client: Any,
    *,
    sleep: Callable[[float], None] = time.sleep,
    backoff_steps: tuple[float, ...] = _DEFAULT_BACKOFF_STEPS,
) -> DeviceIdentity:
    """Enrolls the device if it has no valid persisted identity yet.

    Idempotent: a valid (non-revoked) identity already on disk short-circuits
    without any network call. Network errors retry with backoff; a definitive
    rejection (401 bad token, 409 duplicate device) raises immediately — no
    retry loop, per PR-A scope ("mensagem clara e parada").
    """
    if token_manager.has_valid_identity():
        identity = token_manager.identity
        logger.info(
            "enrollment_skipped device_id=%s (identidade já persistida)", identity.device_id
        )
        return identity

    if not config.enrollment_token:
        raise EnrollmentError(
            "ENROLLMENT_TOKEN não definido — necessário para o primeiro enroll deste device"
        )

    url = f"{config.api_url}/api/v1/edge/enroll"
    body = {
        "enrollment_token": config.enrollment_token,
        "device_id": config.device_id,
        "device_name": config.device_name,
        "public_key_pem": token_manager.public_key_pem,
    }

    last_exc: Exception | None = None
    for attempt, delay in enumerate((0.0, *backoff_steps)):
        if delay:
            logger.warning("enroll_retry attempt=%d delay_s=%s", attempt, delay)
            sleep(delay)
        try:
            resp = http_client.post(url, json=body, timeout=30.0)
        except Exception as exc:  # network / timeout — retryable
            last_exc = exc
            logger.warning("enroll_network_error attempt=%d %s", attempt + 1, exc)
            continue

        if resp.status_code == 401:
            raise EnrollmentError(
                "enrollment_token inválido, expirado ou já utilizado (é one-time) — "
                "gere um novo token no admin"
            )
        if resp.status_code == 409:
            raise EnrollmentError(
                f"device_id {config.device_id!r} já cadastrado neste tenant — "
                "use outro DEVICE_ID ou revogue o anterior no admin"
            )
        if resp.status_code != 201:
            raise EnrollmentError(f"enroll falhou HTTP {resp.status_code}: {resp.text[:300]}")

        data = (resp.json() or {}).get("data") or {}
        missing = [k for k in ("tenant_id", "site_id", "device_id", "scopes") if k not in data]
        if missing:
            raise EnrollmentError(f"resposta de enroll sem campo(s) {missing}")

        identity = token_manager.save_identity(
            device_id=data["device_id"],
            tenant_id=data["tenant_id"],
            site_id=data["site_id"],
            scopes=data["scopes"],
        )
        logger.info(
            "enrolled device_id=%s tenant=%s… site=%s… scopes=%s",
            identity.device_id, identity.tenant_id[:8], identity.site_id[:8], identity.scopes,
        )
        return identity

    raise EnrollmentError(
        f"enroll falhou após {len(backoff_steps) + 1} tentativas (falha de rede): {last_exc}"
    )
