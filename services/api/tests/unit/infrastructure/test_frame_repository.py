"""
Tests: FrameRepository — uncovered methods.

Covers: get_pre_annotations, get_annotated_by_video, get_by_id_and_user,
mark_validated, count_validated.
"""
from contextlib import contextmanager
from uuid import uuid4

from unittest.mock import MagicMock

from app.infrastructure.database.repositories.frame_repository import FrameRepository


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
    return FrameRepository(_pool_with_cursor(cur)), cur


class TestGetPreAnnotations:

    def test_returns_annotations_list(self):
        frame_id = uuid4()
        annotations = [{"x": 10, "y": 20, "label": "helmet"}]
        cur = MagicMock()
        cur.fetchone.return_value = {"pre_annotations": annotations}
        repo, _ = _repo(cur)
        result = repo.get_pre_annotations(frame_id)
        assert result == annotations

    def test_returns_none_when_frame_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_pre_annotations(uuid4()) is None

    def test_returns_none_when_pre_annotations_absent(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"pre_annotations": None}
        repo, _ = _repo(cur)
        assert repo.get_pre_annotations(uuid4()) is None

    def test_frame_id_in_params(self):
        frame_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.get_pre_annotations(frame_id)
        params = cur.execute.call_args[0][1]
        assert str(frame_id) in params


class TestGetAnnotatedByVideo:

    def test_returns_annotated_frames(self):
        cur = MagicMock()
        cur.fetchall.return_value = [
            {"id": "f-1", "is_annotated": True, "annotation_count": 3},
        ]
        repo, _ = _repo(cur)
        result = repo.get_annotated_by_video(uuid4(), uuid4())
        assert len(result) == 1
        assert result[0]["is_annotated"] is True

    def test_video_id_and_user_id_in_params(self):
        video_id = uuid4()
        user_id = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_annotated_by_video(video_id, user_id)
        params = cur.execute.call_args[0][1]
        assert str(video_id) in params
        assert str(user_id) in params

    def test_query_joins_training_videos(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_annotated_by_video(uuid4(), uuid4())
        query = cur.execute.call_args[0][0]
        assert "training_videos" in query


class TestGetByIdAndUser:

    def test_returns_frame_when_owner_matches(self):
        frame_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(frame_id), "is_annotated": False}
        repo, _ = _repo(cur)
        result = repo.get_by_id_and_user(frame_id, uuid4())
        assert result["id"] == str(frame_id)

    def test_returns_none_when_not_found_or_wrong_owner(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_by_id_and_user(uuid4(), uuid4()) is None

    def test_both_ids_in_params(self):
        frame_id = uuid4()
        user_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.get_by_id_and_user(frame_id, user_id)
        params = cur.execute.call_args[0][1]
        assert str(frame_id) in params
        assert str(user_id) in params


class TestMarkValidated:

    def test_returns_validated_frame(self):
        frame_id = uuid4()
        user_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(frame_id), "validated_at": "2026-01-01"}
        repo, _ = _repo(cur)
        result = repo.mark_validated(frame_id, user_id)
        assert result["validated_at"] == "2026-01-01"

    def test_returns_none_when_not_owned(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.mark_validated(uuid4(), uuid4()) is None

    def test_user_id_appears_twice_in_params(self):
        frame_id = uuid4()
        user_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.mark_validated(frame_id, user_id)
        params = cur.execute.call_args[0][1]
        # user_id appears as validated_by AND in WHERE clause
        assert params.count(str(user_id)) == 2


class TestCountValidated:

    def test_returns_counts_dict(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"annotated": 5, "validated": 3, "total": 10}
        repo, _ = _repo(cur)
        result = repo.count_validated(uuid4(), uuid4())
        assert result["annotated"] == 5
        assert result["validated"] == 3
        assert result["total"] == 10

    def test_returns_zeros_when_no_row(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        result = repo.count_validated(uuid4(), uuid4())
        assert result == {"annotated": 0, "validated": 0, "total": 0}

    def test_handles_none_values_from_db(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"annotated": None, "validated": None, "total": 5}
        repo, _ = _repo(cur)
        result = repo.count_validated(uuid4(), uuid4())
        assert result["annotated"] == 0
        assert result["validated"] == 0

    def test_both_ids_in_params(self):
        video_id = uuid4()
        user_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"annotated": 0, "validated": 0, "total": 0}
        repo, cur = _repo(cur)
        repo.count_validated(video_id, user_id)
        params = cur.execute.call_args[0][1]
        assert str(video_id) in params
        assert str(user_id) in params

    def test_query_joins_training_videos_for_ownership(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.count_validated(uuid4(), uuid4())
        query = cur.execute.call_args[0][0]
        assert "training_videos" in query
