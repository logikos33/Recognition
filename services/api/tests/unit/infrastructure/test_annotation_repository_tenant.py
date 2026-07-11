"""
Tests: AnnotationRepository — yolo_classes tenant-scoped (migration 093).
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.annotation_repository import AnnotationRepository


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
    return AnnotationRepository(_pool_with_cursor(cur)), cur


class TestCreateClassTenantScoped:
    def test_legacy_call_derives_tenant_from_user(self):
        """Retrocompat: sem tenant_id → subquery em users (mesmo backfill 093)."""
        uid = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 1, "name": "Capacete"}
        repo, cur = _repo(cur)
        result = repo.create_class(uid, "Capacete", "#22c55e")
        assert result["name"] == "Capacete"
        query, params = cur.execute.call_args[0]
        assert "tenant_id" in query
        assert "module_code" in query
        assert "(SELECT tenant_id FROM users WHERE id = %s)" in query
        assert params[3] is None          # tenant_id não fornecido
        assert params[4] == str(uid)      # subquery
        assert params[5] is None          # module_code → COALESCE 'epi'

    def test_explicit_tenant_and_module(self):
        tenant = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 2}
        repo, cur = _repo(cur)
        repo.create_class(uuid4(), "Bico", "#f00", tenant_id=tenant, module_code="fueling")
        params = cur.execute.call_args[0][1]
        assert params[3] == str(tenant)
        assert params[5] == "fueling"


class TestGetClassesForTenant:
    def test_tenant_with_user_fallback(self):
        """Fallback p/ linhas legadas: tenant_id IS NULL AND user_id = dono."""
        tenant = str(uuid4())
        uid = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": 1, "name": "Capacete"}]
        repo, cur = _repo(cur)
        result = repo.get_classes_for_tenant(tenant, user_id=uid)
        assert len(result) == 1
        query, params = cur.execute.call_args[0]
        assert "tenant_id = %s OR (tenant_id IS NULL AND user_id = %s)" in query
        assert "module_code = %s" in query
        assert params == (tenant, str(uid), "epi")

    def test_tenant_only_no_fallback(self):
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_classes_for_tenant(tenant, module_code="fueling")
        query, params = cur.execute.call_args[0]
        assert "user_id" not in query
        assert params == (tenant, "fueling")

    def test_legacy_get_classes_by_user_untouched(self):
        uid = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": 1}]
        repo, cur = _repo(cur)
        repo.get_classes_by_user(uid)
        query, params = cur.execute.call_args[0]
        assert "WHERE user_id = %s" in query
        assert params == (str(uid),)
