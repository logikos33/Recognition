"""
Tests: ModelRolloutRepository — _to_manifest helper + repository methods.

All DB calls go through a mocked DatabasePool (contextmanager pattern).
`_to_manifest` is tested directly as a pure function.
"""
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4


from app.infrastructure.database.repositories.model_rollout_repository import (
    ModelRolloutRepository,
    _to_manifest,
)

_POOL_PATH = "app.infrastructure.database.connection.DatabasePool"


def _repo() -> tuple[ModelRolloutRepository, MagicMock]:
    mock_pool = MagicMock()
    return ModelRolloutRepository(mock_pool), mock_pool


def _pool_with_cursor(mock_cursor):
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


def _row(
    model_id=None,
    name="v1",
    module="epi",
    version="1.0",
    r2_key="models/v1.pt",
    hub_model_id=None,
    metrics=None,
    active=True,
    created_at=None,
) -> dict:
    return {
        "id": model_id or uuid4(),
        "name": name,
        "module": module,
        "version": version,
        "r2_key": r2_key,
        "hub_model_id": hub_model_id,
        "metrics": metrics or {"mAP50": 0.92},
        "active": active,
        "created_at": created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
    }


# ---------------------------------------------------------------------------
# _to_manifest (pure function)
# ---------------------------------------------------------------------------

class TestToManifest:

    def test_basic_fields_mapped(self):
        row = _row()
        m = _to_manifest(row)
        assert m["module"] == "epi"
        assert m["name"] == "v1"
        assert m["version"] == "1.0"
        assert m["checksum"] == "models/v1.pt"
        assert m["active"] is True

    def test_id_cast_to_str(self):
        uid = uuid4()
        row = _row(model_id=uid)
        m = _to_manifest(row)
        assert m["id"] == str(uid)

    def test_metrics_dict_parsed(self):
        row = _row(metrics={"git_sha": "abc123", "canary": True})
        m = _to_manifest(row)
        assert m["git_sha"] == "abc123"
        assert m["canary"] is True

    def test_metrics_json_string_parsed(self):
        row = _row(metrics=json.dumps({"git_sha": "def456"}))
        m = _to_manifest(row)
        assert m["git_sha"] == "def456"

    def test_metrics_invalid_json_string_defaults(self):
        row = _row(metrics="not-json")
        m = _to_manifest(row)
        assert m["git_sha"] is None
        assert m["canary"] is False

    def test_metrics_none_defaults(self):
        row = _row(metrics=None)
        m = _to_manifest(row)
        assert m["git_sha"] is None
        assert m["canary"] is False

    def test_created_at_iso_format(self):
        dt = datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc)
        row = _row(created_at=dt)
        m = _to_manifest(row)
        assert "2026-06-20" in m["created_at"]

    def test_created_at_none_is_none(self):
        row = _row(created_at=None)
        row["created_at"] = None
        m = _to_manifest(row)
        assert m["created_at"] is None

    def test_active_false_mapped(self):
        row = _row(active=False)
        m = _to_manifest(row)
        assert m["active"] is False


# ---------------------------------------------------------------------------
# get_active_model
# ---------------------------------------------------------------------------

