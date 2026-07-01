"""Tests: branding routes — existing GET/PUT/logo (branding/routes.py) and task-048 admin branding routes."""
import io
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
_POOL_PATH = "app.api.v1.branding.routes.DatabasePool"


@pytest.fixture
def admin_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "email": "admin@test.com",
                "role": "admin",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def superadmin_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "email": "superadmin@test.com",
                "role": "superadmin",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _make_pool(row=None, rows=None, returning=None):
    """Build mock pool whose cursor returns configured results."""
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        # Support `with conn.cursor() as cur:` — __enter__ must return the cursor itself
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = row
        mock_cur.fetchall.return_value = rows or []
        mock_conn.cursor.return_value = mock_cur
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


# ---------------------------------------------------------------------------
# PUT /api/v1/admin/branding
# ---------------------------------------------------------------------------

class TestUpdateBranding:

    def test_without_token_returns_401(self, client):
        resp = client.put("/api/v1/admin/branding", json={"branding": {}})
        assert resp.status_code == 401

    def test_operator_role_returns_403(self, client, app):
        with app.app_context():
            from flask_jwt_extended import create_access_token
            token = create_access_token(
                identity=USER_ID,
                additional_claims={
                    "tenant_id": TENANT_ID, "tenant_schema": "public",
                    "role": "operator", "modules": [],
                },
            )
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.put("/api/v1/admin/branding", json={"branding": {}}, headers=headers)
        assert resp.status_code == 403

    def test_missing_branding_field_returns_400(self, client, admin_headers):
        resp = client.put("/api/v1/admin/branding", json={}, headers=admin_headers)
        assert resp.status_code == 400

    def test_invalid_branding_type_returns_400(self, client, admin_headers):
        resp = client.put("/api/v1/admin/branding",
                          json={"branding": "not-a-dict"}, headers=admin_headers)
        assert resp.status_code == 400

    def test_invalid_branding_keys_returns_400(self, client, admin_headers):
        resp = client.put("/api/v1/admin/branding",
                          json={"branding": {"unauthorized_key": "value"}},
                          headers=admin_headers)
        assert resp.status_code == 400

    def test_valid_branding_updates_and_returns_200(self, client, admin_headers):
        returning_row = {"id": TENANT_ID}

        @contextmanager
        def _conn_ctx():
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.__enter__ = MagicMock(return_value=mock_cur)
            mock_cur.__exit__ = MagicMock(return_value=False)
            mock_cur.fetchone.return_value = returning_row
            mock_conn.cursor.return_value = mock_cur
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _conn_ctx

        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.put(
                "/api/v1/admin/branding",
                json={"branding": {"brand": {"name": "Acme"}}},
                headers=admin_headers,
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["branding"]["brand"]["name"] == "Acme"

    def test_tenant_not_found_returns_404(self, client, admin_headers):
        @contextmanager
        def _conn_ctx():
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.__enter__ = MagicMock(return_value=mock_cur)
            mock_cur.__exit__ = MagicMock(return_value=False)
            mock_cur.fetchone.return_value = None  # no row returned
            mock_conn.cursor.return_value = mock_cur
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _conn_ctx

        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.put(
                "/api/v1/admin/branding",
                json={"branding": {"colors": {}}},
                headers=admin_headers,
            )
        assert resp.status_code == 404

    def test_superadmin_can_pass_explicit_tenant_id(self, client, superadmin_headers):
        other_tenant = str(uuid4())

        @contextmanager
        def _conn_ctx():
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.__enter__ = MagicMock(return_value=mock_cur)
            mock_cur.__exit__ = MagicMock(return_value=False)
            mock_cur.fetchone.return_value = {"id": other_tenant}
            mock_conn.cursor.return_value = mock_cur
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _conn_ctx

        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.put(
                "/api/v1/admin/branding",
                json={"branding": {"brand": {}}, "tenant_id": other_tenant},
                headers=superadmin_headers,
            )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["tenant_id"] == other_tenant


# ---------------------------------------------------------------------------
# POST /api/v1/admin/branding/logo
# ---------------------------------------------------------------------------

class TestUploadLogo:

    def test_without_token_returns_401(self, client):
        resp = client.post("/api/v1/admin/branding/logo")
        assert resp.status_code == 401

    def test_no_file_returns_400(self, client, admin_headers):
        resp = client.post("/api/v1/admin/branding/logo", headers=admin_headers)
        assert resp.status_code == 400

    def test_invalid_mime_returns_415(self, client, admin_headers):
        data = {"file": (io.BytesIO(b"data"), "test.exe", "application/octet-stream")}
        resp = client.post(
            "/api/v1/admin/branding/logo",
            content_type="multipart/form-data",
            data=data,
            headers=admin_headers,
        )
        assert resp.status_code == 415

    def test_file_too_large_returns_413(self, client, admin_headers):
        big_data = b"x" * (2 * 1024 * 1024 + 1)
        data = {"file": (io.BytesIO(big_data), "logo.png", "image/png")}
        resp = client.post(
            "/api/v1/admin/branding/logo",
            content_type="multipart/form-data",
            data=data,
            headers=admin_headers,
        )
        assert resp.status_code == 413

    def test_valid_png_upload_returns_200(self, client, admin_headers):
        mock_storage = MagicMock()
        mock_storage.upload_bytes.return_value = None
        mock_storage.generate_presigned_download_url.return_value = "https://cdn.test/logo.png"

        data = {"file": (io.BytesIO(b"fake-png-data"), "logo.png", "image/png")}

        with patch("app.api.v1.branding.routes.get_storage", return_value=mock_storage):
            resp = client.post(
                "/api/v1/admin/branding/logo",
                content_type="multipart/form-data",
                data=data,
                headers=admin_headers,
            )
        assert resp.status_code == 200
        result = resp.get_json()
        assert "key" in result["data"]

    def test_valid_jpeg_upload_sets_correct_extension(self, client, admin_headers):
        mock_storage = MagicMock()
        data = {"file": (io.BytesIO(b"fake-jpg"), "logo.jpg", "image/jpeg")}
        with patch("app.api.v1.branding.routes.get_storage", return_value=mock_storage):
            resp = client.post(
                "/api/v1/admin/branding/logo",
                content_type="multipart/form-data",
                data=data,
                headers=admin_headers,
            )
        assert resp.status_code == 200
        key = resp.get_json()["data"]["key"]
        assert key.endswith(".jpeg")


# ---------------------------------------------------------------------------
# GET /api/v1/admin/branding/tenants — superadmin only
# ---------------------------------------------------------------------------

class TestListTenantsBranding:

    def test_without_token_returns_401(self, client):
        resp = client.get("/api/v1/admin/branding/tenants")
        assert resp.status_code == 401

    def test_admin_role_returns_403(self, client, admin_headers):
        resp = client.get("/api/v1/admin/branding/tenants", headers=admin_headers)
        assert resp.status_code == 403

    def test_superadmin_gets_tenant_list(self, client, superadmin_headers):
        rows = [
            {"id": TENANT_ID, "name": "Tenant A", "slug": "tenant-a",
             "is_active": True, "branding": {"brand": {"name": "A"}}},
        ]
        mock_pool = _make_pool(rows=rows)
        with patch(_POOL_PATH) as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            resp = client.get("/api/v1/admin/branding/tenants", headers=superadmin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]["tenants"]) == 1
        assert data["data"]["tenants"][0]["name"] == "Tenant A"


