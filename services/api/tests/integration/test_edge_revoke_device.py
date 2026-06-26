"""Tests for task-011: POST /api/v1/edge/devices/<device_pk>/revoke.

Eval cases (spec):
  1. revogar device do tenant → 200, revoked=true, revoked_at/revoked_by setados
  2. idempotência: revogar 2x → 200 nas duas, sem erro
  3. isolamento: revogar device de OUTRO tenant → 404; device do outro tenant continua revoked=false
  4. integração: após revogar, heartbeat com token desse device → 403 (reusar fluxo task-002)
  5. role insuficiente → 403; sem JWT → 401
"""
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import jwt as pyjwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask_jwt_extended import create_access_token

from tests.security._helpers_tenant import make_two_tenant_contexts


def _make_jwt(app, tenant_id, role="admin", user_id=None):
    uid = str(user_id or uuid4())
    with app.app_context():
        return create_access_token(
            identity=uid,
            additional_claims={"tenant_id": str(tenant_id), "role": role},
        )


def _revoked_row(device_pk, device_id="edge-device-001"):
    return {
        "id": str(device_pk),
        "device_id": device_id,
        "revoked": True,
        "revoked_at": datetime.now(timezone.utc),
        "revoked_by": str(uuid4()),
        "revocation_reason": "manual",
    }


def _generate_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv, pub


def _make_device_token(private_pem, tenant_id, site_id, device_id, exp_offset=3600):
    now = int(time.time())
    return pyjwt.encode(
        {
            "device_id": device_id,
            "tenant_id": str(tenant_id),
            "site_id": str(site_id),
            "scopes": ["heartbeat:write"],
            "iat": now,
            "exp": now + exp_offset,
        },
        private_pem,
        algorithm="RS256",
    )


class TestRevokeDevice:

    def test_revoke_returns_200_and_revoked_true(self, client, app):
        tenant_id = uuid4()
        device_pk = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_repo = MagicMock()
        mock_repo.revoke_device.return_value = _revoked_row(device_pk)

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/devices/{device_pk}/revoke",
                headers={"Authorization": f"Bearer {token}"},
                json={},
            )

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["revoked"] is True

    def test_revoke_sets_revoked_at_and_revoked_by(self, client, app):
        tenant_id = uuid4()
        user_id = uuid4()
        device_pk = uuid4()
        token = _make_jwt(app, tenant_id, user_id=user_id)

        mock_repo = MagicMock()
        mock_repo.revoke_device.return_value = _revoked_row(device_pk)

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            client.post(
                f"/api/v1/edge/devices/{device_pk}/revoke",
                headers={"Authorization": f"Bearer {token}"},
                json={},
            )

        # Confirma que revoke_device foi chamado com o user correto
        call_args = mock_repo.revoke_device.call_args
        assert call_args.args[0] == str(device_pk)   # device_pk
        assert call_args.args[1] == str(tenant_id)   # tenant_id
        assert call_args.args[2] == str(user_id)     # revoked_by

    def test_idempotent_revoke_twice_returns_200_both_times(self, client, app):
        """Spec: idempotente — revogar device já revogado → 200 no-op."""
        tenant_id = uuid4()
        device_pk = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_repo = MagicMock()
        mock_repo.revoke_device.return_value = _revoked_row(device_pk)

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res1 = client.post(
                f"/api/v1/edge/devices/{device_pk}/revoke",
                headers={"Authorization": f"Bearer {token}"},
                json={},
            )
            res2 = client.post(
                f"/api/v1/edge/devices/{device_pk}/revoke",
                headers={"Authorization": f"Bearer {token}"},
                json={},
            )

        assert res1.status_code == 200
        assert res2.status_code == 200

    def test_cross_tenant_device_returns_404(self, client, app):
        """C-01: revogar device de outro tenant → 404, device do outro tenant inalterado."""
        ctx_a, ctx_b = make_two_tenant_contexts(app)
        device_pk = uuid4()

        mock_repo = MagicMock()
        mock_repo.revoke_device.return_value = None  # não pertence ao tenant_b

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/devices/{device_pk}/revoke",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
                json={},
            )

        assert res.status_code == 404
        # Repo chamado com tenant_b — nunca toca dados do tenant_a
        call_args = mock_repo.revoke_device.call_args
        assert call_args.args[1] == str(ctx_b.tenant_id)
        assert call_args.args[1] != str(ctx_a.tenant_id)

    def test_after_revoke_heartbeat_returns_403(self, client, app):
        """Integração: heartbeat de device revogado → 403."""
        priv_pem, pub_pem = _generate_keypair()
        tenant_id = uuid4()
        site_id = uuid4()
        device_id = "edge-revoke-test-001"
        device_token = _make_device_token(priv_pem, tenant_id, site_id, device_id)

        # Device está revogado
        device_record = {
            "id": str(uuid4()),
            "tenant_id": tenant_id,
            "site_id": site_id,
            "device_id": device_id,
            "public_key_pem": pub_pem,
            "revoked": True,
        }
        mock_hb_repo = MagicMock()
        mock_hb_repo.get_device_by_device_id.return_value = device_record

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo):
            res = client.post(
                "/api/v1/edge/heartbeat",
                json={"device_id": device_id, "status": "healthy"},
                headers={"Authorization": f"Bearer {device_token}"},
            )

        assert res.status_code == 403
        mock_hb_repo.insert_heartbeat.assert_not_called()

    def test_no_jwt_returns_401(self, client):
        res = client.post(f"/api/v1/edge/devices/{uuid4()}/revoke", json={})
        assert res.status_code == 401

    def test_operator_role_returns_403(self, client, app):
        tenant_id = uuid4()
        device_pk = uuid4()
        token = _make_jwt(app, tenant_id, role="operator")

        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/devices/{device_pk}/revoke",
                headers={"Authorization": f"Bearer {token}"},
                json={},
            )

        assert res.status_code == 403
        mock_repo.revoke_device.assert_not_called()

    def test_revoke_with_reason_passed_to_repo(self, client, app):
        tenant_id = uuid4()
        device_pk = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_repo = MagicMock()
        mock_repo.revoke_device.return_value = _revoked_row(device_pk)

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            client.post(
                f"/api/v1/edge/devices/{device_pk}/revoke",
                headers={"Authorization": f"Bearer {token}"},
                json={"reason": "dispositivo perdido"},
            )

        call_args = mock_repo.revoke_device.call_args
        reason_used = call_args.args[3] if len(call_args.args) > 3 else call_args.kwargs.get("reason")
        assert reason_used == "dispositivo perdido"
