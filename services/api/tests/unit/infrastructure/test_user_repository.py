"""Tests: UserRepository — get_by_id (line 28) and update_active (line 71)."""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.user_repository import UserRepository


def _make_repo(cursor):
    @contextmanager
    def _conn_ctx():
        conn = MagicMock()
        conn.cursor.return_value = cursor
        yield conn

    pool = MagicMock()
    pool.get_connection.side_effect = _conn_ctx
    return UserRepository(pool)


class TestGetById:

    def test_returns_user_when_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "uid-1", "email": "a@b.com", "name": "A", "role": "operator"}
        repo = _make_repo(cur)
        result = repo.get_by_id(uuid4())
        assert result["email"] == "a@b.com"

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo = _make_repo(cur)
        assert repo.get_by_id(uuid4()) is None

    def test_user_id_in_query_params(self):
        uid = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo = _make_repo(cur)
        repo.get_by_id(uid)
        params = cur.execute.call_args[0][1]
        assert str(uid) in params


class TestUpdateActive:

    def test_activate_returns_updated_user(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "uid-1", "email": "a@b.com", "is_active": True}
        repo = _make_repo(cur)
        result = repo.update_active(uuid4(), True)
        assert result["is_active"] is True

    def test_deactivate_returns_updated_user(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "uid-1", "email": "a@b.com", "is_active": False}
        repo = _make_repo(cur)
        result = repo.update_active(uuid4(), False)
        assert result["is_active"] is False

    def test_returns_none_when_user_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo = _make_repo(cur)
        assert repo.update_active(uuid4(), True) is None

    def test_params_contain_flag_and_user_id(self):
        uid = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo = _make_repo(cur)
        repo.update_active(uid, True)
        params = cur.execute.call_args[0][1]
        assert str(uid) in params
        assert True in params