class TestGetActiveModel:

    def test_returns_manifest_when_row_found(self):
        row = _row(active=True)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = row
        repo, _ = _repo()
        repo._db = _pool_with_cursor(mock_cursor)
        result = repo.get_active_model("tenant_a", "epi")
        assert result is not None
        assert result["active"] is True

    def test_returns_none_when_no_row(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        repo, _ = _repo()
        repo._db = _pool_with_cursor(mock_cursor)
        result = repo.get_active_model("tenant_a", "epi")
        assert result is None

    def test_executes_with_module_param(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        repo, _ = _repo()
        repo._db = _pool_with_cursor(mock_cursor)
        repo.get_active_model("tenant_x", "fueling")
        params = mock_cursor.execute.call_args[0][1]
        assert "fueling" in params


# ---------------------------------------------------------------------------
# get_model_by_id
# ---------------------------------------------------------------------------

class TestGetModelById:

    def test_returns_raw_dict_when_found(self):
        row = _row(version="2.0")
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = row
        repo, _ = _repo()
        repo._db = _pool_with_cursor(mock_cursor)
        result = repo.get_model_by_id("tenant_a", str(uuid4()))
        assert result["version"] == "2.0"

    def test_returns_none_when_not_found(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        repo, _ = _repo()
        repo._db = _pool_with_cursor(mock_cursor)
        assert repo.get_model_by_id("tenant_a", "no-such-id") is None


# ---------------------------------------------------------------------------
# mark_canary
# ---------------------------------------------------------------------------

class TestMarkCanary:

    def test_returns_manifest_on_success(self):
        row = _row(metrics={"canary": True})
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = row
        repo, _ = _repo()
        repo._db = _pool_with_cursor(mock_cursor)
        result = repo.mark_canary("tenant_a", str(uuid4()))
        assert result["canary"] is True

    def test_returns_none_when_not_found(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        repo, _ = _repo()
        repo._db = _pool_with_cursor(mock_cursor)
        assert repo.mark_canary("tenant_a", "ghost-id") is None


# ---------------------------------------------------------------------------
# pin_model
# ---------------------------------------------------------------------------

class TestPinModel:

    def test_returns_new_and_previous_manifests(self):
        prev_row = _row(name="old", active=True)
        new_row = _row(name="new", active=True)
        schema = "tenant_a"
        module = "epi"
        model_id = str(uuid4())

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [prev_row, new_row]

        @contextmanager
        def _txn_conn():
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _txn_conn

        repo, _ = _repo()
        repo._db = mock_pool
        new_m, prev_m = repo.pin_model(schema, model_id, module)

        assert new_m["name"] == "new"
        assert prev_m["name"] == "old"

    def test_previous_is_none_when_no_prior_active(self):
        new_row = _row(name="first", active=True)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [None, new_row]

        @contextmanager
        def _txn_conn():
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = _txn_conn

        repo, _ = _repo()
        repo._db = mock_pool
        new_m, prev_m = repo.pin_model("tenant_a", str(uuid4()), "epi")
        assert prev_m is None
        assert new_m is not None


# ---------------------------------------------------------------------------
# record_activation_log
# ---------------------------------------------------------------------------

class TestRecordActivationLog:

    def test_calls_execute_mutation_no_return(self):
        repo, _ = _repo()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        repo._db = _pool_with_cursor(mock_cursor)
        model_id = str(uuid4())
        repo.record_activation_log(model_id, "user:admin", None)
        params = mock_cursor.execute.call_args[0][1]
        assert model_id in params
        assert "user:admin" in params

    def test_previous_model_id_in_params(self):
        repo, _ = _repo()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        repo._db = _pool_with_cursor(mock_cursor)
        prev_id = str(uuid4())
        repo.record_activation_log(str(uuid4()), "user:admin", prev_id)
        params = mock_cursor.execute.call_args[0][1]
        assert prev_id in params


# ---------------------------------------------------------------------------
# get_last_activation_log
# ---------------------------------------------------------------------------

class TestGetLastActivationLog:

    def test_returns_log_dict_when_found(self):
        log_row = {
            "id": uuid4(), "model_id": uuid4(), "activated_by": "user:admin",
            "activated_at": datetime.now(tz=timezone.utc), "previous_model_id": None,
        }
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = log_row
        repo, _ = _repo()
        repo._db = _pool_with_cursor(mock_cursor)
        result = repo.get_last_activation_log(str(uuid4()))
        assert result["activated_by"] == "user:admin"

    def test_returns_none_when_no_log(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        repo, _ = _repo()
        repo._db = _pool_with_cursor(mock_cursor)
        assert repo.get_last_activation_log("no-model") is None
