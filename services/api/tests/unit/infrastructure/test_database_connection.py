"""
Tests: DatabasePool singleton + get_database_url helper.

psycopg2.pool.ThreadedConnectionPool is mocked throughout — no real DB needed.
Every test that touches the singleton must call DatabasePool.reset() in teardown
to avoid state leakage between tests.
"""
import os
from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from app.core.exceptions import DatabaseError
from app.infrastructure.database.connection import DatabasePool, get_database_url

_POOL_CLS = "app.infrastructure.database.connection.psycopg2.pool.ThreadedConnectionPool"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pool(url="postgresql://user:pass@localhost/db", **kwargs) -> DatabasePool:
    """Instantiate a DatabasePool with a mocked ThreadedConnectionPool."""
    with patch(_POOL_CLS) as mock_cls:
        mock_cls.return_value = MagicMock()
        return DatabasePool(url, **kwargs)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:

    def teardown_method(self):
        DatabasePool.reset()

    def test_creates_threaded_connection_pool(self):
        with patch(_POOL_CLS) as mock_cls:
            mock_cls.return_value = MagicMock()
            pool = DatabasePool("postgresql://u:p@h/db")
        mock_cls.assert_called_once()
        assert pool._pool is not None

    def test_psycopg2_error_raises_database_error(self):
        with patch(_POOL_CLS, side_effect=psycopg2.OperationalError("conn refused")):
            with pytest.raises(DatabaseError, match="pool"):
                DatabasePool("postgresql://bad/url")

    def test_default_min_max_conn(self):
        with patch(_POOL_CLS) as mock_cls:
            mock_cls.return_value = MagicMock()
            DatabasePool("postgresql://u:p@h/db")
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["minconn"] == 1
        assert call_kwargs["maxconn"] == 10

    def test_custom_min_max_conn(self):
        with patch(_POOL_CLS) as mock_cls:
            mock_cls.return_value = MagicMock()
            DatabasePool("postgresql://u:p@h/db", min_conn=2, max_conn=20)
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["minconn"] == 2
        assert call_kwargs["maxconn"] == 20

    def test_real_dict_cursor_factory_used(self):
        with patch(_POOL_CLS) as mock_cls:
            mock_cls.return_value = MagicMock()
            DatabasePool("postgresql://u:p@h/db")
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["cursor_factory"] is psycopg2.extras.RealDictCursor


# ---------------------------------------------------------------------------
# initialize / get_instance / reset
# ---------------------------------------------------------------------------

class TestSingleton:

    def teardown_method(self):
        DatabasePool.reset()

    def test_get_instance_none_before_init(self):
        DatabasePool.reset()
        assert DatabasePool.get_instance() is None

    def test_initialize_sets_instance(self):
        with patch(_POOL_CLS) as mock_cls:
            mock_cls.return_value = MagicMock()
            pool = DatabasePool.initialize("postgresql://u:p@h/db")
        assert DatabasePool.get_instance() is pool

    def test_initialize_twice_returns_same_instance(self):
        with patch(_POOL_CLS) as mock_cls:
            mock_cls.return_value = MagicMock()
            pool1 = DatabasePool.initialize("postgresql://u:p@h/db")
            pool2 = DatabasePool.initialize("postgresql://other/db")
        assert pool1 is pool2
        # ThreadedConnectionPool only called once
        assert mock_cls.call_count == 1

    def test_reset_clears_instance(self):
        with patch(_POOL_CLS) as mock_cls:
            mock_cls.return_value = MagicMock()
            DatabasePool.initialize("postgresql://u:p@h/db")
        DatabasePool.reset()
        assert DatabasePool.get_instance() is None

    def test_reset_when_no_instance_is_safe(self):
        DatabasePool.reset()  # already None — should not raise
        DatabasePool.reset()


# ---------------------------------------------------------------------------
# get_connection
# ---------------------------------------------------------------------------

