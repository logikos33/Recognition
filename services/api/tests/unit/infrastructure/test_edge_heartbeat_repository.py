"""
Tests: EdgeHeartbeatRepository — all methods.

recognition_shared.heartbeat.Heartbeat is stubbed via sys.modules.
"""
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4


# Stub recognition_shared.heartbeat before importing the repository
_heartbeat_mod = MagicMock()


class _HeartbeatStatus:
    healthy = "healthy"
    degraded = "degraded"
    offline = "offline"


_FakeHeartbeat = MagicMock
_heartbeat_mod.Heartbeat = _FakeHeartbeat
_heartbeat_mod.HeartbeatStatus = _HeartbeatStatus
sys.modules["recognition_shared"] = MagicMock()
sys.modules["recognition_shared.heartbeat"] = _heartbeat_mod
# Stub every submodule imported by app/api/v1/edge/routes.py and app/core/device_auth.py
# so that create_app() in other test files' fixtures can import the edge blueprint cleanly.
sys.modules["recognition_shared.device"] = MagicMock()
sys.modules["recognition_shared.enums"] = MagicMock()

from app.infrastructure.database.repositories.edge_heartbeat_repository import (  # noqa: E402
    EdgeHeartbeatRepository,
)


def _make_heartbeat(**kwargs):
    hb = MagicMock()
    hb.cpu_pct = kwargs.get("cpu_pct", 45.0)
    hb.mem_pct = kwargs.get("mem_pct", 60.0)
    hb.gpu_pct = kwargs.get("gpu_pct", None)
    hb.gpu_mem_pct = kwargs.get("gpu_mem_pct", None)
    hb.disk_pct = kwargs.get("disk_pct", 30.0)
    hb.inference_fps = kwargs.get("inference_fps", 5.0)
    hb.inference_latency_ms = kwargs.get("inference_latency_ms", 200.0)
    hb.cameras_online = kwargs.get("cameras_online", 3)
    hb.cameras_total = kwargs.get("cameras_total", 4)
    hb.queue_depth = kwargs.get("queue_depth", 0)
    hb.upload_kbps = kwargs.get("upload_kbps", 100.0)
    hb.download_kbps = kwargs.get("download_kbps", 50.0)
    hb.status = MagicMock()
    hb.status.value = kwargs.get("status", "healthy")
    hb.last_error = kwargs.get("last_error", None)
    hb.edge_version = kwargs.get("edge_version", "1.0.0")
    return hb


def _pool_with_cursor(mock_cursor):
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


def _repo(mock_cursor=None):
    cur = mock_cursor or MagicMock()
    return EdgeHeartbeatRepository(_pool_with_cursor(cur)), cur


class TestGetDeviceByDeviceId:

    def test_returns_device_when_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "d-1", "device_id": "dev-abc", "revoked": False}
        repo, _ = _repo(cur)
        result = repo.get_device_by_device_id("dev-abc")
        assert result["device_id"] == "dev-abc"

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_device_by_device_id("bad-id") is None

    def test_device_id_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.get_device_by_device_id("my-device-99")
        params = cur.execute.call_args[0][1]
        assert "my-device-99" in params


class TestInsertHeartbeat:

    def test_returns_row_with_id_and_received_at(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "hb-1", "received_at": datetime.now(timezone.utc)}
        repo, _ = _repo(cur)
        hb = _make_heartbeat()
        result = repo.insert_heartbeat(uuid4(), uuid4(), "dev-1", hb)
        assert result["id"] == "hb-1"

    def test_none_fields_passed_as_none(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "hb-2", "received_at": None}
        repo, cur = _repo(cur)
        hb = _make_heartbeat(gpu_pct=None, gpu_mem_pct=None, inference_fps=None)
        repo.insert_heartbeat(uuid4(), uuid4(), "dev-1", hb)
        params = cur.execute.call_args[0][1]
        # gpu_pct should be None (index 6 in the param tuple)
        assert params[5] is None  # gpu_pct
        assert params[6] is None  # gpu_mem_pct

    def test_status_value_used(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "hb-3", "received_at": None}
        repo, cur = _repo(cur)
        hb = _make_heartbeat(status="degraded")
        repo.insert_heartbeat(uuid4(), uuid4(), "dev-1", hb)
        params = cur.execute.call_args[0][1]
        assert "degraded" in params


