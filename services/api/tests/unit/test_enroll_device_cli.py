"""Round-trip do CLI de enrollment: o token que ele assina passa em verify_device_token.

Garante que `scripts/edge/enroll_device.py` produz um DeviceClaims JWT RS256 com o
contrato exato que o backend verifica (core/device_auth), fechando a peça que
faltava no caminho de heartbeat (o device auto-assina — ADR-0019).
"""
import importlib.util
from pathlib import Path

import pytest

from app.core.device_auth import verify_device_token
from app.core.exceptions import AuthenticationError

_CLI_PATH = Path(__file__).resolve().parents[4] / "scripts" / "edge" / "enroll_device.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("enroll_device", _CLI_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_file_exists():
    assert _CLI_PATH.is_file(), f"CLI ausente em {_CLI_PATH}"


def test_signed_token_passes_backend_verification():
    cli = _load_cli()
    private_pem, public_pem = cli.generate_keypair()
    ctx = {
        "api_url": "https://api.test",
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "site_id": "22222222-2222-2222-2222-222222222222",
        "device_id": "pandora-orin-rvb",
        "scopes": ["heartbeat:write", "events:write"],
    }
    token = cli.sign_token(private_pem, ctx, ttl_hours=1)

    claims = verify_device_token(token, public_pem)  # não deve levantar

    assert str(claims.tenant_id) == ctx["tenant_id"]
    assert str(claims.site_id) == ctx["site_id"]
    assert claims.device_id == ctx["device_id"]
    scope_values = {getattr(s, "value", s) for s in claims.scopes}
    assert "heartbeat:write" in scope_values
    assert "events:write" in scope_values


def test_token_rejected_by_wrong_public_key():
    cli = _load_cli()
    private_pem, _ = cli.generate_keypair()
    _, other_public = cli.generate_keypair()
    ctx = {
        "api_url": "https://api.test",
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "site_id": "22222222-2222-2222-2222-222222222222",
        "device_id": "pandora-orin-rvb",
        "scopes": ["heartbeat:write"],
    }
    token = cli.sign_token(private_pem, ctx, ttl_hours=1)
    with pytest.raises(AuthenticationError):
        verify_device_token(token, other_public)