# ---------------------------------------------------------------------------
# task-048: Public endpoint — GET /api/v1/tenant/branding (admin.branding_routes)
# ---------------------------------------------------------------------------

def _make_app():
    """Create minimal Flask test app with branding blueprints."""
    from app import create_app
    app = create_app("testing")
    return app


class TestGetTenantBrandingPublic:
    def test_no_tenant_id_returns_defaults(self):
        app = _make_app()
        with app.test_client() as c:
            r = c.get("/api/v1/tenant/branding")
            data = r.get_json()
            assert r.status_code == 200
            assert data["success"] is True
            assert data["data"]["is_default"] is True
            assert data["data"]["branding"]["product_name"] == "Recognition"

    def test_unknown_tenant_returns_defaults(self):
        app = _make_app()
        with app.test_client() as c:
            r = c.get("/api/v1/tenant/branding?tenant_id=00000000-0000-0000-0000-000000000099")
            data = r.get_json()
            assert r.status_code == 200
            assert data["data"]["is_default"] is True

    @patch("app.api.v1.admin.branding_routes._pool")
    def test_db_error_returns_defaults(self, mock_pool):
        mock_pool.side_effect = RuntimeError("db down")
        app = _make_app()
        with app.test_client() as c:
            r = c.get("/api/v1/tenant/branding?tenant_id=any-id")
            data = r.get_json()
            assert r.status_code == 200
            assert data["data"]["is_default"] is True

    @patch("app.api.v1.admin.branding_routes._pool")
    def test_returns_tenant_branding(self, mock_pool):
        stored = {"product_name": "CATH Vision", "color_primary": "#2563eb"}
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = {"branding": stored}
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cur
        mock_pool.return_value.get_connection.return_value = conn

        app = _make_app()
        with app.test_client() as c:
            r = c.get("/api/v1/tenant/branding?tenant_id=some-uuid")
            data = r.get_json()
            assert r.status_code == 200
            assert data["data"]["branding"]["product_name"] == "CATH Vision"
            assert data["data"]["branding"]["color_primary"] == "#2563eb"
            assert data["data"]["is_default"] is False

    @patch("app.api.v1.admin.branding_routes._pool")
    def test_empty_branding_jsonb_is_default(self, mock_pool):
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = {"branding": {}}
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cur
        mock_pool.return_value.get_connection.return_value = conn

        app = _make_app()
        with app.test_client() as c:
            r = c.get("/api/v1/tenant/branding?tenant_id=some-uuid")
            data = r.get_json()
            assert data["data"]["is_default"] is True


# ---------------------------------------------------------------------------
# task-048: _merge_branding helper
# ---------------------------------------------------------------------------

class TestMergeBranding:
    def test_empty_stored_returns_defaults(self):
        from app.api.v1.admin.branding_routes import _merge_branding, _DEFAULT_BRANDING
        result = _merge_branding({})
        assert result == _DEFAULT_BRANDING

    def test_partial_override(self):
        from app.api.v1.admin.branding_routes import _merge_branding
        result = _merge_branding({"product_name": "MyApp", "color_primary": "#ff0000"})
        assert result["product_name"] == "MyApp"
        assert result["color_primary"] == "#ff0000"
        assert result["color_secondary"] == "#ea580c"  # unchanged default

    def test_none_values_fall_back_to_defaults(self):
        from app.api.v1.admin.branding_routes import _merge_branding
        result = _merge_branding({"product_name": None, "color_primary": "#ff0000"})
        assert result["product_name"] == "Recognition"
        assert result["color_primary"] == "#ff0000"
