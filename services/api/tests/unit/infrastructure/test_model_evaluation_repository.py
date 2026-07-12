"""
Tests: ModelEvaluationRepository — avaliação campeão×desafiante (migration 101).
"""
import json
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.constants import EvalVerdict
from app.infrastructure.database.repositories.model_evaluation_repository import (
    ModelEvaluationRepository,
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
    return ModelEvaluationRepository(_pool_with_cursor(cur)), cur


class TestCreate:
    def test_create_pending_by_default(self):
        tenant = uuid4()
        model = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "verdict": "pending"}
        repo, cur = _repo(cur)
        result = repo.create({"tenant_id": tenant, "model_id": model})
        assert result["verdict"] == "pending"
        query, params = cur.execute.call_args[0]
        assert "COALESCE(%s, 'pending')" in query
        assert params[0] == str(tenant)
        assert params[6] is None  # verdict omitido

    def test_create_with_champion_and_metrics(self):
        champion = uuid4()
        dsv = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create({
            "tenant_id": uuid4(),
            "model_id": uuid4(),
            "champion_model_id": champion,
            "dataset_version_id": dsv,
            "metrics": {"map50": 0.88},
            "confusion_matrix": {"helmet": {"tp": 10}},
            "verdict": EvalVerdict.PROMOTE,
        })
        params = cur.execute.call_args[0][1]
        assert params[2] == str(champion)
        assert params[3] == str(dsv)
        assert json.loads(params[4]) == {"map50": 0.88}
        assert json.loads(params[5]) == {"helmet": {"tp": 10}}
        assert params[6] == "promote"


class TestReads:
    def test_get_latest_for_model(self):
        model = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "e1", "verdict": "promote"}
        repo, cur = _repo(cur)
        result = repo.get_latest_for_model(model, tenant)
        assert result["verdict"] == "promote"
        query, params = cur.execute.call_args[0]
        assert "ORDER BY created_at DESC LIMIT 1" in query
        assert params == (str(model), tenant)

    def test_list_by_model(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "e2"}, {"id": "e1"}]
        repo, cur = _repo(cur)
        result = repo.list_by_model(uuid4(), str(uuid4()))
        assert len(result) == 2
        assert "tenant_id = %s" in cur.execute.call_args[0][0]

    def test_get_by_id_tenant_scoped(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        assert repo.get_by_id(uuid4(), str(uuid4())) is None
        assert "tenant_id = %s" in cur.execute.call_args[0][0]


class TestUpdateVerdict:
    def test_verdict_only(self):
        eid = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(eid), "verdict": "reject"}
        repo, cur = _repo(cur)
        result = repo.update_verdict(eid, tenant, EvalVerdict.REJECT)
        assert result["verdict"] == "reject"
        query, params = cur.execute.call_args[0]
        assert "metrics" not in query
        assert params == ("reject", str(eid), tenant)

    def test_verdict_with_metrics_and_matrix(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.update_verdict(
            uuid4(), str(uuid4()), "promote",
            metrics={"map50": 0.9},
            confusion_matrix={"vest": {"fp": 2}},
        )
        query, params = cur.execute.call_args[0]
        assert "metrics = %s::jsonb" in query
        assert "confusion_matrix = %s::jsonb" in query
        assert json.loads(params[1]) == {"map50": 0.9}
        assert json.loads(params[2]) == {"vest": {"fp": 2}}
