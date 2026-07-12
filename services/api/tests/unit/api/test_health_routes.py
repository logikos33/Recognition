"""Tests: health/routes.py — /health and /api/v1/health/metrics endpoints."""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


TENANT_ID = str(uuid4())
USER_ID = str(uuid4())

_POOL_PATH = "app.infrastructure.database.connection"


@pytest.fixture
def auth_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "email": "test@test.com",
                "role": "admin",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealthCheck:

    def test_returns_json(self, client):
        resp = client.get("/health")
        assert resp.is_json

    def test_no_db_no_redis_returns_503(self, client):
        resp = client.get("/health")
        assert resp.status_code == 503

    def test_response_has_checks_key(self, client):
        resp = client.get("/health")
        data = resp.get_json()
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]

    def test_database_false_triggers_degraded(self, client):
        resp = client.get("/health")
        data = resp.get_json()
        assert data["status"] == "degraded"

    def test_both_healthy_returns_200(self, client):
        def _make_pool():
            mock_cur = MagicMock()
            mock_cur.__enter__ = lambda s: mock_cur
            mock_cur.__exit__ = MagicMock(return_value=False)

            @contextmanager
            def _conn_ctx():
                mock_conn = MagicMock()
                mock_conn.cursor.return_value = mock_cur
                yield mock_conn

            mock_pool = MagicMock()
            mock_pool.get_connection.side_effect = _conn_ctx
            return mock_pool

        mock_redis_mod = MagicMock()
        mock_redis_client = MagicMock()
        mock_redis_mod.from_url.return_value = mock_redis_client

        import sys
        with patch(f"{_POOL_PATH}.DatabasePool") as mock_pool_cls, \
             patch.dict(sys.modules, {"redis": mock_redis_mod}), \
             patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
            mock_pool_cls.get_instance.return_value = _make_pool()
            resp = client.get("/health")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"


# ---------------------------------------------------------------------------
# _check_database helper
# ---------------------------------------------------------------------------

class TestCheckDatabase:

    def test_pool_none_returns_false(self):
        from app.api.v1.health.routes import _check_database
        with patch(f"{_POOL_PATH}.DatabasePool") as mock_cls:
            mock_cls.get_instance.return_value = None
            assert _check_database() is False

    def test_db_exception_returns_false(self):
        from app.api.v1.health.routes import _check_database
        with patch(f"{_POOL_PATH}.DatabasePool") as mock_cls:
            mock_cls.get_instance.side_effect = Exception("connection refused")
            assert _check_database() is False

    def test_successful_query_returns_true(self):
        from app.api.v1.health.routes import _check_database

        @contextmanager
        def _conn_ctx():
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conn.cursor.return_value = mock_cur
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _conn_ctx

        with patch(f"{_POOL_PATH}.DatabasePool") as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            assert _check_database() is True


# ---------------------------------------------------------------------------
# _check_redis helper
# ---------------------------------------------------------------------------

class TestCheckRedis:

    def test_no_redis_url_returns_false(self):
        from app.api.v1.health.routes import _check_redis
        import os
        with patch.dict(os.environ, {"REDIS_URL": ""}):
            assert _check_redis() is False

    def test_redis_exception_returns_false(self):
        from app.api.v1.health.routes import _check_redis
        import sys
        mock_redis = MagicMock()
        mock_redis.from_url.side_effect = Exception("redis down")
        with patch.dict(sys.modules, {"redis": mock_redis}), \
             patch.dict("os.environ", {"REDIS_URL": "redis://localhost"}):
            assert _check_redis() is False

    def test_ping_success_returns_true(self):
        from app.api.v1.health.routes import _check_redis
        import sys
        mock_redis = MagicMock()
        mock_client = MagicMock()
        mock_redis.from_url.return_value = mock_client
        with patch.dict(sys.modules, {"redis": mock_redis}), \
             patch.dict("os.environ", {"REDIS_URL": "redis://localhost"}):
            assert _check_redis() is True


# ---------------------------------------------------------------------------
# _count_active_cameras helper
# ---------------------------------------------------------------------------

class TestCountActiveCameras:

    def test_invalid_schema_returns_zero(self):
        from app.api.v1.health.routes import _count_active_cameras
        assert _count_active_cameras("invalid; DROP TABLE") == 0

    def test_pool_none_returns_zero(self):
        from app.api.v1.health.routes import _count_active_cameras
        with patch(f"{_POOL_PATH}.DatabasePool") as mock_cls:
            mock_cls.get_instance.return_value = None
            assert _count_active_cameras("public") == 0

    def test_db_exception_returns_zero(self):
        from app.api.v1.health.routes import _count_active_cameras
        with patch(f"{_POOL_PATH}.DatabasePool") as mock_cls:
            mock_cls.get_instance.side_effect = Exception("DB error")
            assert _count_active_cameras("public") == 0

    def test_valid_schema_returns_count(self):
        from app.api.v1.health.routes import _count_active_cameras

        @contextmanager
        def _conn_ctx():
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {"count": 5}
            mock_conn.cursor.return_value = mock_cur
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _conn_ctx

        with patch(f"{_POOL_PATH}.DatabasePool") as mock_cls:
            mock_cls.get_instance.return_value = mock_pool
            assert _count_active_cameras("tenant_abc") == 5

    def test_schema_starting_with_digit_returns_zero(self):
        from app.api.v1.health.routes import _count_active_cameras
        assert _count_active_cameras("1invalid") == 0


# ---------------------------------------------------------------------------
# GET /api/v1/health/metrics — JWT-protected
# ---------------------------------------------------------------------------

class TestHealthMetrics:

    def test_without_token_returns_401(self, client):
        resp = client.get("/api/v1/health/metrics")
        assert resp.status_code == 401

    def test_with_token_returns_200(self, client, auth_headers):
        with patch(f"{_POOL_PATH}.DatabasePool") as mock_cls:
            mock_cls.get_instance.return_value = None
            resp = client.get("/api/v1/health/metrics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "database" in data
        assert "redis" in data
        assert "cameras_active" in data
