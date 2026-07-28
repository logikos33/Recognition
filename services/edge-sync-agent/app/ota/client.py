"""Fetches the target software ref from the cloud (GET /api/v1/edge/software/target).

The nuvem only ever INDICATES a target — this call never pushes/applies
anything by itself; `updater.run_once` decides whether to act on it.
"""

from __future__ import annotations

from typing import Any, Protocol


class TargetFetchError(Exception):
    """Raised when the cloud call fails or returns an unusable response."""


class TokenSource(Protocol):
    def get_bearer(self, ttl_s: int = 300) -> str: ...


def fetch_target_ref(
    http_client: Any,
    cloud_url: str,
    token_source: TokenSource,
    *,
    channel: str | None = None,
) -> str:
    url = f"{cloud_url.rstrip('/')}/api/v1/edge/software/target"
    params = {"channel": channel} if channel else None
    token = token_source.get_bearer()

    try:
        resp = http_client.get(
            url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=15.0
        )
    except Exception as exc:  # network/timeout
        raise TargetFetchError(f"falha de rede consultando target_ref: {exc}") from exc

    if resp.status_code != 200:
        raise TargetFetchError(f"GET /edge/software/target falhou HTTP {resp.status_code}")

    body = resp.json() or {}
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    target_ref = data.get("target_ref")
    if not target_ref:
        raise TargetFetchError("resposta de /edge/software/target sem 'target_ref'")
    return target_ref
