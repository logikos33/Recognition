"""
Tests: DemoVideoRepository — create, list_active, get_for_camera, soft_delete.

All DB calls go through a mocked DatabasePool (contextmanager pattern).
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from app.infrastructure.database.repositories.demo_video_repository import (
    DemoVideoRepository,
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
    pool = _pool_with_cursor(cur)
    return DemoVideoRepository(pool), cur


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

class TestCreate:

    def test_returns_created_row(self):
        row = {"id": 1, "module": "epi", "r2_key": "k/v.mp4", "r2_url": "https://x.r2/v.mp4"}
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = row
        repo, _ = _repo(mock_cursor)
        result = repo.create(module="epi", r2_key="k/v.mp4", r2_url="https://x.r2/v.mp4")
        assert result["module"] == "epi"
        assert result["r2_key"] == "k/v.mp4"

    def test_passes_all_optional_params(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 2, "module": "epi",
                                              "r2_key": "k", "r2_url": "u"}
        repo, cur = _repo(mock_cursor)
        repo.create(
            module="epi",
            r2_key="k",
            r2_url="u",
            camera_id="cam-1",
            label="Entrada",
            file_size_bytes=1024,
            duration_seconds=10.5,
            uploaded_by="user-1",
        )
        params = cur.execute.call_args[0][1]
        assert "cam-1" in params
        assert "Entrada" in params
        assert 1024 in params
        assert 10.5 in params
        assert "user-1" in params

    def test_none_optionals_passed_as_none(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 3, "module": "epi",
                                              "r2_key": "k", "r2_url": "u"}
        repo, cur = _repo(mock_cursor)
        repo.create(module="epi", r2_key="k", r2_url="u")
        params = cur.execute.call_args[0][1]
        # camera_id, label, file_size_bytes, duration_seconds, uploaded_by default to None
        assert params.count(None) >= 5

    def test_insert_returning_in_query(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 4, "module": "epi",
                                              "r2_key": "k", "r2_url": "u"}
        repo, cur = _repo(mock_cursor)
        repo.create(module="epi", r2_key="k", r2_url="u")
        query = cur.execute.call_args[0][0]
        assert "INSERT" in query.upper()
        assert "RETURNING" in query.upper()


# ---------------------------------------------------------------------------
# list_active
# ---------------------------------------------------------------------------

class TestListActive:

    def test_no_filters_returns_all_active(self):
        rows = [{"id": 1, "module": "epi"}, {"id": 2, "module": "fueling"}]
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        repo, _ = _repo(mock_cursor)
        result = repo.list_active()
        assert len(result) == 2

    def test_module_filter_added_to_query(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        repo, cur = _repo(mock_cursor)
        repo.list_active(module="epi")
        query, params = cur.execute.call_args[0]
        assert "module" in query
        assert "epi" in params

    def test_camera_id_filter_added_to_query(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        repo, cur = _repo(mock_cursor)
        repo.list_active(camera_id="cam-42")
        query, params = cur.execute.call_args[0]
        assert "camera_id" in query
        assert "cam-42" in params

    def test_both_filters_combined(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        repo, cur = _repo(mock_cursor)
        repo.list_active(module="epi", camera_id="cam-1")
        query, params = cur.execute.call_args[0]
        assert "module" in query
        assert "camera_id" in query
        assert "epi" in params
        assert "cam-1" in params

    def test_always_filters_active_true(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        repo, cur = _repo(mock_cursor)
        repo.list_active()
        query = cur.execute.call_args[0][0]
        assert "active" in query.lower()

    def test_returns_list_of_dicts(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"id": 1, "module": "epi"}]
        repo, _ = _repo(mock_cursor)
        result = repo.list_active()
        assert isinstance(result, list)
        assert result[0]["id"] == 1

    def test_empty_result(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        repo, _ = _repo(mock_cursor)
        assert repo.list_active() == []


# ---------------------------------------------------------------------------
# get_for_camera
# ---------------------------------------------------------------------------

class TestGetForCamera:

    def test_with_module_returns_row(self):
        row = {"id": 1, "camera_id": "cam-1", "module": "epi"}
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = row
        repo, _ = _repo(mock_cursor)
        result = repo.get_for_camera("cam-1", module="epi")
        assert result is not None
        assert result["camera_id"] == "cam-1"

    def test_without_module_queries_camera_only(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        repo, cur = _repo(mock_cursor)
        repo.get_for_camera("cam-99")
        query, params = cur.execute.call_args[0]
        assert "camera_id" in query
        assert "cam-99" in params
        assert "module" not in query.lower()

    def test_with_module_includes_fallback_logic(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        repo, cur = _repo(mock_cursor)
        repo.get_for_camera("cam-1", module="epi")
        query, params = cur.execute.call_args[0]
        # fallback: camera_id IS NULL AND module = %s
        assert "NULL" in query.upper() or "null" in query
        assert "epi" in params

    def test_no_row_returns_none(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        repo, _ = _repo(mock_cursor)
        assert repo.get_for_camera("cam-x") is None

    def test_no_row_with_module_returns_none(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        repo, _ = _repo(mock_cursor)
        assert repo.get_for_camera("cam-x", module="epi") is None


# ---------------------------------------------------------------------------
# soft_delete
# ---------------------------------------------------------------------------

class TestSoftDelete:

    def test_returns_true_when_row_found(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 5}
        repo, _ = _repo(mock_cursor)
        assert repo.soft_delete(5) is True

    def test_returns_false_when_no_row(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        repo, _ = _repo(mock_cursor)
        assert repo.soft_delete(99) is False

    def test_sets_active_false(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 5}
        repo, cur = _repo(mock_cursor)
        repo.soft_delete(5)
        query = cur.execute.call_args[0][0]
        assert "active = false" in query.lower() or "active=false" in query.lower()

    def test_passes_video_id_as_param(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 7}
        repo, cur = _repo(mock_cursor)
        repo.soft_delete(7)
        params = cur.execute.call_args[0][1]
        assert 7 in params
