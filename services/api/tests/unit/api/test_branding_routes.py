"""
Tests for branding routes (task-048).
"""
import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Create minimal Flask test app with branding blueprints."""
    from app import create_app
    app = create_app("testing")
    return app


# ---------------------------------------------------------------------------
# Public endpoint — GET /api/v1/tenant/branding
# ---------------------------------------------------------------------------

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
# _merge_branding helper
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
