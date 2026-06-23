"""
Tests: worker_registry.py — publish_heartbeat, get_worker_status, get_worker_metrics,
route_inference_task, fallback_to_railway, _scan_redis_workers, get_all_workers_status,
_persist_worker_metrics.

All Redis calls go through `_get_redis` which is patched per-test.
"""
import json
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

# `import redis as _redis` happens at module load — stub it before import
sys.modules.setdefault("redis", MagicMock())

from app.infrastructure.queue.worker_registry import (  # noqa: E402
    _persist_worker_metrics,
    _scan_redis_workers,
    fallback_to_railway,
    get_all_workers_status,
    get_worker_metrics,
    get_worker_status,
    publish_heartbeat,
    route_inference_task,
)

_GET_REDIS = "app.infrastructure.queue.worker_registry._get_redis"
_POOL_PATH = "app.infrastructure.database.connection.DatabasePool"


# ---------------------------------------------------------------------------
# get_worker_status
# ---------------------------------------------------------------------------

class TestGetWorkerStatus:

    def test_key_present_returns_onpremise(self):
        r = MagicMock()
        r.get.return_value = '{"gpu_pct":50}'
        with patch(_GET_REDIS, return_value=r):
            assert get_worker_status("t_x") == "onpremise"

    def test_key_absent_returns_railway(self):
        r = MagicMock()
        r.get.return_value = None
        with patch(_GET_REDIS, return_value=r):
            assert get_worker_status("t_x") == "railway"

    def test_redis_error_returns_offline(self):
        with patch(_GET_REDIS, side_effect=Exception("conn refused")):
            assert get_worker_status("t_x") == "offline"


# ---------------------------------------------------------------------------
# get_worker_metrics
# ---------------------------------------------------------------------------

class TestGetWorkerMetrics:

    def test_key_present_returns_parsed_json(self):
        payload = {"gpu_pct": 42, "fps_avg": 5.5}
        r = MagicMock()
        r.get.return_value = json.dumps(payload)
        with patch(_GET_REDIS, return_value=r):
            result = get_worker_metrics("t_x")
        assert result["gpu_pct"] == 42

    def test_key_absent_returns_none(self):
        r = MagicMock()
        r.get.return_value = None
        with patch(_GET_REDIS, return_value=r):
            assert get_worker_metrics("t_x") is None

    def test_redis_error_returns_none(self):
        with patch(_GET_REDIS, side_effect=Exception("timeout")):
            assert get_worker_metrics("t_x") is None


# ---------------------------------------------------------------------------
# publish_heartbeat
# ---------------------------------------------------------------------------

class TestPublishHeartbeat:

    def test_sets_key_with_ttl(self):
        r = MagicMock()
        r.incr.return_value = 2
        with patch(_GET_REDIS, return_value=r):
            publish_heartbeat("t_x", {"gpu_pct": 70})
        r.setex.assert_called_once()
        assert "t_x" in r.setex.call_args[0][0]

    def test_first_heartbeat_sets_counter_expire(self):
        r = MagicMock()
        r.incr.return_value = 1
        with patch(_GET_REDIS, return_value=r):
            publish_heartbeat("t_x", {})
        r.expire.assert_called_once()

    def test_non_first_non_fifth_no_expire_no_persist(self):
        r = MagicMock()
        r.incr.return_value = 3
        with patch(_GET_REDIS, return_value=r), \
             patch("app.infrastructure.queue.worker_registry._persist_worker_metrics") as mp:
            publish_heartbeat("t_x", {})
        r.expire.assert_not_called()
        mp.assert_not_called()

    def test_fifth_heartbeat_triggers_persist(self):
        r = MagicMock()
        r.incr.return_value = 5
        with patch(_GET_REDIS, return_value=r), \
             patch("app.infrastructure.queue.worker_registry._persist_worker_metrics") as mp:
            publish_heartbeat("t_x", {"gpu_pct": 80})
        mp.assert_called_once_with("t_x", {"gpu_pct": 80})
        r.delete.assert_called_once()

    def test_redis_error_silently_swallowed(self):
        with patch(_GET_REDIS, side_effect=Exception("redis down")):
            publish_heartbeat("t_x", {})  # must not raise


# ---------------------------------------------------------------------------
# route_inference_task
# ---------------------------------------------------------------------------

class TestRouteInferenceTask:

    def test_onpremise_returns_schema_specific_queue(self):
        with patch("app.infrastructure.queue.worker_registry.get_worker_status",
                   return_value="onpremise"):
            assert route_inference_task("tenant_abc") == "inference_tenant_abc"

    def test_railway_returns_default_queue(self):
        with patch("app.infrastructure.queue.worker_registry.get_worker_status",
                   return_value="railway"):
            assert route_inference_task("tenant_abc") == "inference"

    def test_offline_returns_default_queue(self):
        with patch("app.infrastructure.queue.worker_registry.get_worker_status",
                   return_value="offline"):
            assert route_inference_task("tenant_abc") == "inference"


# ---------------------------------------------------------------------------
# fallback_to_railway
# ---------------------------------------------------------------------------

class TestFallbackToRailway:

    def test_publishes_and_deletes_heartbeat_key(self):
        r = MagicMock()
        with patch(_GET_REDIS, return_value=r):
            fallback_to_railway("tenant_x")
        r.publish.assert_called_once()
        channel = r.publish.call_args[0][0]
        assert "tenant_x" in channel
        r.delete.assert_called_once()

    def test_redis_error_silently_swallowed(self):
        with patch(_GET_REDIS, side_effect=Exception("redis down")):
            fallback_to_railway("tenant_x")  # must not raise


