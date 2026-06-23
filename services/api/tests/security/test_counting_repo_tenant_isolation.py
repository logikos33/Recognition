"""
Regression tests — P0-05: counting_repository IDOR ativo.

FALHA antes do fix: get_session(session_id) e stop_session(session_id, counts)
sem filtro de tenant → qualquer usuário autenticado com o UUID da sessão
podia acessar/encerrar sessão de outro tenant (IDOR ativo).

PASSA após o fix: tenant_id é parâmetro obrigatório; SQL inclui
AND tenant_id = %s para get_session e stop_session.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.counting_repository import CountingRepository


class _MockPool:
    def __init__(self) -> None:
        self.mock_cursor = MagicMock()
        self.mock_cursor.fetchone.return_value = None
        self.mock_cursor.fetchall.return_value = []
        self.mock_conn = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self.mock_conn


def _make_repo() -> tuple["CountingRepository", "_MockPool"]:
    pool = _MockPool()
    return CountingRepository(pool), pool  # type: ignore[arg-type]


class TestGetSessionTenantIsolation:
    """P0-05-A — get_session deve exigir tenant_id para impedir IDOR."""

    def test_requires_tenant_id_argument(self) -> None:
        """FALHA antes do fix (TypeError — só aceitava session_id). PASSA após fix."""
        repo, _ = _make_repo()
        # Antes do fix: TypeError — takes 2 positional arguments but 3 were given
        repo.get_session(uuid4(), uuid4())  # não deve lançar exceção

    def test_sql_contains_tenant_filter(self) -> None:
        """SQL de get_session deve conter AND tenant_id = %s."""
        repo, pool = _make_repo()
        session_id = uuid4()
        tenant_id = uuid4()

        repo.get_session(session_id, tenant_id)

        sql, params = pool.mock_cursor.execute.call_args[0]
        assert "tenant_id" in sql.lower(), "SQL deve filtrar por tenant_id"
        assert str(session_id) in params
        assert str(tenant_id) in params

    def test_tenant_b_cannot_read_tenant_a_session(self) -> None:
        """tenant_b recebe None para sessão de tenant_a — sem acesso cross-tenant."""
        repo, pool = _make_repo()
        tenant_a_id = uuid4()
        tenant_b_id = uuid4()
        session_id = uuid4()

        # DB retorna None (sessão não pertence a tenant_b)
        pool.mock_cursor.fetchone.return_value = None

        result = repo.get_session(session_id, tenant_b_id)
        assert result is None, "tenant B não deve receber sessão de tenant A"

        _, params = pool.mock_cursor.execute.call_args[0]
        assert str(tenant_b_id) in params
        assert str(tenant_a_id) not in params


class TestStopSessionTenantIsolation:
    """P0-05-B — stop_session deve exigir tenant_id para impedir UPDATE cross-tenant."""

    def test_requires_tenant_id_argument(self) -> None:
        """FALHA antes do fix (TypeError — só aceitava session_id + counts). PASSA após fix."""
        repo, _ = _make_repo()
        # Antes do fix: stop_session(session_id, total_counts) sem tenant_id
        repo.stop_session(uuid4(), uuid4(), {})  # não deve lançar exceção

    def test_sql_update_contains_tenant_filter(self) -> None:
        """UPDATE de stop_session deve conter AND tenant_id = %s."""
        repo, pool = _make_repo()
        session_id = uuid4()
        tenant_id = uuid4()

        repo.stop_session(session_id, tenant_id, {"helmet": 5})

        sql, params = pool.mock_cursor.execute.call_args[0]
        assert "tenant_id" in sql.lower(), "UPDATE deve filtrar por tenant_id"
        assert str(session_id) in params
        assert str(tenant_id) in params

    def test_tenant_b_cannot_stop_tenant_a_session(self) -> None:
        """UPDATE com tenant_b_id não altera sessão de tenant_a (0 rows affected)."""
        repo, pool = _make_repo()
        tenant_a_id = uuid4()
        tenant_b_id = uuid4()
        session_id = uuid4()

        pool.mock_cursor.fetchone.return_value = None  # 0 rows → sessão não pertence ao tenant_b

        result = repo.stop_session(session_id, tenant_b_id, {})
        assert result is None, "tenant B não deve conseguir parar sessão de tenant A"

        _, params = pool.mock_cursor.execute.call_args[0]
        assert str(tenant_b_id) in params
        assert str(tenant_a_id) not in params