class TestGetConnection:

    def teardown_method(self):
        DatabasePool.reset()

    def _pool_with_mock_conn(self):
        mock_conn = MagicMock()
        pool = _make_pool()
        pool._pool.getconn.return_value = mock_conn
        return pool, mock_conn

    def test_yields_connection(self):
        pool, mock_conn = self._pool_with_mock_conn()
        with pool.get_connection() as conn:
            assert conn is mock_conn

    def test_commits_on_success(self):
        pool, mock_conn = self._pool_with_mock_conn()
        with pool.get_connection():
            pass
        mock_conn.commit.assert_called_once()

    def test_puts_conn_back_on_success(self):
        pool, mock_conn = self._pool_with_mock_conn()
        with pool.get_connection():
            pass
        pool._pool.putconn.assert_called_once_with(mock_conn)

    def test_rollback_on_psycopg2_error(self):
        pool, mock_conn = self._pool_with_mock_conn()
        mock_conn.commit.side_effect = psycopg2.OperationalError("disk full")
        with pytest.raises(DatabaseError):
            with pool.get_connection():
                pass
        mock_conn.rollback.assert_called_once()

    def test_psycopg2_error_wrapped_as_database_error(self):
        pool, mock_conn = self._pool_with_mock_conn()
        mock_conn.commit.side_effect = psycopg2.OperationalError("disk full")
        with pytest.raises(DatabaseError):
            with pool.get_connection():
                pass

    def test_puts_conn_back_on_psycopg2_error(self):
        pool, mock_conn = self._pool_with_mock_conn()
        mock_conn.commit.side_effect = psycopg2.OperationalError("disk full")
        with pytest.raises(DatabaseError):
            with pool.get_connection():
                pass
        pool._pool.putconn.assert_called_once_with(mock_conn)

    def test_rollback_on_generic_exception(self):
        pool, mock_conn = self._pool_with_mock_conn()
        with pytest.raises(ValueError):
            with pool.get_connection():
                raise ValueError("boom")
        mock_conn.rollback.assert_called_once()

    def test_generic_exception_not_wrapped(self):
        pool, mock_conn = self._pool_with_mock_conn()
        with pytest.raises(ValueError, match="boom"):
            with pool.get_connection():
                raise ValueError("boom")

    def test_puts_conn_back_on_generic_exception(self):
        pool, mock_conn = self._pool_with_mock_conn()
        with pytest.raises(ValueError):
            with pool.get_connection():
                raise ValueError("boom")
        pool._pool.putconn.assert_called_once_with(mock_conn)


# ---------------------------------------------------------------------------
# close_all
# ---------------------------------------------------------------------------

class TestCloseAll:

    def teardown_method(self):
        DatabasePool.reset()

    def test_calls_closeall_on_open_pool(self):
        pool = _make_pool()
        pool._pool.closed = False
        pool.close_all()
        pool._pool.closeall.assert_called_once()

    def test_skips_closeall_on_already_closed_pool(self):
        pool = _make_pool()
        pool._pool.closed = True
        pool.close_all()
        pool._pool.closeall.assert_not_called()


# ---------------------------------------------------------------------------
# get_database_url
# ---------------------------------------------------------------------------

class TestGetDatabaseUrl:

    def test_normalizes_postgres_to_postgresql(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://user:pass@host/db"}):
            url = get_database_url()
        assert url.startswith("postgresql://")
        assert "user:pass@host/db" in url

    def test_postgresql_url_unchanged(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://u:p@h/db"}):
            url = get_database_url()
        assert url == "postgresql://u:p@h/db"

    def test_empty_when_env_not_set(self):
        env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        with patch.dict(os.environ, env, clear=True):
            url = get_database_url()
        assert url == ""

    def test_only_first_occurrence_replaced(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://postgres://x"}):
            url = get_database_url()
        assert url.startswith("postgresql://postgres://x")
