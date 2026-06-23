"""Tests: streams/routes.py — Celery worker status (public endpoint, no JWT)."""
import os
import sys
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# GET /api/streams/status
# ---------------------------------------------------------------------------

class TestStreamsStatus:

    def test_no_redis_url_returns_redis_unavailable(self, client):
        env = {k: v for k, v in os.environ.items() if k != "REDIS_URL"}
        env["REDIS_URL"] = ""
        with patch.dict("os.environ", env, clear=True):
            resp = client.get("/api/streams/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "redis_unavailable"
        assert data["workers"] == []

    def test_missing_redis_url_returns_redis_unavailable(self, client):
        env = {k: v for k, v in os.environ.items() if k != "REDIS_URL"}
        with patch.dict("os.environ", env, clear=True):
            resp = client.get("/api/streams/status")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "redis_unavailable"

    def test_with_online_workers_returns_ok(self, client):
        mock_celery_mod = MagicMock()
        inspector = MagicMock()
        inspector.active.return_value = {
            "worker@host1": [{"id": "task-abc", "name": "inference.run"}],
        }
        inspector.stats.return_value = {
            "worker@host1": {"pool": {"implementation": "prefork"}},
        }
        mock_celery_mod.celery.control.inspect.return_value = inspector

        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379"}, clear=False), \
             patch.dict(sys.modules, {"app.infrastructure.queue.celery_app": mock_celery_mod}):
            resp = client.get("/api/streams/status")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert len(data["workers"]) == 1
        worker = data["workers"][0]
        assert worker["worker_id"] == "worker@host1"
        assert worker["status"] == "online"
        assert worker["active_tasks"] == 1
        assert worker["pool"] == "prefork"

    def test_no_active_workers_returns_empty_list(self, client):
        mock_celery_mod = MagicMock()
        inspector = MagicMock()
        inspector.active.return_value = {}
        inspector.stats.return_value = {}
        mock_celery_mod.celery.control.inspect.return_value = inspector

        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379"}, clear=False), \
             patch.dict(sys.modules, {"app.infrastructure.queue.celery_app": mock_celery_mod}):
            resp = client.get("/api/streams/status")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["workers"] == []

    def test_inspect_returns_none_treated_as_empty(self, client):
        mock_celery_mod = MagicMock()
        inspector = MagicMock()
        inspector.active.return_value = None
        inspector.stats.return_value = None
        mock_celery_mod.celery.control.inspect.return_value = inspector

        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379"}, clear=False), \
             patch.dict(sys.modules, {"app.infrastructure.queue.celery_app": mock_celery_mod}):
            resp = client.get("/api/streams/status")

        assert resp.status_code == 200
        assert resp.get_json()["workers"] == []

    def test_celery_exception_returns_status_error(self, client):
        mock_celery_mod = MagicMock()
        mock_celery_mod.celery.control.inspect.side_effect = Exception("Connection refused")

        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379"}, clear=False), \
             patch.dict(sys.modules, {"app.infrastructure.queue.celery_app": mock_celery_mod}):
            resp = client.get("/api/streams/status")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "error"
        assert data["workers"] == []

    def test_worker_with_no_active_tasks_shows_zero(self, client):
        mock_celery_mod = MagicMock()
        inspector = MagicMock()
        inspector.active.return_value = {"worker@host1": []}
        inspector.stats.return_value = {
            "worker@host1": {"pool": {"implementation": "gevent"}},
        }
        mock_celery_mod.celery.control.inspect.return_value = inspector

        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379"}, clear=False), \
             patch.dict(sys.modules, {"app.infrastructure.queue.celery_app": mock_celery_mod}):
            resp = client.get("/api/streams/status")

        worker = resp.get_json()["workers"][0]
        assert worker["active_tasks"] == 0
        assert worker["pool"] == "gevent"
