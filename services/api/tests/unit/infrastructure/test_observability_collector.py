"""Tests: tasks/observability.py — coletor de snapshots (WS11/E2-6)."""
import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from app.infrastructure.queue.tasks.observability import (
    _api_delta_points,
    _dynamic_inference_queues,
    _oldest_item_age_seconds,
    _queue_points,
    collect_platform_metrics,
    prune_old_metrics,
)

_MOD = "app.infrastructure.queue.tasks.observability"


def _make_pool(rows_by_call=None):
    """Pool mock: cursor.fetchone devolve dicts (RealDictRow simulado)."""
    cursor = MagicMock()
    if rows_by_call:
        cursor.fetchone.side_effect = rows_by_call
    cursor.fetchall.return_value = []

    @contextmanager
    def _conn_ctx():
        conn = MagicMock()
        conn.cursor.return_value = cursor
        yield conn

    pool = MagicMock()
    pool.get_connection.side_effect = _conn_ctx
    return pool, cursor


class TestDynamicQueues:
    def test_discovers_inference_queues_from_heartbeats(self):
        r = MagicMock()
        r.scan.return_value = (0, ["worker:heartbeat:rvb", "worker:heartbeat:acme"])
        assert _dynamic_inference_queues(r) == ["inference_rvb", "inference_acme"]

    def test_empty_scan(self):
        r = MagicMock()
        r.scan.return_value = (0, [])
        assert _dynamic_inference_queues(r) == []


class TestOldestItemAge:
    def test_empty_queue_returns_none(self):
        r = MagicMock()
        r.lindex.return_value = None
        assert _oldest_item_age_seconds(r, "inference") is None

    def test_unparseable_envelope_returns_none(self):
        r = MagicMock()
        r.lindex.return_value = json.dumps({"headers": {}, "properties": {}})
        assert _oldest_item_age_seconds(r, "inference") is None

    def test_numeric_timestamp_parsed(self):
        import time as _time
        r = MagicMock()
        r.lindex.return_value = json.dumps(
            {"headers": {"timestamp": _time.time() - 120}}
        )
        age = _oldest_item_age_seconds(r, "inference")
        assert age is not None
        assert 100 <= age <= 200

    def test_garbage_returns_none(self):
        r = MagicMock()
        r.lindex.return_value = "not-json"
        assert _oldest_item_age_seconds(r, "inference") is None


class TestQueuePoints:
    def test_depth_and_stats_points(self):
        r = MagicMock()
        r.llen.return_value = 3
        r.lindex.return_value = None
        r.hgetall.return_value = {"ok": "10", "fail": "2"}
        points = _queue_points(r, ["inference"])
        metrics = {p["metric"] for p in points}
        assert "queue_depth" in metrics
        assert "task_fail_day" in metrics
        assert "task_ok_day" in metrics
        depth = next(p for p in points if p["metric"] == "queue_depth")
        assert depth["value"] == 3
        assert depth["labels"] == {"queue": "inference"}


class TestApiDeltaPoints:
    def test_delta_within_same_hour(self):
        # current_hour_snapshot/_hour_key são importados DENTRO da função —
        # o patch precisa ser no módulo app.core.request_metrics.
        r = MagicMock()
        snap = {"count": 100, "err_4xx": 5, "err_5xx": 2, "dur_ms_sum": 4000}
        with patch(
            "app.core.request_metrics.current_hour_snapshot", return_value=snap
        ), patch("app.core.request_metrics._hour_key", return_value="apimetrics:x"):
            r.get.return_value = json.dumps(
                {"hour": "apimetrics:x", "count": 60, "err_4xx": 1,
                 "err_5xx": 0, "dur_ms_sum": 1000}
            )
            points = _api_delta_points(r)
        by_metric = {p["metric"]: p["value"] for p in points}
        assert by_metric["http_count"] == 40
        assert by_metric["http_4xx"] == 4
        assert by_metric["http_5xx"] == 2
        assert by_metric["http_avg_ms"] == 75.0

    def test_first_cycle_uses_absolute(self):
        r = MagicMock()
        r.get.return_value = None
        snap = {"count": 10, "err_4xx": 0, "err_5xx": 1, "dur_ms_sum": 500}
        with patch(
            "app.core.request_metrics.current_hour_snapshot", return_value=snap
        ), patch("app.core.request_metrics._hour_key", return_value="apimetrics:y"):
            points = _api_delta_points(r)
        by_metric = {p["metric"]: p["value"] for p in points}
        assert by_metric["http_count"] == 10
        assert by_metric["http_5xx"] == 1


class TestCollect:
    def test_no_pool_returns_zero(self):
        with patch(f"{_MOD}._get_repo", return_value=None):
            assert collect_platform_metrics() == 0

    def test_redis_down_still_collects_db_and_edge(self):
        repo = MagicMock()
        repo.insert_points.side_effect = lambda pts: len(pts)
        with patch(f"{_MOD}._get_repo", return_value=repo), \
             patch(f"{_MOD}._get_redis", side_effect=Exception("down")), \
             patch(f"{_MOD}._db_connection_points",
                   return_value=[{"scope": "db", "metric": "conn_active", "value": 1}]), \
             patch(f"{_MOD}._edge_fleet_points",
                   return_value=[{"scope": "edge", "metric": "sites_offline", "value": 0}]):
            n = collect_platform_metrics()
        assert n == 2
        repo.insert_points.assert_called_once()

    def test_full_cycle_inserts_points(self):
        repo = MagicMock()
        repo.insert_points.side_effect = lambda pts: len(pts)
        r = MagicMock()
        r.scan.return_value = (0, [])
        r.llen.return_value = 0
        r.lindex.return_value = None
        r.hgetall.return_value = {}
        r.info.return_value = {"used_memory": 1048576, "connected_clients": 4}
        r.get.return_value = None
        with patch(f"{_MOD}._get_repo", return_value=repo), \
             patch(f"{_MOD}._get_redis", return_value=r), \
             patch(f"{_MOD}._db_connection_points", return_value=[]), \
             patch(f"{_MOD}._edge_fleet_points", return_value=[]), \
             patch("app.core.request_metrics.current_hour_snapshot",
                   return_value={"count": 0, "err_4xx": 0, "err_5xx": 0, "dur_ms_sum": 0}):
            n = collect_platform_metrics()
        assert n > 0
        scopes = {p["scope"] for p in repo.insert_points.call_args[0][0]}
        assert "celery" in scopes
        assert "redis" in scopes
        assert "workers" in scopes
        assert "api" in scopes


class TestPrune:
    def test_prune_uses_env_days(self, monkeypatch):
        monkeypatch.setenv("PLATFORM_METRICS_RETENTION_DAYS", "7")
        repo = MagicMock()
        repo.prune_older_than.return_value = 42
        with patch(f"{_MOD}._get_repo", return_value=repo):
            assert prune_old_metrics() == 42
        repo.prune_older_than.assert_called_once_with(7)

    def test_prune_invalid_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("PLATFORM_METRICS_RETENTION_DAYS", "abc")
        repo = MagicMock()
        repo.prune_older_than.return_value = 0
        with patch(f"{_MOD}._get_repo", return_value=repo):
            prune_old_metrics()
        repo.prune_older_than.assert_called_once_with(30)

    def test_no_pool_returns_zero(self):
        with patch(f"{_MOD}._get_repo", return_value=None):
            assert prune_old_metrics() == 0
