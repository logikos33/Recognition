"""
Tests: VideoRepository — create, get_by_id, get_by_user, delete,
get_total_storage, update_status (4 branches), update_progress, update_duration.
"""
from contextlib import contextmanager
from uuid import uuid4

from unittest.mock import MagicMock

from app.infrastructure.database.repositories.video_repository import VideoRepository


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
    return VideoRepository(_pool_with_cursor(cur)), cur


class TestCreate:

    def test_returns_created_row(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "vid-1", "filename": "a.mp4"}
        repo, _ = _repo(cur)
        result = repo.create(uuid4(), "a.mp4", "original.mp4", 1024)
        assert result["filename"] == "a.mp4"

    def test_params_include_filename_and_size(self):
        user_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create(user_id, "b.mp4", None, 2048)
        params = cur.execute.call_args[0][1]
        assert str(user_id) in params
        assert "b.mp4" in params
        assert 2048 in params


class TestGetById:

    def test_returns_row_when_found(self):
        vid_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(vid_id)}
        repo, _ = _repo(cur)
        result = repo.get_by_id(vid_id)
        assert result["id"] == str(vid_id)

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_by_id(uuid4()) is None


class TestGetByUser:

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "v1"}, {"id": "v2"}]
        repo, _ = _repo(cur)
        result = repo.get_by_user(uuid4())
        assert len(result) == 2

    def test_user_id_in_params(self):
        user_id = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_by_user(user_id)
        params = cur.execute.call_args[0][1]
        assert str(user_id) in params


class TestDelete:

    def test_returns_true_when_video_deleted(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "vid-1"}
        repo, _ = _repo(cur)
        result = repo.delete(uuid4())
        assert result is True

    def test_returns_false_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.delete(uuid4()) is False

    def test_deletes_frames_before_video(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "v1"}
        repo, cur = _repo(cur)
        vid_id = uuid4()
        repo.delete(vid_id)
        calls = cur.execute.call_args_list
        assert len(calls) == 2
        assert "training_frames" in calls[0][0][0]
        assert "training_videos" in calls[1][0][0]

    def test_video_id_in_both_delete_params(self):
        vid_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.delete(vid_id)
        for call in cur.execute.call_args_list:
            assert str(vid_id) in call[0][1]


class TestGetTotalStorage:

    def test_returns_total_bytes(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"total": 5242880}
        repo, _ = _repo(cur)
        result = repo.get_total_storage(uuid4())
        assert result == 5242880

    def test_returns_zero_when_no_row(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_total_storage(uuid4()) == 0

    def test_returns_int(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"total": "1024"}
        repo, _ = _repo(cur)
        result = repo.get_total_storage(uuid4())
        assert isinstance(result, int)


class TestUpdateStatus:

    def test_both_frame_count_and_frames_expected(self):
        vid_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(vid_id), "status": "processing"}
        repo, cur = _repo(cur)
        repo.update_status(vid_id, "processing", frame_count=10, frames_expected=100)
        query = cur.execute.call_args[0][0]
        assert "frame_count" in query
        assert "frames_expected" in query

    def test_only_frames_expected(self):
        vid_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(vid_id)}
        repo, cur = _repo(cur)
        repo.update_status(vid_id, "processing", frames_expected=200)
        query = cur.execute.call_args[0][0]
        assert "frames_expected" in query
        assert "frame_count" not in query

    def test_only_frame_count(self):
        vid_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(vid_id)}
        repo, cur = _repo(cur)
        repo.update_status(vid_id, "done", frame_count=50)
        query = cur.execute.call_args[0][0]
        assert "frame_count" in query
        assert "frames_expected" not in query

    def test_base_case_neither(self):
        vid_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(vid_id), "status": "error"}
        repo, cur = _repo(cur)
        repo.update_status(vid_id, "error", error_message="failed")
        query = cur.execute.call_args[0][0]
        assert "error_message" in query
        assert "frame_count" not in query
        assert "frames_expected" not in query

    def test_status_always_in_params(self):
        vid_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(vid_id)}
        repo, cur = _repo(cur)
        repo.update_status(vid_id, "ready")
        params = cur.execute.call_args[0][1]
        assert "ready" in params


class TestUpdateProgress:

    def test_updates_frame_count(self):
        vid_id = uuid4()
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.update_progress(vid_id, 42)
        params = cur.execute.call_args[0][1]
        assert 42 in params
        assert str(vid_id) in params


class TestUpdateDuration:

    def test_updates_duration_seconds(self):
        vid_id = uuid4()
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.update_duration(vid_id, 120.5)
        params = cur.execute.call_args[0][1]
        assert 120.5 in params
        assert str(vid_id) in params
