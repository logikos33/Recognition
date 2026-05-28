"""
Fixtures compartilhadas para os testes do Quality Gate.
"""
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_pool():
    """Pool de conexoes mockado com conn e cursor prontos."""
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = None
    cur.fetchall.return_value = []
    conn.__enter__ = lambda s: conn
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    pool.get_connection.return_value = conn
    return pool, conn, cur


@pytest.fixture
def mock_redis():
    """Cliente Redis mockado."""
    r = MagicMock()
    r.publish.return_value = 1
    return r