# ---------------------------------------------------------------------------
# _scan_redis_workers
# ---------------------------------------------------------------------------

class TestScanRedisWorkers:

    def test_returns_workers_from_scan(self):
        r = MagicMock()
        r.scan.return_value = (0, ["worker:heartbeat:tenant_a"])
        r.get.return_value = json.dumps({"gpu_pct": 55})
        with patch(_GET_REDIS, return_value=r):
            result = _scan_redis_workers()
        assert len(result) == 1
        assert result[0]["tenant_schema"] == "tenant_a"
        assert result[0]["status"] == "onpremise"

    def test_empty_scan_returns_empty_list(self):
        r = MagicMock()
        r.scan.return_value = (0, [])
        with patch(_GET_REDIS, return_value=r):
            assert _scan_redis_workers() == []

    def test_redis_error_returns_empty_list(self):
        with patch(_GET_REDIS, side_effect=Exception("scan failed")):
            assert _scan_redis_workers() == []


# ---------------------------------------------------------------------------
# get_all_workers_status
# ---------------------------------------------------------------------------

def _build_pool_with_rows(rows, col_names):
    """Build a mock pool whose cursor returns given rows and description."""
    mock_cursor = MagicMock()
    mock_cursor.description = [(c,) for c in col_names]
    mock_cursor.fetchall.return_value = rows

    @contextmanager
    def _cursor_ctx():
        yield mock_cursor

    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = _cursor_ctx
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


_WORKER_COLS = [
    "id", "tenant_id", "tenant_schema", "hostname", "tailscale_ip",
    "software_version", "gpu_model", "gpu_vram_gb",
    "registered_at", "last_heartbeat_at", "status", "active",
    "tenant_name", "tenant_slug",
]


class TestGetAllWorkersStatus:

    def test_pool_none_returns_empty_list(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            assert get_all_workers_status() == []

    def test_db_exception_falls_back_to_scan(self):
        with patch(_POOL_PATH) as pool_cls, \
             patch("app.infrastructure.queue.worker_registry._scan_redis_workers",
                   return_value=[{"tenant_schema": "t_a", "status": "onpremise"}]) as mock_scan:
            pool_cls.get_instance.side_effect = Exception("DB down")
            result = get_all_workers_status()
        mock_scan.assert_called_once()
        assert len(result) == 1

    def test_returns_workers_with_live_status_and_metrics(self):
        wid = str(uuid4())
        tid = str(uuid4())
        row = (wid, tid, "tenant_a", "host-1", None, "1.0", "RTX4090", 24,
               None, None, "online", True, "Tenant A", "tenant_a")
        mock_pool = _build_pool_with_rows([row], _WORKER_COLS)

        with patch(_POOL_PATH) as pool_cls, \
             patch("app.infrastructure.queue.worker_registry.get_worker_status",
                   return_value="onpremise"), \
             patch("app.infrastructure.queue.worker_registry.get_worker_metrics",
                   return_value={"gpu_pct": 60}):
            pool_cls.get_instance.return_value = mock_pool
            result = get_all_workers_status()

        assert len(result) == 1
        w = result[0]
        assert w["status"] == "onpremise"
        assert w["live_metrics"] == {"gpu_pct": 60}
        assert w["tenant_schema"] == "tenant_a"


# ---------------------------------------------------------------------------
# _persist_worker_metrics
# ---------------------------------------------------------------------------

class TestPersistWorkerMetrics:

    def test_pool_none_returns_early(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            _persist_worker_metrics("t_x", {})  # must not raise

    def test_exception_silently_swallowed(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.side_effect = Exception("DB crash")
            _persist_worker_metrics("t_x", {})  # must not raise

    def test_existing_worker_inserts_metrics(self):
        worker_id = str(uuid4())

        mock_cursor = MagicMock()
        # First fetchone returns worker row; subsequent calls return worker_id row
        mock_cursor.fetchone.side_effect = [
            (worker_id,),   # SELECT id FROM worker_registry
        ]

        @contextmanager
        def _cursor_ctx():
            yield mock_cursor

        @contextmanager
        def _conn_ctx():
            mock_conn = MagicMock()
            mock_conn.cursor.side_effect = _cursor_ctx
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _conn_ctx

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            _persist_worker_metrics("t_x", {"gpu_pct": 90, "fps_avg": 4.0})

        # Should have called execute at least 3 times: SELECT worker, INSERT metrics, UPDATE registry
        assert mock_cursor.execute.call_count >= 3

    def test_new_worker_auto_registered_then_metrics_inserted(self):
        tenant_id = str(uuid4())
        worker_id = str(uuid4())

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            None,            # no existing worker
            (tenant_id,),    # tenant found
            (worker_id,),    # INSERT RETURNING id
        ]

        @contextmanager
        def _cursor_ctx():
            yield mock_cursor

        @contextmanager
        def _conn_ctx():
            mock_conn = MagicMock()
            mock_conn.cursor.side_effect = _cursor_ctx
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _conn_ctx

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            _persist_worker_metrics("t_new", {"hostname": "gpu-box"})

        # At minimum: SELECT worker, SELECT tenant, INSERT worker, INSERT metrics, UPDATE
        assert mock_cursor.execute.call_count >= 5

    def test_new_worker_tenant_not_found_returns_early(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            None,   # no existing worker
            None,   # tenant not found
        ]

        @contextmanager
        def _cursor_ctx():
            yield mock_cursor

        @contextmanager
        def _conn_ctx():
            mock_conn = MagicMock()
            mock_conn.cursor.side_effect = _cursor_ctx
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _conn_ctx

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            _persist_worker_metrics("unknown_tenant", {})
        # No crash — returned early after tenant not found
