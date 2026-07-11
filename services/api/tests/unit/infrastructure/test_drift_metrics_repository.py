"""
Tests: DriftMetricsRepository — janelas de drift (migration 101).
"""
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.drift_metrics_repository import (
    DriftMetricsRepository,
)


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
    return DriftMetricsRepository(_pool_with_cursor(cur)), cur


_WINDOW_START = datetime(2026, 7, 10, 0, 0, tzinfo=timezone.utc)
_WINDOW_END = datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc)


class TestCreate:
    def test_create_full_window(self):
        tenant = uuid4()
        model = uuid4()
        cam = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "drift_score": 0.12}
        repo, cur = _repo(cur)
        result = repo.create({
            "tenant_id": tenant,
            "model_id": model,
            "camera_id": cam,
            "window_start": _WINDOW_START,
            "window_end": _WINDOW_END,
            "detections_count": 42,
            "avg_confidence": 0.81,
            "class_distribution": {"helmet": 0.6, "no_helmet": 0.4},
            "drift_score": 0.12,
        })
        assert result["drift_score"] == 0.12
        params = cur.execute.call_args[0][1]
        assert params[0] == str(tenant)
        assert params[1] == str(model)
        assert params[2] == str(cam)
        assert params[5] == 42
        assert json.loads(params[7]) == {"helmet": 0.6, "no_helmet": 0.4}

    def test_create_minimal_defaults_count(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create({"tenant_id": uuid4()})
        query, params = cur.execute.call_args[0]
        assert "COALESCE(%s, 0)" in query
        assert params[5] is None  # detections_count omitido → default 0


class TestReads:
    def test_list_by_model_with_limit(self):
        model = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "w2"}, {"id": "w1"}]
        repo, cur = _repo(cur)
        result = repo.list_by_model(model, tenant, limit=7)
        assert len(result) == 2
        query, params = cur.execute.call_args[0]
        assert "ORDER BY window_start DESC" in query
        assert params == (str(model), tenant, 7)

    def test_get_baseline_is_earliest_window(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "w0", "avg_confidence": 0.85}
        repo, cur = _repo(cur)
        result = repo.get_baseline(uuid4(), uuid4(), str(uuid4()))
        assert result["avg_confidence"] == 0.85
        query = cur.execute.call_args[0][0]
        assert "ORDER BY window_start ASC" in query
        assert "LIMIT 1" in query

    def test_get_latest_window(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "w9"}
        repo, cur = _repo(cur)
        repo.get_latest_window(uuid4(), uuid4(), str(uuid4()))
        query = cur.execute.call_args[0][0]
        assert "ORDER BY window_start DESC" in query

    def test_exists_for_window_true(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"found": 1}
        repo, cur = _repo(cur)
        assert repo.exists_for_window(uuid4(), uuid4(), str(uuid4()), _WINDOW_START)

    def test_exists_for_window_false(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        assert not repo.exists_for_window(uuid4(), uuid4(), str(uuid4()), _WINDOW_START)
