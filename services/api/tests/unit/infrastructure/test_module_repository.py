"""
Tests: ModuleRepository — all 5 methods.
"""
from contextlib import contextmanager

from unittest.mock import MagicMock

from app.infrastructure.database.repositories.module_repository import ModuleRepository


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
    return ModuleRepository(_pool_with_cursor(cur)), cur


class TestGetByTenant:

    def test_returns_modules(self):
        cur = MagicMock()
        cur.fetchall.return_value = [
            {"module_code": "epi", "enabled": True},
            {"module_code": "fueling", "enabled": False},
        ]
        repo, _ = _repo(cur)
        result = repo.get_by_tenant("tenant-1")
        assert len(result) == 2

    def test_tenant_id_in_params(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_by_tenant("tenant-abc")
        params = cur.execute.call_args[0][1]
        assert "tenant-abc" in params

    def test_empty_tenant_returns_empty_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, _ = _repo(cur)
        assert repo.get_by_tenant("nobody") == []


class TestGetTenantModule:

    def test_returns_module_when_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"module_code": "epi", "enabled": True}
        repo, _ = _repo(cur)
        result = repo.get_tenant_module("tenant-1", "epi")
        assert result["enabled"] is True

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_tenant_module("tenant-1", "missing") is None

    def test_both_params_in_query(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.get_tenant_module("tenant-x", "fueling")
        params = cur.execute.call_args[0][1]
        assert "tenant-x" in params
        assert "fueling" in params


class TestGetClasses:

    def test_returns_class_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [
            {"class_id": 0, "name": "helmet", "is_active": True},
            {"class_id": 1, "name": "no_helmet", "is_active": True},
        ]
        repo, _ = _repo(cur)
        result = repo.get_classes("epi")
        assert len(result) == 2
        assert result[0]["name"] == "helmet"

    def test_module_code_in_params(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_classes("fueling")
        params = cur.execute.call_args[0][1]
        assert "fueling" in params


class TestUpsertTenantModule:

    def test_returns_created_or_updated_row(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"tenant_id": "t-1", "module_code": "epi", "enabled": True}
        repo, _ = _repo(cur)
        result = repo.upsert_tenant_module("t-1", "epi")
        assert result["enabled"] is True

    def test_params_contain_tenant_and_module(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"tenant_id": "t-2", "module_code": "fueling"}
        repo, cur = _repo(cur)
        repo.upsert_tenant_module("t-2", "fueling")
        params = cur.execute.call_args[0][1]
        assert "t-2" in params
        assert "fueling" in params

    def test_conflict_resolution_in_query(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.upsert_tenant_module("t", "epi")
        query = cur.execute.call_args[0][0]
        assert "ON CONFLICT" in query
        assert "enabled = true" in query.lower() or "enabled=true" in query.lower().replace(" ", "")


class TestToggleClassActive:

    def test_activates_class(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "cls-1", "is_active": True}
        repo, _ = _repo(cur)
        result = repo.toggle_class_active("cls-1", True)
        assert result["is_active"] is True

    def test_deactivates_class(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "cls-1", "is_active": False}
        repo, _ = _repo(cur)
        result = repo.toggle_class_active("cls-1", False)
        assert result["is_active"] is False

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.toggle_class_active("bad-id", True) is None

    def test_class_id_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.toggle_class_active("cls-99", False)
        params = cur.execute.call_args[0][1]
        assert "cls-99" in params
