"""
Tests for POST /api/v1/edge/enroll.

Eval cases (spec task-004):
  1. Valid token + valid body → 201; device_tokens created with tenant_id/site_id from
     the enrollment_tokens row (never from body) — C-01.
  2. Same token used 2× → 2nd call 401, no new device created (one-time atomic).
  3. Expired token → 401, nothing created.
  4. Body with forged tenant_id → ignored; device gets tenant from enrollment record (C-01).
  5. device_id already enrolled in tenant → 409.
"""
import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import psycopg2.errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_PUBLIC_KEY = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Z3VS5JJcds3xHn/ygWe\n"
    "-----END PUBLIC KEY-----\n"
)


def _valid_body(device_id="mini-pc-001", token="tok-abc123"):
    return {
        "enrollment_token": token,
        "device_id": device_id,
        "device_name": "Mini PC Galpão 1",
        "public_key_pem": _FAKE_PUBLIC_KEY,
    }


def _mock_device_row(tenant_id, site_id, device_id="mini-pc-001"):
    return {
        "id": str(uuid4()),
        "tenant_id": str(tenant_id),
        "site_id": str(site_id),
        "device_id": device_id,
        "enrolled_at": datetime(2026, 6, 3, tzinfo=timezone.utc),
    }


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestEnrollDevice:

    def test_valid_token_returns_201_with_enrollment_tenant(self, client, app):
        """Eval 1: valid token → 201; response tenant/site come from enrollment record."""
        tenant_a = uuid4()
        site_a = uuid4()
        device_row = _mock_device_row(tenant_a, site_a)

        mock_repo = MagicMock()
        mock_repo.enroll_device.return_value = device_row

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post("/api/v1/edge/enroll", json=_valid_body())

        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["tenant_id"] == str(tenant_a)
        assert data["data"]["site_id"] == str(site_a)
        assert data["data"]["device_id"] == "mini-pc-001"
        assert len(data["data"]["scopes"]) > 0

    def test_valid_token_repo_called_with_correct_hash_and_key(self, client, app):
        """Eval 1: repo.enroll_device receives SHA-256 of token and fingerprint of public key."""
        tenant_a = uuid4()
        site_a = uuid4()
        plaintext_token = "tok-verify-hash"
        body = _valid_body(token=plaintext_token)

        mock_repo = MagicMock()
        mock_repo.enroll_device.return_value = _mock_device_row(tenant_a, site_a)

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post("/api/v1/edge/enroll", json=body)

        assert res.status_code == 201
        call_kwargs = mock_repo.enroll_device.call_args.kwargs
        expected_hash = hashlib.sha256(plaintext_token.encode()).hexdigest()
        expected_fingerprint = hashlib.sha256(_FAKE_PUBLIC_KEY.encode()).hexdigest()
        assert call_kwargs["token_hash"] == expected_hash
        assert call_kwargs["fingerprint"] == expected_fingerprint
        assert call_kwargs["public_key_pem"] == _FAKE_PUBLIC_KEY

    def test_same_token_used_twice_second_call_returns_401(self, client, app):
        """Eval 2: second use of same token → 401, no new device created."""
        tenant_a = uuid4()
        site_a = uuid4()
        device_row = _mock_device_row(tenant_a, site_a)

        mock_repo = MagicMock()
        # First call succeeds; second raises ValueError (token already used)
        mock_repo.enroll_device.side_effect = [
            device_row,
            ValueError("enrollment_token_invalid"),
        ]

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res1 = client.post("/api/v1/edge/enroll", json=_valid_body())
            res2 = client.post("/api/v1/edge/enroll", json=_valid_body())

        assert res1.status_code == 201
        assert res2.status_code == 401
        assert mock_repo.enroll_device.call_count == 2

    def test_expired_token_returns_401(self, client, app):
        """Eval 3: expired token → 401, nothing created."""
        mock_repo = MagicMock()
        mock_repo.enroll_device.side_effect = ValueError("enrollment_token_invalid")

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post("/api/v1/edge/enroll", json=_valid_body())

        assert res.status_code == 401
        mock_repo.enroll_device.assert_called_once()

    def test_forged_tenant_id_in_body_is_ignored(self, client, app):
        """Eval 4: body with extra tenant_id field is ignored; device gets tenant from enrollment (C-01)."""
        tenant_a = uuid4()
        site_a = uuid4()
        tenant_forged = uuid4()

        device_row = _mock_device_row(tenant_a, site_a)
        mock_repo = MagicMock()
        mock_repo.enroll_device.return_value = device_row

        body = _valid_body()
        body["tenant_id"] = str(tenant_forged)  # forged field — must be ignored

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post("/api/v1/edge/enroll", json=body)

        assert res.status_code == 201
        data = res.get_json()
        # Response tenant must come from enrollment record, not from body
        assert data["data"]["tenant_id"] == str(tenant_a)
        assert data["data"]["tenant_id"] != str(tenant_forged)
        # enroll_device must NOT have been called with the forged tenant
        call_kwargs = mock_repo.enroll_device.call_args.kwargs
        assert "tenant_id" not in call_kwargs, (
            "tenant_id from body must never reach the repository call"
        )

    def test_duplicate_device_id_returns_409(self, client, app):
        """Eval 5: device_id already enrolled in tenant → 409."""
        mock_repo = MagicMock()
        mock_repo.enroll_device.side_effect = psycopg2.errors.UniqueViolation()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post("/api/v1/edge/enroll", json=_valid_body())

        assert res.status_code == 409
        mock_repo.enroll_device.assert_called_once()

    def test_missing_required_fields_returns_422(self, client, app):
        """Body missing enrollment_token → 422."""
        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/enroll",
                json={"device_id": "mini-pc-001"},  # missing enrollment_token + public_key_pem
            )

        assert res.status_code == 422
        mock_repo.enroll_device.assert_not_called()

    def test_missing_public_key_returns_422(self, client, app):
        """Body missing public_key_pem → 422."""
        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/enroll",
                json={"enrollment_token": "tok", "device_id": "mini-pc-001"},
            )

        assert res.status_code == 422
        mock_repo.enroll_device.assert_not_called()

    def test_response_scopes_contain_heartbeat_write(self, client, app):
        """Scopes in response must include heartbeat:write."""
        tenant_a = uuid4()
        site_a = uuid4()
        mock_repo = MagicMock()
        mock_repo.enroll_device.return_value = _mock_device_row(tenant_a, site_a)

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post("/api/v1/edge/enroll", json=_valid_body())

        assert res.status_code == 201
        scopes = res.get_json()["data"]["scopes"]
        assert "heartbeat:write" in scopes