class TestUpdateLastSeen:

    def test_updates_last_seen_at(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        tenant_id = uuid4()
        repo.update_last_seen("dev-1", tenant_id)
        params = cur.execute.call_args[0][1]
        assert "dev-1" in params
        assert str(tenant_id) in params


class TestGetLastHeartbeatPerSite:

    def test_returns_site_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [
            {"site_id": "s-1", "site_name": "Site A", "heartbeat_status": "healthy"},
        ]
        repo, _ = _repo(cur)
        result = repo.get_last_heartbeat_per_site("tenant-1")
        assert len(result) == 1
        assert result[0]["site_name"] == "Site A"

    def test_tenant_id_used_twice_in_params(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_last_heartbeat_per_site("tenant-x")
        params = cur.execute.call_args[0][1]
        assert params.count("tenant-x") == 2


class TestGetLastHeartbeatPerSiteWithStatus:

    def test_returns_sites_with_status(self):
        cur = MagicMock()
        cur.fetchall.return_value = [
            {"site_id": "s-1", "site_status": "active", "heartbeat_status": "healthy"},
        ]
        repo, _ = _repo(cur)
        result = repo.get_last_heartbeat_per_site_with_status("tenant-1")
        assert result[0]["site_status"] == "active"

    def test_query_includes_site_status(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_last_heartbeat_per_site_with_status("tenant-1")
        query = cur.execute.call_args[0][0]
        assert "site_status" in query or "s.status" in query


class TestSummaryForSite:

    def test_returns_aggregated_metrics(self):
        cur = MagicMock()
        cur.fetchone.return_value = {
            "heartbeat_count": 10,
            "avg_inference_fps": 4.5,
            "max_inference_fps": 5.0,
            "avg_inference_latency_ms": 210.0,
            "uptime_pct": 90.0,
            "last_received_at": datetime.now(timezone.utc),
            "last_status": "healthy",
        }
        repo, _ = _repo(cur)
        result = repo.summary_for_site("t-1", "s-1", 3600)
        assert result["heartbeat_count"] == 10
        assert result["uptime_pct"] == 90.0

    def test_returns_zero_defaults_when_no_heartbeats(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        result = repo.summary_for_site("t-1", "s-1", 3600)
        assert result["heartbeat_count"] == 0
        assert result["last_status"] is None

    def test_all_params_in_query(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"heartbeat_count": 0}
        repo, cur = _repo(cur)
        repo.summary_for_site("tenant-abc", "site-abc", 7200)
        params = cur.execute.call_args[0][1]
        assert "tenant-abc" in params
        assert "site-abc" in params


class TestListHeartbeats:

    def test_returns_heartbeats_without_cursor(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "hb-1"}, {"id": "hb-2"}]
        repo, _ = _repo(cur)
        result = repo.list_heartbeats("t-1", "s-1")
        assert len(result) == 2

    def test_returns_heartbeats_with_before_cursor(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "hb-old"}]
        repo, _ = _repo(cur)
        result = repo.list_heartbeats("t-1", "s-1", before="2026-01-01T00:00:00Z")
        assert len(result) == 1

    def test_limit_clamped_to_500(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_heartbeats("t-1", "s-1", limit=9999)
        params = cur.execute.call_args[0][1]
        assert 500 in params

    def test_limit_clamped_to_minimum_1(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_heartbeats("t-1", "s-1", limit=0)
        params = cur.execute.call_args[0][1]
        assert 1 in params

    def test_before_cursor_included_in_params_when_set(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_heartbeats("t-1", "s-1", before="2026-01-15T12:00:00Z")
        params = cur.execute.call_args[0][1]
        assert "2026-01-15T12:00:00Z" in params
