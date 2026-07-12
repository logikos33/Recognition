"""
Tests: AlertRepository — all methods.

All DB calls go through a mocked DatabasePool (contextmanager pattern).
"""
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from unittest.mock import MagicMock

from app.infrastructure.database.repositories.alert_repository import AlertRepository


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
    return AlertRepository(_pool_with_cursor(cur)), cur


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

class TestCreate:

    def test_returns_created_row(self):
        row = {"id": str(uuid4()), "camera_id": str(uuid4()), "confidence": 0.9}
        cur = MagicMock()
        cur.fetchone.return_value = row
        repo, _ = _repo(cur)
        result = repo.create(uuid4(), [{"class": "no_helmet"}], 0.9, "evidence/key.jpg")
        assert result["confidence"] == 0.9

    def test_violations_serialized_as_json(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        violations = [{"class": "no_helmet", "conf": 0.8}]
        repo.create(uuid4(), violations, 0.8, "k")
        params = cur.execute.call_args[0][1]
        # Second param should be JSON string
        assert json.loads(params[1]) == violations

    def test_camera_id_cast_to_str(self):
        camera_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create(camera_id, [], 0.5, "k")
        params = cur.execute.call_args[0][1]
        assert params[0] == str(camera_id)


# ---------------------------------------------------------------------------
# get_by_camera
# ---------------------------------------------------------------------------

class TestGetByCamera:

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "a"}, {"id": "b"}]
        repo, _ = _repo(cur)
        result = repo.get_by_camera(uuid4())
        assert len(result) == 2

    def test_default_limit_offset(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_by_camera(uuid4())
        params = cur.execute.call_args[0][1]
        assert 50 in params  # default limit
        assert 0 in params   # default offset

    def test_custom_limit_offset(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_by_camera(uuid4(), limit=10, offset=20)
        params = cur.execute.call_args[0][1]
        assert 10 in params
        assert 20 in params


# ---------------------------------------------------------------------------
# get_unacknowledged
# ---------------------------------------------------------------------------

class TestGetUnacknowledged:

    def test_no_camera_returns_all(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "x"}]
        repo, cur = _repo(cur)
        repo.get_unacknowledged()
        query = cur.execute.call_args[0][0]
        assert "camera_id" not in query

    def test_with_camera_filters_by_camera(self):
        cam_id = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_unacknowledged(camera_id=cam_id)
        params = cur.execute.call_args[0][1]
        assert str(cam_id) in params

    def test_acknowledged_false_in_query(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_unacknowledged()
        query = cur.execute.call_args[0][0]
        assert "acknowledged" in query.lower()


# ---------------------------------------------------------------------------
# acknowledge
# ---------------------------------------------------------------------------

class TestAcknowledge:

    def test_returns_updated_row(self):
        alert_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(alert_id), "acknowledged": True}
        repo, _ = _repo(cur)
        result = repo.acknowledge(alert_id)
        assert result["acknowledged"] is True

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.acknowledge(uuid4()) is None

    def test_sets_acknowledged_true_in_query(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.acknowledge(uuid4())
        query = cur.execute.call_args[0][0]
        assert "acknowledged = TRUE" in query or "acknowledged=TRUE" in query.replace(" ", "")


# ---------------------------------------------------------------------------
# count_by_camera
# ---------------------------------------------------------------------------

class TestCountByCamera:

    def test_returns_count(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"count": 42}
        repo, _ = _repo(cur)
        assert repo.count_by_camera(uuid4()) == 42

    def test_no_row_returns_zero(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.count_by_camera(uuid4()) == 0


# ---------------------------------------------------------------------------
# list_with_filters
# ---------------------------------------------------------------------------

class TestListWithFilters:

    def _call(self, **kwargs):
        cur = MagicMock()
        cur.fetchone.return_value = {"count": 5}
        cur.fetchall.return_value = [{"id": "a"}]
        repo, _ = _repo(cur)
        return repo.list_with_filters("tenant-1", **kwargs), cur

    def test_returns_items_and_total(self):
        result, _ = self._call()
        assert "items" in result
        assert "total" in result

    def test_total_from_count_query(self):
        result, _ = self._call()
        assert result["total"] == 5

    def test_tenant_id_in_params(self):
        _, cur = self._call()
        # Both count and items queries should have tenant-1
        all_params = [str(c) for c in cur.execute.call_args_list]
        assert any("tenant-1" in p for p in all_params)

    def test_camera_id_filter_added(self):
        _, cur = self._call(camera_id="cam-42")
        params_list = [c[0][1] for c in cur.execute.call_args_list]
        assert any("cam-42" in p for p in params_list)

    def test_start_date_filter_added(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _, cur = self._call(start_date=dt)
        params_list = [c[0][1] for c in cur.execute.call_args_list]
        assert any(dt in p for p in params_list)

    def test_end_date_filter_added(self):
        dt = datetime(2026, 12, 31, tzinfo=timezone.utc)
        _, cur = self._call(end_date=dt)
        params_list = [c[0][1] for c in cur.execute.call_args_list]
        assert any(dt in p for p in params_list)

    def test_violation_type_filter_added(self):
        _, cur = self._call(violation_type="no_helmet")
        params_list = [c[0][1] for c in cur.execute.call_args_list]
        assert any(any("no_helmet" in str(p) for p in params) for params in params_list)

    def test_acknowledged_filter_added(self):
        _, cur = self._call(acknowledged=True)
        params_list = [c[0][1] for c in cur.execute.call_args_list]
        assert any(True in p for p in params_list)

    def test_default_limit_offset(self):
        _, cur = self._call()
        # items query should have limit=20, offset=0
        params_list = [c[0][1] for c in cur.execute.call_args_list]
        assert any(20 in p for p in params_list)


# ---------------------------------------------------------------------------
# list_for_camera_scenario
# ---------------------------------------------------------------------------

class TestListForCameraScenario:

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "rule-1"}]
        repo, _ = _repo(cur)
        result = repo.list_for_camera_scenario("tenant-1", "cam-1")
        assert result == [{"id": "rule-1"}]

    def test_tenant_id_and_camera_id_in_params(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_for_camera_scenario("tenant-x", "cam-y")
        params = cur.execute.call_args[0][1]
        assert "tenant-x" in params
        assert "cam-y" in params

    def test_enabled_true_in_query(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_for_camera_scenario("t", "c")
        query = cur.execute.call_args[0][0]
        assert "enabled" in query.lower()


# ---------------------------------------------------------------------------
# count_since / count_all_since / count_by_hour
# ---------------------------------------------------------------------------

class TestCountSince:

    def test_returns_count(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"count": 7}
        repo, _ = _repo(cur)
        assert repo.count_since("t-1", "epi", datetime.now(tz=timezone.utc)) == 7

    def test_no_row_returns_zero(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.count_since("t-1", "epi", datetime.now(tz=timezone.utc)) == 0

    def test_module_code_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"count": 0}
        repo, cur = _repo(cur)
        repo.count_since("t-1", "fueling", datetime.now(tz=timezone.utc))
        params = cur.execute.call_args[0][1]
        assert "fueling" in params


class TestCountAllSince:

    def test_returns_count(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"count": 15}
        repo, _ = _repo(cur)
        assert repo.count_all_since("t-1", datetime.now(tz=timezone.utc)) == 15

    def test_no_row_returns_zero(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.count_all_since("t-1", datetime.now(tz=timezone.utc)) == 0


class TestCountByHour:

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"hour": "2026-01-01 10:00", "count": 3}]
        repo, _ = _repo(cur)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 2, tzinfo=timezone.utc)
        result = repo.count_by_hour("t-1", start, end)
        assert len(result) == 1
        assert result[0]["count"] == 3

    def test_tenant_and_dates_in_params(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 2, tzinfo=timezone.utc)
        repo.count_by_hour("tenant-99", start, end)
        params = cur.execute.call_args[0][1]
        assert "tenant-99" in params
        assert start in params
        assert end in params
