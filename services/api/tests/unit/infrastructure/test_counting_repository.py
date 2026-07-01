"""
Tests: CountingRepository — sessions, events, LPR plate methods.
"""
import json
from contextlib import contextmanager
from uuid import uuid4

from unittest.mock import MagicMock

from app.infrastructure.database.repositories.counting_repository import CountingRepository


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
    return CountingRepository(_pool_with_cursor(cur)), cur


class TestCreateSession:

    def test_returns_created_row(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "sess-1", "module_code": "epi"}
        repo, _ = _repo(cur)
        result = repo.create_session(uuid4(), uuid4(), "epi")
        assert result["module_code"] == "epi"

    def test_tenant_camera_module_in_params(self):
        tenant_id = uuid4()
        camera_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create_session(tenant_id, camera_id, "fueling")
        params = cur.execute.call_args[0][1]
        assert str(tenant_id) in params
        assert str(camera_id) in params
        assert "fueling" in params


class TestGetSession:

    def test_returns_session_when_found(self):
        sess_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(sess_id), "status": "running"}
        repo, _ = _repo(cur)
        result = repo.get_session(sess_id, uuid4())
        assert result["status"] == "running"

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_session(uuid4(), uuid4()) is None

    def test_both_ids_in_params(self):
        sess_id = uuid4()
        tenant_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.get_session(sess_id, tenant_id)
        params = cur.execute.call_args[0][1]
        assert str(sess_id) in params
        assert str(tenant_id) in params


class TestListActiveSessions:

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "s1", "camera_name": "Cam 1"}]
        repo, _ = _repo(cur)
        result = repo.list_active_sessions(uuid4())
        assert len(result) == 1
        assert result[0]["camera_name"] == "Cam 1"

    def test_tenant_id_in_params(self):
        tenant_id = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_active_sessions(tenant_id)
        params = cur.execute.call_args[0][1]
        assert str(tenant_id) in params

    def test_running_status_in_query(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_active_sessions(uuid4())
        query = cur.execute.call_args[0][0]
        assert "running" in query


class TestStopSession:

    def test_returns_stopped_session(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "s1", "status": "stopped"}
        repo, _ = _repo(cur)
        result = repo.stop_session(uuid4(), uuid4(), {"helmet": 3})
        assert result["status"] == "stopped"

    def test_total_counts_serialized_as_json(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        counts = {"helmet": 5, "vest": 2}
        repo.stop_session(uuid4(), uuid4(), counts)
        params = cur.execute.call_args[0][1]
        assert json.loads(params[0]) == counts

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.stop_session(uuid4(), uuid4(), {}) is None


class TestUpsertEvent:

    def test_returns_event_row(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "ev-1", "class_name": "helmet"}
        repo, _ = _repo(cur)
        result = repo.upsert_event(uuid4(), 42, "helmet", 0.95)
        assert result["class_name"] == "helmet"

    def test_track_id_and_confidence_in_params(self):
        sess_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.upsert_event(sess_id, 99, "no_vest", 0.75)
        params = cur.execute.call_args[0][1]
        assert str(sess_id) in params
        assert 99 in params
        assert "no_vest" in params
        assert 0.75 in params

    def test_conflict_resolution_in_query(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.upsert_event(uuid4(), 1, "helmet", 0.9)
        query = cur.execute.call_args[0][0]
        assert "ON CONFLICT" in query


class TestGetSessionCounts:

    def test_returns_aggregated_counts(self):
        cur = MagicMock()
        cur.fetchall.return_value = [
            {"class_name": "helmet", "count": 5},
            {"class_name": "no_helmet", "count": 2},
        ]
        repo, _ = _repo(cur)
        result = repo.get_session_counts(uuid4())
        assert len(result) == 2
        assert result[0]["class_name"] == "helmet"

    def test_session_id_in_params(self):
        sess_id = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_session_counts(sess_id)
        params = cur.execute.call_args[0][1]
        assert str(sess_id) in params


class TestUpdatePlate:

    def test_returns_updated_row(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "s1", "plate_text": "ABC1234"}
        repo, _ = _repo(cur)
        result = repo.update_plate(uuid4(), uuid4(), "ABC1234", 0.92)
        assert result["plate_text"] == "ABC1234"

    def test_plate_and_tenant_in_params(self):
        sess_id = uuid4()
        tenant_id = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.update_plate(sess_id, tenant_id, "XYZ9999", 0.88)
        params = cur.execute.call_args[0][1]
        assert "XYZ9999" in params
        assert str(sess_id) in params
        assert str(tenant_id) in params

    def test_plate_review_manual_flags(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.update_plate(uuid4(), uuid4(), "ABC", 0.5, plate_review=True, plate_manual=True)
        params = cur.execute.call_args[0][1]
        assert True in params

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.update_plate(uuid4(), uuid4(), "ABC", 0.9) is None


class TestListSessionsWithPlate:

    def test_returns_sessions_with_plate(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "s1", "plate_text": "ABC"}]
        repo, _ = _repo(cur)
        result = repo.list_sessions_with_plate(uuid4())
        assert len(result) == 1

    def test_plate_not_null_in_query(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_sessions_with_plate(uuid4())
        query = cur.execute.call_args[0][0]
        assert "plate_text IS NOT NULL" in query

    def test_only_review_adds_filter(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_sessions_with_plate(uuid4(), only_review=True)
        query = cur.execute.call_args[0][0]
        assert "plate_review" in query

    def test_only_review_false_no_extra_filter(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_sessions_with_plate(uuid4(), only_review=False)
        query = cur.execute.call_args[0][0]
        assert "plate_review = TRUE" not in query

    def test_tenant_id_in_params(self):
        tenant_id = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_sessions_with_plate(tenant_id)
        params = cur.execute.call_args[0][1]
        assert str(tenant_id) in params
