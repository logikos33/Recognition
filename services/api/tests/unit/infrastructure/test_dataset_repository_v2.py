"""
Tests: DatasetRepository — datasets pai + create_version_v2 (096, ajuste #9).
"""
import json
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.constants import DatasetVersionStatus
from app.infrastructure.database.repositories.dataset_repository import DatasetRepository


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
    return DatasetRepository(_pool_with_cursor(cur)), cur


class TestDatasetsParent:
    def test_create_dataset(self):
        tenant = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "name": "EPI Obra Sul"}
        repo, cur = _repo(cur)
        result = repo.create_dataset({
            "tenant_id": tenant, "name": "EPI Obra Sul", "created_by": uuid4(),
        })
        assert result["name"] == "EPI Obra Sul"
        params = cur.execute.call_args[0][1]
        assert params[0] == str(tenant)
        assert params[1] is None  # module_code omitido → COALESCE 'epi'

    def test_create_dataset_with_module(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create_dataset({
            "tenant_id": uuid4(), "name": "Fueling", "module_code": "fueling",
        })
        params = cur.execute.call_args[0][1]
        assert params[1] == "fueling"

    def test_get_dataset_by_id_tenant_scoped(self):
        did = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        assert repo.get_dataset_by_id(did, tenant) is None
        query, params = cur.execute.call_args[0]
        assert "tenant_id = %s" in query
        assert params == (str(did), tenant)

    def test_list_datasets_by_tenant_and_module(self):
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": str(uuid4())}]
        repo, cur = _repo(cur)
        result = repo.list_datasets(tenant, module_code="epi")
        assert len(result) == 1
        query, params = cur.execute.call_args[0]
        assert "module_code = %s" in query
        assert params == (tenant, "epi")

    def test_list_datasets_without_module(self):
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_datasets(tenant)
        query, params = cur.execute.call_args[0]
        assert "module_code" not in query
        assert params == (tenant,)


class TestCreateVersionV2:
    def test_writes_all_096_columns(self):
        tenant = uuid4()
        dataset_id = uuid4()
        created_by = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "status": "building"}
        repo, cur = _repo(cur)

        result = repo.create_version_v2({
            "user_id": created_by,
            "version": "v3",
            "frame_count": 120,
            "train_count": 84,
            "val_count": 18,
            "test_count": 18,
            "class_distribution": {"helmet": 60},
            "tenant_id": tenant,
            "module_code": "epi",
            "dataset_id": dataset_id,
            "split": {"train": 0.7, "val": 0.15, "test": 0.15},
            "augmentations": {"flip": True},
            "coco_r2_key": "dataset-exports/t/d/v3/_annotations.coco.json",
            "export_format": "coco",
            "status": DatasetVersionStatus.BUILDING,
            "created_by": created_by,
        })
        assert result["status"] == "building"

        query, params = cur.execute.call_args[0]
        for column in ("tenant_id", "module_code", "dataset_id", "split",
                       "augmentations", "coco_r2_key", "export_format",
                       "status", "created_by"):
            assert column in query

        assert params[8] == str(tenant)
        assert params[10] == str(dataset_id)
        assert json.loads(params[11]) == {"train": 0.7, "val": 0.15, "test": 0.15}
        assert json.loads(params[12]) == {"flip": True}
        assert params[13] == "dataset-exports/t/d/v3/_annotations.coco.json"
        assert params[14] == "coco"
        assert params[15] == "building"

    def test_minimal_payload_uses_schema_defaults(self):
        """Sem status/module_code → COALESCE cai nos defaults ('ready'/'epi')."""
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create_version_v2({
            "user_id": uuid4(), "version": "v1", "tenant_id": uuid4(),
        })
        params = cur.execute.call_args[0][1]
        assert params[9] is None   # module_code
        assert params[15] is None  # status
        assert params[2] == 0      # frame_count default

    def test_legacy_create_untouched(self):
        """create() legado continua com as 8 colunas originais."""
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x", "version": "v1.0.0"}
        repo, cur = _repo(cur)
        repo.create({
            "user_id": uuid4(), "version": "v1.0.0", "frame_count": 10,
            "train_count": 7, "val_count": 2, "test_count": 1,
        })
        query = cur.execute.call_args[0][0]
        assert "tenant_id" not in query


class TestVersionStatusAndListing:
    def test_update_version_status(self):
        vid = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(vid), "status": "ready"}
        repo, cur = _repo(cur)
        result = repo.update_version_status(vid, tenant, DatasetVersionStatus.READY)
        assert result["status"] == "ready"
        query, params = cur.execute.call_args[0]
        assert "tenant_id = %s" in query
        assert params == ("ready", str(vid), tenant)

    def test_update_version_status_with_coco_key(self):
        vid = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(vid)}
        repo, cur = _repo(cur)
        repo.update_version_status(vid, str(uuid4()), "ready", coco_r2_key="k.json")
        query, params = cur.execute.call_args[0]
        assert "coco_r2_key = %s" in query
        assert params[1] == "k.json"

    def test_get_versions_by_dataset(self):
        did = uuid4()
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "v2"}, {"id": "v1"}]
        repo, cur = _repo(cur)
        result = repo.get_versions_by_dataset(did, tenant)
        assert len(result) == 2
        query, params = cur.execute.call_args[0]
        assert "dataset_id = %s AND tenant_id = %s" in query
        assert params == (str(did), tenant)


class TestGetPendingVersion:
    """Achado da revisão adversarial: sem esta guarda, cada retry do Celery
    reINSERTava dataset_versions com o mesmo (dataset_id, version) — não há
    UNIQUE no schema (096) para impedir a duplicata."""

    def test_query_filters_building_and_error_status(self):
        did = str(uuid4())
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "status": "error"}
        repo, cur = _repo(cur)
        result = repo.get_pending_version(did, tenant, "v1")
        assert result["status"] == "error"
        query, params = cur.execute.call_args[0]
        assert "status IN ('building', 'error')" in query
        assert "dataset_id = %s AND tenant_id = %s AND version = %s" in query
        assert params == (did, tenant, "v1")

    def test_returns_none_when_no_pending_version(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        assert repo.get_pending_version(str(uuid4()), str(uuid4()), "v1") is None
