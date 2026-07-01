"""
Tests: OperationRepository — all methods.
"""
import json
from contextlib import contextmanager

from unittest.mock import MagicMock

from app.infrastructure.database.repositories.operation_repository import OperationRepository


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
    return OperationRepository(_pool_with_cursor(cur)), cur


class TestListByCamera:

    def test_returns_operations(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": 1, "name": "op1"}, {"id": 2, "name": "op2"}]
        repo, _ = _repo(cur)
        result = repo.list_by_camera("t-1", "cam-1")
        assert len(result) == 2

    def test_tenant_and_camera_in_params(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_by_camera("tenant-x", "cam-y")
        params = cur.execute.call_args[0][1]
        assert "tenant-x" in params
        assert "cam-y" in params


class TestListByCameraAndModule:

    def test_returns_filtered_operations(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": 5}]
        repo, _ = _repo(cur)
        result = repo.list_by_camera_and_module("t-1", "cam-1", "mod-1")
        assert result[0]["id"] == 5

    def test_all_three_ids_in_params(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_by_camera_and_module("t-abc", "cam-abc", "mod-abc")
        params = cur.execute.call_args[0][1]
        assert "t-abc" in params
        assert "cam-abc" in params
        assert "mod-abc" in params


class TestGetById:

    def test_returns_operation_when_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 42, "name": "my_op"}
        repo, _ = _repo(cur)
        result = repo.get_by_id("t-1", 42)
        assert result["id"] == 42

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_by_id("t-1", 999) is None

    def test_tenant_and_operation_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.get_by_id("tenant-7", 77)
        params = cur.execute.call_args[0][1]
        assert "tenant-7" in params
        assert 77 in params


class TestCreate:

    def test_returns_created_operation(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 1, "name": "count_people", "status": "pending"}
        repo, _ = _repo(cur)
        result = repo.create("t-1", "cam-1", "mod-1", "type-A", "count_people", {"threshold": 5})
        assert result["name"] == "count_people"

    def test_config_serialized_as_json(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 1}
        repo, cur = _repo(cur)
        config = {"zone": [10, 20, 30, 40]}
        repo.create("t", "cam", "mod", "type", "op", config)
        params = cur.execute.call_args[0][1]
        assert json.loads(params[5]) == config

    def test_all_required_params_present(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 1}
        repo, cur = _repo(cur)
        repo.create("tenant-1", "camera-1", "module-1", "type-1", "operation-1", {})
        params = cur.execute.call_args[0][1]
        assert "tenant-1" in params
        assert "camera-1" in params
        assert "operation-1" in params


class TestUpdate:

    def test_returns_updated_operation(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 5, "name": "new_name", "version": 2}
        repo, _ = _repo(cur)
        result = repo.update("t-1", 5, "new_name", {"k": "v"})
        assert result["version"] == 2

    def test_version_incremented_in_query(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 5}
        repo, cur = _repo(cur)
        repo.update("t-1", 5, "name", {})
        query = cur.execute.call_args[0][0]
        assert "version + 1" in query or "version+1" in query.replace(" ", "")

    def test_config_serialized(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 5}
        repo, cur = _repo(cur)
        config = {"x": 99}
        repo.update("t-1", 5, "n", config)
        params = cur.execute.call_args[0][1]
        assert json.loads(params[1]) == config


class TestDelete:

    def test_returns_rowcount(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, _ = _repo(cur)
        result = repo.delete("t-1", 10)
        assert result == 1

    def test_tenant_and_id_in_params(self):
        cur = MagicMock()
        cur.rowcount = 0
        repo, cur = _repo(cur)
        repo.delete("tenant-x", 55)
        params = cur.execute.call_args[0][1]
        assert "tenant-x" in params
        assert 55 in params


class TestCountResults:

    def test_returns_count(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"cnt": 42}
        repo, _ = _repo(cur)
        assert repo.count_results(7) == 42

    def test_no_row_returns_zero(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.count_results(7) == 0

    def test_returns_int(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"cnt": "15"}
        repo, _ = _repo(cur)
        result = repo.count_results(1)
        assert isinstance(result, int)
        assert result == 15


class TestListResults:

    def test_returns_results(self):
        cur = MagicMock()
        cur.fetchall.return_value = [
            {"id": 1, "result_json": {"x": 1}},
            {"id": 2, "result_json": {"x": 2}},
        ]
        repo, _ = _repo(cur)
        result = repo.list_results(5)
        assert len(result) == 2

    def test_operation_id_and_limit_in_params(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_results(99, limit=25)
        params = cur.execute.call_args[0][1]
        assert 99 in params
        assert 25 in params

    def test_default_limit_is_100(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_results(1)
        params = cur.execute.call_args[0][1]
        assert 100 in params


class TestUpdateLiveValue:

    def test_serializes_last_value_json(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        value = {"count": 5, "zone": "A"}
        repo.update_live_value(7, value)
        params = cur.execute.call_args[0][1]
        assert json.loads(params[0]) == value

    def test_operation_id_in_params(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.update_live_value(42, {}, status="idle")
        params = cur.execute.call_args[0][1]
        assert 42 in params
        assert "idle" in params

    def test_default_status_is_active(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.update_live_value(1, {})
        params = cur.execute.call_args[0][1]
        assert "active" in params


class TestInsertResult:

    def test_serializes_result_json(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        result_data = {"detections": 3}
        repo.insert_result(10, result_data)
        params = cur.execute.call_args[0][1]
        assert json.loads(params[1]) == result_data

    def test_operation_id_in_params(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.insert_result(99, {"x": 1})
        params = cur.execute.call_args[0][1]
        assert 99 in params
