"""
Tests: ModelDeploymentRepository — histórico de deployments (migration 100).
"""
import json
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.constants import DeploymentStatus
from app.infrastructure.database.repositories.model_deployment_repository import (
    ModelDeploymentRepository,
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
    return ModelDeploymentRepository(_pool_with_cursor(cur)), cur


class TestCreate:
    def test_create_with_config(self):
        tenant = uuid4()
        model = uuid4()
        cam = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "status": "active"}
        repo, cur = _repo(cur)
        config = {"roi": [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]],
                  "thresholds": {"helmet": 0.6}}
        result = repo.create({
            "tenant_id": tenant, "model_id": model, "camera_id": cam,
            "config": config, "deployed_by": uuid4(),
        })
        assert result["status"] == "active"
        query, params = cur.execute.call_args[0]
        assert "COALESCE(%s, 'epi')" in query
        assert "COALESCE(%s, 'active')" in query
        assert params[0] == str(tenant)
        assert json.loads(params[4]) == config

    def test_create_defaults_empty_config(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create({
            "tenant_id": uuid4(), "model_id": uuid4(), "camera_id": uuid4(),
        })
        params = cur.execute.call_args[0][1]
        assert json.loads(params[4]) == {}


class TestReads:
    def test_get_active_for_camera(self):
        tenant = str(uuid4())
        cam = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "d1", "status": "active"}
        repo, cur = _repo(cur)
        result = repo.get_active_for_camera(tenant, cam, "epi")
        assert result["status"] == "active"
        query, params = cur.execute.call_args[0]
        assert "status = 'active'" in query
        assert "LIMIT 1" in query
        assert params == (tenant, str(cam), "epi")

    def test_list_for_camera_with_module(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "d2"}, {"id": "d1"}]
        repo, cur = _repo(cur)
        result = repo.list_for_camera(str(uuid4()), uuid4(), module_code="epi")
        assert len(result) == 2
        assert "module_code = %s" in cur.execute.call_args[0][0]

    def test_list_for_camera_all_modules(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_for_camera(str(uuid4()), uuid4())
        assert "module_code" not in cur.execute.call_args[0][0]

    def test_list_by_model_tenant_scoped(self):
        model = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "d1"}]
        repo, cur = _repo(cur)
        repo.list_by_model(model, tenant)
        query, params = cur.execute.call_args[0]
        assert "model_id = %s AND tenant_id = %s" in query
        assert params == (str(model), tenant)

    def test_get_by_id_tenant_scoped(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        assert repo.get_by_id(uuid4(), str(uuid4())) is None
        assert "tenant_id = %s" in cur.execute.call_args[0][0]


class TestDeactivate:
    def test_deactivate_sets_status_and_timestamp(self):
        did = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(did), "status": "inactive"}
        repo, cur = _repo(cur)
        result = repo.deactivate(did, tenant)
        assert result["status"] == "inactive"
        query, params = cur.execute.call_args[0]
        assert "deactivated_at = NOW()" in query
        assert params == ("inactive", str(did), tenant)

    def test_deactivate_rolled_back_status(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x", "status": "rolled_back"}
        repo, cur = _repo(cur)
        repo.deactivate(uuid4(), str(uuid4()), status=DeploymentStatus.ROLLED_BACK)
        params = cur.execute.call_args[0][1]
        assert params[0] == "rolled_back"

    def test_deactivate_active_for_camera_returns_rowcount(self):
        cur = MagicMock()
        cur.rowcount = 2
        repo, cur = _repo(cur)
        count = repo.deactivate_active_for_camera(str(uuid4()), uuid4(), "epi")
        assert count == 2
        query = cur.execute.call_args[0][0]
        assert "status = 'active'" in query
        assert "SET status = 'inactive'" in query
