"""Tests: retention/routes.py — tiers de retenção por tenant (task-047)."""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
_POOL_PATH = "app.api.v1.retention.routes.DatabasePool"


def _make_headers(app, role="admin"):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "role": role,
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _make_pool(fetchone_row=None):
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = fetchone_row
        mock_conn.cursor.return_value = mock_cur
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


# ---------------------------------------------------------------------------
# GET /api/v1/tenant/retention
# ---------------------------------------------------------------------------

class TestGetTenantRetention:

    def test_no_token_returns_401(self, client):
        assert client.get("/api/v1/tenant/retention").status_code == 401

    def test_tenant_not_found_returns_404(self, client, app):
        headers = _make_headers(app)
        mock_pool = _make_pool(fetchone_row=None)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.get("/api/v1/tenant/retention", headers=headers)
        assert resp.status_code == 404

    def test_effective_from_plan_when_no_override(self, client, app):
        headers = _make_headers(app)
        row = {"plan_days": 30, "default_retention_days": None}
        mock_pool = _make_pool(fetchone_row=row)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.get("/api/v1/tenant/retention", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["effective_retention_days"] == 30
        assert data["data"]["default_retention_days"] is None

    def test_override_takes_precedence_over_plan(self, client, app):
        headers = _make_headers(app)
        row = {"plan_days": 30, "default_retention_days": 7}
        mock_pool = _make_pool(fetchone_row=row)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.get("/api/v1/tenant/retention", headers=headers)
        assert resp.get_json()["data"]["effective_retention_days"] == 7

    def test_allowed_tiers_included_in_response(self, client, app):
        headers = _make_headers(app)
        row = {"plan_days": 7, "default_retention_days": None}
        mock_pool = _make_pool(fetchone_row=row)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.get("/api/v1/tenant/retention", headers=headers)
        tiers = resp.get_json()["data"]["allowed_tiers"]
        for expected in (1, 7, 30, 90):
            assert expected in tiers

    def test_db_error_returns_500(self, client, app):
        headers = _make_headers(app)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.side_effect = Exception("DB error")
            resp = client.get("/api/v1/tenant/retention", headers=headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# PUT /api/v1/tenant/retention
# ---------------------------------------------------------------------------

class TestPutTenantRetention:

    def test_no_token_returns_401(self, client):
        resp = client.put("/api/v1/tenant/retention", json={"default_retention_days": 7})
        assert resp.status_code == 401

    def test_operator_role_returns_403(self, client, app):
        headers = _make_headers(app, role="operator")
        resp = client.put(
            "/api/v1/tenant/retention",
            json={"default_retention_days": 7},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_invalid_tier_returns_422(self, client, app):
        headers = _make_headers(app)
        resp = client.put(
            "/api/v1/tenant/retention",
            json={"default_retention_days": 15},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_non_integer_returns_422(self, client, app):
        headers = _make_headers(app)
        resp = client.put(
            "/api/v1/tenant/retention",
            json={"default_retention_days": "7"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_valid_update_as_admin_returns_200(self, client, app):
        headers = _make_headers(app, role="admin")
        mock_pool = _make_pool(fetchone_row={"id": TENANT_ID})
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.put(
                "/api/v1/tenant/retention",
                json={"default_retention_days": 30},
                headers=headers,
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["default_retention_days"] == 30

    def test_superadmin_can_set_retention(self, client, app):
        headers = _make_headers(app, role="superadmin")
        mock_pool = _make_pool(fetchone_row={"id": TENANT_ID})
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.put(
                "/api/v1/tenant/retention",
                json={"default_retention_days": 90},
                headers=headers,
            )
        assert resp.status_code == 200

    def test_all_valid_tiers_accepted(self, client, app):
        headers = _make_headers(app)
        for days in (1, 7, 30, 90):
            mock_pool = _make_pool(fetchone_row={"id": TENANT_ID})
            with patch(_POOL_PATH) as mock_cls:
                mock_cls.get_instance.return_value = mock_pool
                resp = client.put(
                    "/api/v1/tenant/retention",
                    json={"default_retention_days": days},
                    headers=headers,
                )
            assert resp.status_code == 200, f"tier {days} should be accepted"

    def test_tenant_not_found_returns_404(self, client, app):
        headers = _make_headers(app)
        mock_pool = _make_pool(fetchone_row=None)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.put(
                "/api/v1/tenant/retention",
                json={"default_retention_days": 7},
                headers=headers,
            )
        assert resp.status_code == 404

    def test_db_error_returns_500(self, client, app):
        headers = _make_headers(app)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.side_effect = Exception("DB error")
            resp = client.put(
                "/api/v1/tenant/retention",
                json={"default_retention_days": 7},
                headers=headers,
            )
        assert resp.status_code == 500
