"""
Tests: AlertRepository.create — tenant_id/module_code opcionais (ajuste #8).
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

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


class TestCreateTenantScoped:
    def test_legacy_call_omits_tenant_columns(self):
        """Retrocompat: sem tenant/module → INSERT com as 4 colunas originais."""
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "confidence": 0.9}
        repo, cur = _repo(cur)
        result = repo.create(uuid4(), [{"class": "no_helmet"}], 0.9, "evidence/k.jpg")
        assert result["confidence"] == 0.9
        query, params = cur.execute.call_args[0]
        assert "tenant_id" not in query
        assert "module_code" not in query
        assert len(params) == 4

    def test_tenant_and_module_included(self):
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create(
            uuid4(), [{"class": "no_vest"}], 0.7, "evidence/k.jpg",
            tenant_id=tenant, module_code="epi",
        )
        query, params = cur.execute.call_args[0]
        assert "tenant_id" in query
        assert "module_code" in query
        assert params[4] == tenant
        assert params[5] == "epi"

    def test_tenant_only(self):
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create(uuid4(), [], 0.5, "k", tenant_id=tenant)
        query, params = cur.execute.call_args[0]
        assert "tenant_id" in query
        assert "module_code" not in query
        assert params[-1] == tenant

    def test_params_order_preserved(self):
        """Ordem dos 4 params originais preservada (contrato dos testes antigos)."""
        import json as _json
        cam = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        violations = [{"class": "no_helmet", "conf": 0.8}]
        repo.create(cam, violations, 0.8, "evidence/k.jpg", tenant_id=str(uuid4()))
        params = cur.execute.call_args[0][1]
        assert params[0] == str(cam)
        assert _json.loads(params[1]) == violations
        assert params[2] == 0.8
        assert params[3] == "evidence/k.jpg"
