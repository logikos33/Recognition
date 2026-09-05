"""
Tests: TrainingRepository — campos do pipeline MLOps (097/098, ajuste #2).

Cobre: get_model_by_job_id (guarda anti-duplicação), create_job estendido
(retrocompat + novos campos) e create_model estendido (registry 098).
"""
import json
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.constants import Framework, GpuProvider
from app.infrastructure.database.repositories.training_repository import TrainingRepository


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
    return TrainingRepository(_pool_with_cursor(cur)), cur


class TestGetModelByJobId:
    """Guarda anti-duplicação (ajuste #2): job_id não tem UNIQUE."""

    def test_returns_existing_model(self):
        job_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "job_id": str(job_id)}
        repo, cur = _repo(cur)
        result = repo.get_model_by_job_id(job_id)
        assert result is not None
        assert result["job_id"] == str(job_id)
        query, params = cur.execute.call_args[0]
        assert "job_id = %s" in query
        assert "LIMIT 1" in query
        assert params == (str(job_id),)

    def test_returns_none_when_no_model(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_model_by_job_id(uuid4()) is None


class TestCreateJobExtended:
    def test_legacy_call_unchanged(self):
        """Callers legados (4 args posicionais) — colunas 097 fora do INSERT."""
        uid = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "status": "pending"}
        repo, cur = _repo(cur)
        repo.create_job(uid, "balanced", "yolo26n", 100)
        query, params = cur.execute.call_args[0]
        assert "framework" not in query
        assert "callback_token" not in query
        # tenant_id SEMPRE presente: COALESCE(explicito, tenant do user)
        assert "tenant_id" in query
        assert "SELECT tenant_id FROM users" in query
        assert params == (str(uid), "balanced", "yolo26n", 100, None, str(uid))

    def test_pipeline_fields_included_when_set(self):
        uid = uuid4()
        dsv = uuid4()
        tenant = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4())}
        repo, cur = _repo(cur)
        repo.create_job(
            uid,
            dataset_version_id=dsv,
            framework=Framework.RFDETR,
            base_model="rfdetr_base",
            hyperparams={"epochs": 50, "lr": 1e-4},
            gpu_provider=GpuProvider.VAST_AI,
            callback_token="tok-" + "x" * 60,
            tenant_id=tenant,
        )
        query, params = cur.execute.call_args[0]
        for column in ("dataset_version_id", "framework", "base_model",
                       "hyperparams", "gpu_provider", "callback_token", "tenant_id"):
            assert column in query
        assert str(dsv) in params
        assert "rfdetr" in params
        assert str(tenant) in params
        # hyperparams serializado como JSON
        json_params = [p for p in params if isinstance(p, str) and p.startswith("{")]
        assert any(json.loads(p) == {"epochs": 50, "lr": 1e-4} for p in json_params)

    def test_partial_pipeline_fields(self):
        """Somente framework — demais colunas 097 ausentes do INSERT."""
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create_job(uuid4(), framework="yolox")
        query = cur.execute.call_args[0][0]
        assert "framework" in query
        assert "gpu_provider" not in query
        assert "dataset_version_id" not in query


class TestCreateModelExtended:
    def test_legacy_payload_unchanged(self):
        """Payload legado — colunas 098 fora do INSERT; tenant via subquery."""
        uid = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "name": "m"}
        repo, cur = _repo(cur)
        repo.create_model({
            "user_id": uid, "name": "m", "model_path": "models/best.pt",
        })
        query, params = cur.execute.call_args[0]
        assert "r2_onnx_key" not in query
        assert "framework" not in query
        assert "(SELECT tenant_id FROM users WHERE id = %s)" in query
        assert params[-1] == str(uid)  # subquery de tenant

    def test_registry_fields_included(self):
        uid = uuid4()
        job_id = uuid4()
        dsv = uuid4()
        tenant = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4())}
        repo, cur = _repo(cur)
        repo.create_model({
            "user_id": uid,
            "job_id": job_id,
            "name": "rfdetr-epi-v1",
            "model_path": "models/t/rfdetr-epi-v1.onnx",
            "tenant_id": tenant,
            "origin": "vast_ai",
            "framework": Framework.RFDETR,
            "r2_onnx_key": "models/t/rfdetr-epi-v1.onnx",
            "r2_weights_key": "models/t/rfdetr-epi-v1.pth",
            "metrics": {"per_class": {"helmet": {"ap": 0.91}}},
            "dataset_version_id": dsv,
            "module_code": "epi",
        })
        query, params = cur.execute.call_args[0]
        for column in ("framework", "r2_onnx_key", "r2_weights_key",
                       "metrics", "dataset_version_id", "module_code"):
            assert column in query
        assert str(tenant) in params
        assert "models/t/rfdetr-epi-v1.pth" in params
        json_params = [p for p in params if isinstance(p, str) and p.startswith("{")]
        assert any("per_class" in p for p in json_params)

    def test_display_name_included_when_present(self):
        """Regra de nomenclatura do modelo no nascimento: display_name é
        opcional no mesmo padrão dos demais campos 098 (framework,
        r2_onnx_key, metrics...) — só entra no INSERT quando presente."""
        uid = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4())}
        repo, cur = _repo(cur)
        repo.create_model({
            "user_id": uid, "name": "rfdetr-epi-v1", "model_path": "models/best.onnx",
            "display_name": "Logikos EPI Completo · 04/09 14h30",
        })
        query, params = cur.execute.call_args[0]
        assert "display_name" in query
        assert "Logikos EPI Completo · 04/09 14h30" in params

    def test_display_name_omitted_when_absent(self):
        """Payload sem display_name — coluna fora do INSERT (default NULL do
        schema, retrocompat com callers que ainda não a calculam)."""
        uid = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4())}
        repo, cur = _repo(cur)
        repo.create_model({
            "user_id": uid, "name": "m", "model_path": "models/best.onnx",
        })
        query, _ = cur.execute.call_args[0]
        assert "display_name" not in query

    def test_explicit_tenant_short_circuits_subquery(self):
        """tenant_id explícito → COALESCE usa o valor, não o lookup em users."""
        tenant = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create_model({
            "user_id": uuid4(), "name": "m", "model_path": "p",
            "tenant_id": tenant,
        })
        query, params = cur.execute.call_args[0]
        assert "COALESCE(%s, (SELECT tenant_id FROM users WHERE id = %s))" in query
        assert str(tenant) in params
