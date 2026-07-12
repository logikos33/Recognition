"""
Tests: RecorderRepository — CRUD tenant-scoped (migration 099).
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.recorder_repository import RecorderRepository


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
    return RecorderRepository(_pool_with_cursor(cur)), cur


class TestCreate:
    def test_minimal_payload(self):
        tenant = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "name": "NVR Portaria"}
        repo, cur = _repo(cur)
        result = repo.create({
            "tenant_id": tenant, "name": "NVR Portaria", "host": "10.0.0.5",
        })
        assert result["name"] == "NVR Portaria"
        query, params = cur.execute.call_args[0]
        assert "COALESCE(%s, 'onvif')" in query   # protocol default
        assert params[0] == str(tenant)
        assert params[3] == 80                     # port default

    def test_full_payload(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        creator = uuid4()
        repo.create({
            "tenant_id": uuid4(), "name": "DVR", "host": "10.0.0.9",
            "port": 8000, "username": "admin", "password_encrypted": "gAAAA...",
            "protocol": "hikvision", "manufacturer": "hikvision",
            "channels": 16, "retention_days": 30, "created_by": creator,
        })
        params = cur.execute.call_args[0][1]
        assert params[3] == 8000
        assert params[6] == "hikvision"
        assert params[8] == 16
        assert params[10] == str(creator)


class TestReads:
    def test_get_by_id_tenant_scoped(self):
        rid = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        assert repo.get_by_id(rid, tenant) is None
        query, params = cur.execute.call_args[0]
        assert "id = %s AND tenant_id = %s" in query
        assert params == (str(rid), tenant)

    def test_list_by_tenant(self):
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "a"}, {"id": "b"}]
        repo, cur = _repo(cur)
        result = repo.list_by_tenant(tenant)
        assert len(result) == 2
        query, params = cur.execute.call_args[0]
        assert "WHERE tenant_id = %s" in query
        assert params == (tenant,)


class TestUpdate:
    def test_updates_only_allowlisted_fields(self):
        rid = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(rid), "name": "Novo"}
        repo, cur = _repo(cur)
        result = repo.update(rid, tenant, {
            "name": "Novo", "channels": 8,
            "status": "hacked",       # fora da allowlist — ignorado
            "tenant_id": "attacker",  # fora da allowlist — ignorado
        })
        assert result["name"] == "Novo"
        query, params = cur.execute.call_args[0]
        assert "name = %s" in query
        assert "channels = %s" in query
        assert "status = %s" not in query
        assert "attacker" not in params

    def test_empty_update_returns_current_row(self):
        rid = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(rid)}
        repo, cur = _repo(cur)
        result = repo.update(rid, tenant, {})
        assert result["id"] == str(rid)
        # Caiu no get_by_id (SELECT), não em UPDATE
        query = cur.execute.call_args[0][0]
        assert query.startswith("SELECT")

    def test_update_status(self):
        rid = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(rid), "status": "online"}
        repo, cur = _repo(cur)
        result = repo.update_status(rid, tenant, "online")
        assert result["status"] == "online"
        query, params = cur.execute.call_args[0]
        assert "last_tested_at = NOW()" in query
        assert params == ("online", None, str(rid), tenant)


class TestDelete:
    def test_delete_tenant_scoped(self):
        rid = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        assert repo.delete(rid, tenant) == 1
        query, params = cur.execute.call_args[0]
        assert "tenant_id = %s" in query
        assert params == (str(rid), tenant)

    def test_delete_not_found(self):
        cur = MagicMock()
        cur.rowcount = 0
        repo, _ = _repo(cur)
        assert repo.delete(uuid4(), str(uuid4())) == 0
