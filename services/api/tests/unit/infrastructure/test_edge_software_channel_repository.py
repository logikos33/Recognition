"""Tests: EdgeSoftwareChannelRepository — public.edge_software_channels (migration 106)."""
from contextlib import contextmanager
from unittest.mock import MagicMock

from app.infrastructure.database.repositories.edge_software_channel_repository import (
    EdgeSoftwareChannelRepository,
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
    return EdgeSoftwareChannelRepository(_pool_with_cursor(cur)), cur


class TestGetTargetRef:
    def test_returns_target_ref_when_channel_exists(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"target_ref": "abc123"}
        repo, _ = _repo(cur)
        assert repo.get_target_ref("dev") == "abc123"

    def test_returns_none_when_channel_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_target_ref("nonexistent") is None

    def test_channel_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.get_target_ref("stable")
        assert cur.execute.call_args[0][1] == ("stable",)


class TestListChannels:
    def test_returns_all_channels(self):
        cur = MagicMock()
        cur.fetchall.return_value = [
            {"channel": "dev", "target_ref": "abc"},
            {"channel": "stable", "target_ref": "def"},
        ]
        repo, _ = _repo(cur)
        result = repo.list_channels()
        assert len(result) == 2

    def test_orders_by_channel(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_channels()
        query = cur.execute.call_args[0][0].lower()
        assert "order by channel" in query


class TestSetTargetRef:
    def test_returns_upserted_row(self):
        cur = MagicMock()
        cur.fetchone.return_value = {
            "channel": "dev", "target_ref": "abc123", "updated_by": "user-1",
        }
        repo, _ = _repo(cur)
        result = repo.set_target_ref("dev", "abc123", "user-1")
        assert result["target_ref"] == "abc123"

    def test_params_contain_channel_ref_and_actor(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.set_target_ref("dev", "new-ref", "actor-9")
        params = cur.execute.call_args[0][1]
        assert params == ("dev", "new-ref", "actor-9")

    def test_query_uses_on_conflict_upsert(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.set_target_ref("dev", "ref", None)
        query = cur.execute.call_args[0][0]
        assert "ON CONFLICT" in query
        assert "channel" in query.lower()

    def test_updated_by_can_be_none(self):
        """Programmatic/system-set targets (no human actor) are allowed."""
        cur = MagicMock()
        cur.fetchone.return_value = {"channel": "dev", "target_ref": "r", "updated_by": None}
        repo, cur = _repo(cur)
        repo.set_target_ref("dev", "r", None)
        params = cur.execute.call_args[0][1]
        assert params[2] is None
