"""
Tests for POST /api/v1/edge/heartbeat.

Covers (spec eval cases):
  1. Valid RS256 token + valid payload → 201, heartbeat persisted
  2. Token signed by wrong key → 401, nothing persisted
  3. Revoked device → 403, nothing persisted
  4. Expired token → 401, nothing persisted
  5. Missing Authorization header → 401
  6. Payload missing required field (status) → 422

Keypair is generated in-test; no enrollment dependency.
"""
import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_keypair() -> tuple[str, str]:
    """Generate a fresh RS256 keypair. Returns (private_pem, public_pem)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def _make_token(
    private_pem: str,
    tenant_id: object,
    site_id: object,
    device_id: str,
    exp_offset: int = 3600,
) -> str:
    """Sign a DeviceClaims JWT with the given private key."""
    now = int(time.time())
    return jwt.encode(
        {
            "tenant_id": str(tenant_id),
            "site_id": str(site_id),
            "device_id": device_id,
            "scopes": ["heartbeat:write"],
            "iat": now,
            "exp": now + exp_offset,
        },
        private_pem,
        algorithm="RS256",
    )


VALID_PAYLOAD = {
    "device_id": "edge-device-001",
    "status": "healthy",
    "cpu_pct": "12.5",
    "mem_pct": "40.0",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def device_setup():
    """Returns (private_pem, public_pem, tenant_id, site_id, device_id)."""
    private_pem, public_pem = _generate_keypair()
    return private_pem, public_pem, uuid4(), uuid4(), "edge-device-001"


@pytest.fixture()
def device_record(device_setup):
    """Simulates a device_tokens row as returned by the repository."""
    _, public_pem, tenant_id, site_id, device_id = device_setup
    return {
        "id": str(uuid4()),
        "tenant_id": tenant_id,
        "site_id": site_id,
        "device_id": device_id,
        "public_key_pem": public_pem,
        "revoked": False,
    }


@pytest.fixture()
def mock_repo(device_record):
    """Mock EdgeHeartbeatRepository with a seeded active device."""
    repo = MagicMock()
    repo.get_device_by_device_id.return_value = device_record
    repo.insert_heartbeat.return_value = {
        "id": 42,
        "received_at": "2026-06-02T00:00:00+00:00",
    }
    repo.update_last_seen.return_value = None
    return repo


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestEdgeHeartbeatIngest:

    def test_valid_token_and_payload_returns_201(
        self, client, device_setup, mock_repo
    ) -> None:
        private_pem, _, tenant_id, site_id, device_id = device_setup
        token = _make_token(private_pem, tenant_id, site_id, device_id)

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/heartbeat",
                json=VALID_PAYLOAD,
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["id"] == 42
        mock_repo.insert_heartbeat.assert_called_once()
        mock_repo.update_last_seen.assert_called_once()

    def test_token_signed_by_wrong_key_returns_401(
        self, client, device_setup, mock_repo
    ) -> None:
        wrong_private_pem, _ = _generate_keypair()
        _, _, tenant_id, site_id, device_id = device_setup
        token = _make_token(wrong_private_pem, tenant_id, site_id, device_id)

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/heartbeat",
                json=VALID_PAYLOAD,
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 401
        mock_repo.insert_heartbeat.assert_not_called()

    def test_revoked_device_returns_403(
        self, client, device_setup, mock_repo, device_record
    ) -> None:
        device_record["revoked"] = True
        private_pem, _, tenant_id, site_id, device_id = device_setup
        token = _make_token(private_pem, tenant_id, site_id, device_id)

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/heartbeat",
                json=VALID_PAYLOAD,
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 403
        mock_repo.insert_heartbeat.assert_not_called()

    def test_expired_token_returns_401(
        self, client, device_setup, mock_repo
    ) -> None:
        private_pem, _, tenant_id, site_id, device_id = device_setup
        token = _make_token(private_pem, tenant_id, site_id, device_id, exp_offset=-60)

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/heartbeat",
                json=VALID_PAYLOAD,
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 401
        mock_repo.insert_heartbeat.assert_not_called()

    def test_missing_authorization_returns_401(self, client) -> None:
        res = client.post("/api/v1/edge/heartbeat", json=VALID_PAYLOAD)
        assert res.status_code == 401

    def test_invalid_payload_missing_status_returns_422(
        self, client, device_setup, mock_repo
    ) -> None:
        private_pem, _, tenant_id, site_id, device_id = device_setup
        token = _make_token(private_pem, tenant_id, site_id, device_id)

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/heartbeat",
                json={"device_id": "edge-device-001"},  # missing required 'status'
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 422
        mock_repo.insert_heartbeat.assert_not_called()

    def test_forged_claims_tenant_mismatch_returns_403_and_nothing_stored(
        self, client, device_setup, mock_repo
    ) -> None:
        """C-01: device forja claims com tenant_b diferente do enrollment (tenant_a).
        Deve retornar 403 e nenhuma linha deve ser gravada sob tenant_b ou tenant_a."""
        private_pem, _, tenant_a, site_a, device_id = device_setup
        tenant_b, site_b = uuid4(), uuid4()
        # Token válido (assinado pela chave correta), mas claims apontam para tenant_b
        token = _make_token(private_pem, tenant_b, site_b, device_id)

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/heartbeat",
                json=VALID_PAYLOAD,
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 403
        # Nada gravado — tenant forjado (B) nunca persiste
        mock_repo.insert_heartbeat.assert_not_called()
        # Assert explícito: tenant_b não aparece em nenhuma chamada ao repo
        for call in mock_repo.insert_heartbeat.call_args_list:
            stored_tenant = call.args[0] if call.args else call.kwargs.get("tenant_id")
            assert str(stored_tenant) != str(tenant_b), (
                f"tenant forjado {tenant_b} NÃO deve ser gravado em edge_heartbeats"
            )
