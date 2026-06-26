"""Tests for task-010: GET /api/v1/edge/sites/<site_id>/devices.

Eval cases (spec):
  1. lista devices do site do tenant; campos esperados presentes; public_key_pem/fingerprint AUSENTES
  2. isolamento: device de outro tenant nunca aparece; site de outro tenant → 404
  3. role insuficiente → 403; sem JWT → 401
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

from tests.security._helpers_tenant import make_two_tenant_contexts


def _make_jwt(app, tenant_id, role="admin", user_id=None):
    uid = str(user_id or uuid4())
    with app.app_context():
        return create_access_token(
            identity=uid,
            additional_claims={"tenant_id": str(tenant_id), "role": role},
        )


def _mock_site(tenant_id, site_id):
    return {
        "id": str(site_id),
        "tenant_id": str(tenant_id),
        "name": "Site X",
        "deployment_mode": "edge",
        "status": "active",
    }


def _mock_device(site_id, tenant_id, device_id=None):
    return {
        "id": str(uuid4()),
        "device_id": device_id or f"device-{str(uuid4())[:8]}",
        "device_name": "Mini PC 01",
        "revoked": False,
        "last_seen_at": datetime(2026, 6, 3, tzinfo=timezone.utc),
        "enrolled_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        # These should NEVER appear in the API response:
        "public_key_pem": "SENSITIVE_KEY_MATERIAL",
        "fingerprint": "SENSITIVE_FINGERPRINT",
    }


class TestListDevices:

    def test_returns_devices_with_expected_fields(self, client, app):
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)
        device = _mock_device(site_id, tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = _mock_site(tenant_id, site_id)
        mock_repo.list_devices.return_value = [device]

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                f"/api/v1/edge/sites/{site_id}/devices",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        devices = data["data"]["devices"]
        assert len(devices) == 1

        d = devices[0]
        for field in ("id", "device_id", "device_name", "revoked", "last_seen_at", "enrolled_at"):
            assert field in d, f"Campo '{field}' ausente da resposta"

    def test_public_key_and_fingerprint_absent_from_response(self, client, app):
        """C-05: public_key_pem e fingerprint NÃO devem aparecer na resposta."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)
        device = _mock_device(site_id, tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = _mock_site(tenant_id, site_id)
        mock_repo.list_devices.return_value = [device]

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                f"/api/v1/edge/sites/{site_id}/devices",
                headers={"Authorization": f"Bearer {token}"},
            )

        raw = res.get_data(as_text=True)
        assert "public_key_pem" not in raw, "public_key_pem NÃO deve aparecer na resposta"
        assert "fingerprint" not in raw, "fingerprint NÃO deve aparecer na resposta"
        assert "SENSITIVE_KEY_MATERIAL" not in raw
        assert "SENSITIVE_FINGERPRINT" not in raw

    def test_cross_tenant_site_returns_404(self, client, app):
        """C-01: site de outro tenant → 404."""
        ctx_a, ctx_b = make_two_tenant_contexts(app)

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = None  # site não pertence a ctx_b

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                f"/api/v1/edge/sites/{ctx_a.site_id}/devices",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert res.status_code == 404
        mock_repo.list_devices.assert_not_called()

    def test_cross_tenant_devices_never_in_response(self, client, app):
        """C-01: devices de tenant_a nunca aparecem quando tenant_b lista seu site."""
        ctx_a, ctx_b = make_two_tenant_contexts(app)
        device_b = _mock_device(ctx_b.site_id, ctx_b.tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = _mock_site(ctx_b.tenant_id, ctx_b.site_id)
        mock_repo.list_devices.return_value = [device_b]

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                f"/api/v1/edge/sites/{ctx_b.site_id}/devices",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert res.status_code == 200
        # Repo chamado sempre com tenant_b, nunca tenant_a
        mock_repo.list_devices.assert_called_once_with(
            str(ctx_b.tenant_id), str(ctx_b.site_id)
        )

    def test_no_jwt_returns_401(self, client):
        res = client.get(f"/api/v1/edge/sites/{uuid4()}/devices")
        assert res.status_code == 401

    def test_operator_role_returns_403(self, client, app):
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id, role="operator")

        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                f"/api/v1/edge/sites/{site_id}/devices",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 403
        mock_repo.list_devices.assert_not_called()

    def test_list_called_with_jwt_tenant_and_site(self, client, app):
        """Repo chamado com tenant_id do JWT + site_id do path."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = _mock_site(tenant_id, site_id)
        mock_repo.list_devices.return_value = []

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            client.get(
                f"/api/v1/edge/sites/{site_id}/devices",
                headers={"Authorization": f"Bearer {token}"},
            )

        mock_repo.list_devices.assert_called_once_with(str(tenant_id), str(site_id))
