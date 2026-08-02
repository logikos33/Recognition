"""Tests: health/routes.py — /health, /livez, /readyz, /status, /metrics."""
import sys
import time
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.api.v1.health.readiness import (
    FAILURE_THRESHOLD,
    ReadinessCache,
    ReadinessState,
    cache as readiness_cache,
)

TENANT_ID = str(uuid4())
USER_ID = str(uuid4())

_POOL_PATH = "app.infrastructure.database.connection"
_ROUTES = "app.api.v1.health.routes"


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


# ---------------------------------------------------------------------------
# GET /livez, /readyz, /status — item 2.3 (health honesto)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_readiness_cache():
    """Isola o singleton de readiness entre testes (é global ao processo)."""
    readiness_cache.reset_for_tests()
    yield
    readiness_cache.reset_for_tests()


class TestLivez:

    def test_never_touches_dependencies(self, client):
        # Mocks que EXPLODEM se chamados — prova que /livez não toca DB/Redis.
        with patch(
            f"{_ROUTES}._check_database",
            side_effect=AssertionError("livez não deveria tocar o banco"),
        ), patch(
            f"{_ROUTES}._check_redis",
            side_effect=AssertionError("livez não deveria tocar redis"),
        ):
            resp = client.get("/livez")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "alive"
        assert "uptime_seconds" in data


class TestReadyz:

    def test_503_storage_local_without_ephemeral_flag(self, client, monkeypatch):
        monkeypatch.delenv("R2_ENDPOINT", raising=False)
        monkeypatch.delenv("R2_KEY", raising=False)
        monkeypatch.delenv("R2_SECRET", raising=False)
        monkeypatch.delenv("ALLOW_EPHEMERAL_STORAGE", raising=False)
        monkeypatch.setenv("SERVICE_TYPE", "api")
        # Isola a falha em storage: worker_class e dependências OK.
        monkeypatch.setitem(sys.modules, "gevent", MagicMock())
        with patch(f"{_ROUTES}._check_database", return_value=True), \
             patch(f"{_ROUTES}._check_redis", return_value=True):
            resp = client.get("/readyz")

        assert resp.status_code == 503
        data = resp.get_json()
        assert data["ready"] is False
        assert data["stale"] is False
        assert data["invariants"]["storage_backend"]["ok"] is False

    def test_503_worker_sync_when_gevent_absent(self, client, monkeypatch):
        monkeypatch.setenv("SERVICE_TYPE", "api")
        # Isola a falha no worker_class: storage e dependências OK.
        monkeypatch.setenv("ALLOW_EPHEMERAL_STORAGE", "1")
        monkeypatch.delitem(sys.modules, "gevent", raising=False)
        with patch(f"{_ROUTES}._check_database", return_value=True), \
             patch(f"{_ROUTES}._check_redis", return_value=True):
            resp = client.get("/readyz")

        assert resp.status_code == 503
        data = resp.get_json()
        assert data["ready"] is False
        assert data["invariants"]["worker_class"]["ok"] is False

    def test_503_stale_when_cache_not_refreshed(self, client):
        old_state = ReadinessState(
            checked_at=time.monotonic() - 999,
            ready=True,  # cache mentiroso — staleness deve vencer (fail closed)
            invariants={
                "worker_class": {"ok": True, "detail": "x"},
                "storage_backend": {"ok": True, "detail": "y"},
            },
            dependencies={
                "database": {"ok": True, "raw_ok": True, "consecutive_failures": 0},
                "redis": {"ok": True, "raw_ok": True, "consecutive_failures": 0},
            },
        )
        readiness_cache._state = old_state

        resp = client.get("/readyz")

        assert resp.status_code == 503
        data = resp.get_json()
        assert data["stale"] is True
        assert data["ready"] is False

    def test_200_when_fresh_and_everything_ok(self, client):
        fresh_state = ReadinessState(
            checked_at=time.monotonic(),
            ready=True,
            invariants={
                "worker_class": {"ok": True, "detail": "x"},
                "storage_backend": {"ok": True, "detail": "y"},
            },
            dependencies={
                "database": {"ok": True, "raw_ok": True, "consecutive_failures": 0},
                "redis": {"ok": True, "raw_ok": True, "consecutive_failures": 0},
            },
        )
        readiness_cache._state = fresh_state

        resp = client.get("/readyz")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ready"] is True
        assert data["stale"] is False

    def test_bootstrap_on_demand_when_never_populated(self, client, monkeypatch):
        """Sem loop de fundo (TESTING), a 1a leitura computa inline (mesmo
        contrato de refresh()) — não deve derrubar com estado ausente."""
        monkeypatch.setenv("SERVICE_TYPE", "api")
        monkeypatch.setenv("ALLOW_EPHEMERAL_STORAGE", "1")
        monkeypatch.setitem(sys.modules, "gevent", MagicMock())
        with patch(f"{_ROUTES}._check_database", return_value=True), \
             patch(f"{_ROUTES}._check_redis", return_value=True):
            resp = client.get("/readyz")

        assert resp.status_code == 200
        assert resp.get_json()["ready"] is True


class TestStatus:

    def test_returns_health_plus_dependency_detail(self, client):
        with patch(f"{_ROUTES}._check_database", return_value=True), \
             patch(f"{_ROUTES}._check_redis", return_value=True):
            resp = client.get("/status")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["checks"]["database"]["ok"] is True
        assert "latency_ms" in data["checks"]["database"]
        assert "redis" in data["checks"]
        assert "readiness_cache" in data


class TestReadinessCacheBackoff:
    """Dependências transitórias só reprovam após FAILURE_THRESHOLD seguidas."""

    @staticmethod
    def _ok_invariants():
        """Isola a lógica de backoff das dependências dos invariantes de
        config — testados separadamente em TestReadyz."""
        return patch.multiple(
            ReadinessCache,
            check_worker_class=staticmethod(lambda: {"ok": True, "detail": "mock"}),
            check_storage_backend=staticmethod(lambda: {"ok": True, "detail": "mock"}),
        )

    def test_single_failure_does_not_flip_ready(self):
        rc = ReadinessCache()
        with self._ok_invariants(), \
             patch(f"{_ROUTES}._check_database", return_value=False), \
             patch(f"{_ROUTES}._check_redis", return_value=True):
            state = rc.refresh()
        assert state.dependencies["database"]["raw_ok"] is False
        assert state.dependencies["database"]["ok"] is True  # ainda não flipou
        assert state.ready is True

    def test_flips_after_threshold_consecutive_failures(self):
        rc = ReadinessCache()
        with self._ok_invariants(), \
             patch(f"{_ROUTES}._check_database", return_value=False), \
             patch(f"{_ROUTES}._check_redis", return_value=True):
            state = None
            for _ in range(FAILURE_THRESHOLD):
                state = rc.refresh()
        assert state.dependencies["database"]["ok"] is False
        assert state.ready is False

    def test_recovers_after_success(self):
        rc = ReadinessCache()
        with self._ok_invariants():
            with patch(f"{_ROUTES}._check_database", return_value=False), \
                 patch(f"{_ROUTES}._check_redis", return_value=True):
                for _ in range(FAILURE_THRESHOLD):
                    rc.refresh()
            with patch(f"{_ROUTES}._check_database", return_value=True), \
                 patch(f"{_ROUTES}._check_redis", return_value=True):
                state = rc.refresh()
        assert state.dependencies["database"]["ok"] is True
        assert state.dependencies["database"]["consecutive_failures"] == 0
