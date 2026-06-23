"""
Regression tests — P0-03: list_with_filters cross-tenant IDOR.

FALHA antes do fix: list_with_filters() não aceitava tenant_id e nunca
filtrava por tenant — qualquer usuário autenticado podia listar alertas de
todos os tenants (IDOR ativo via GET /api/alerts e GET /api/alerts/export).

PASSA após o fix: tenant_id é primeiro parâmetro obrigatório; SQL sempre
inclui AND a.tenant_id = %s como primeira condição real.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.alert_repository import AlertRepository


class _MockPool:
    def __init__(self) -> None:
        self.mock_cursor = MagicMock()
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = {"count": 0}
        self.mock_conn = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self.mock_conn

    def reset(self) -> None:
        self.mock_cursor.reset_mock()
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = {"count": 0}


def _make_repo() -> tuple["AlertRepository", "_MockPool"]:
    pool = _MockPool()
    return AlertRepository(pool), pool  # type: ignore[arg-type]


class TestListWithFiltersTenantIsolation:
    """
    P0-03 — list_with_filters deve obrigar tenant_id para impedir cross-tenant IDOR.

    Antes do fix: list_with_filters() sem parâmetro tenant_id →
      nenhum filtro de tenant no SQL → todos os alertas de todos os tenants expostos.
    Após o fix: tenant_id é obrigatório; SQL contém a.tenant_id = %s.
    """

    def test_requires_tenant_id_argument(self) -> None:
        """FALHA antes do fix (TypeError — sem parâmetro tenant_id). PASSA após fix."""
        repo, _ = _make_repo()
        # Antes do fix: TypeError — got an unexpected keyword argument 'tenant_id'
        repo.list_with_filters(tenant_id=str(uuid4()))  # não deve lançar exceção

    def test_sql_count_contains_tenant_filter(self) -> None:
        """Consulta COUNT deve conter a.tenant_id = %s para isolamento correto."""
        repo, pool = _make_repo()
        tenant_id = str(uuid4())

        repo.list_with_filters(tenant_id=tenant_id)

        # list_with_filters faz 2 queries: COUNT e SELECT items
        assert pool.mock_cursor.execute.call_count >= 1
        count_call = pool.mock_cursor.execute.call_args_list[0]
        sql, params = count_call[0]
        assert "tenant_id" in sql.lower(), "SQL COUNT deve filtrar por tenant_id"
        assert tenant_id in params, "tenant_id deve estar nos params do COUNT"

    def test_sql_items_contains_tenant_filter(self) -> None:
        """Consulta de items deve conter a.tenant_id = %s."""
        repo, pool = _make_repo()
        tenant_id = str(uuid4())

        repo.list_with_filters(tenant_id=tenant_id)

        assert pool.mock_cursor.execute.call_count >= 2
        items_call = pool.mock_cursor.execute.call_args_list[1]
        sql, params = items_call[0]
        assert "tenant_id" in sql.lower(), "SQL items deve filtrar por tenant_id"
        assert tenant_id in params, "tenant_id deve estar nos params dos items"

    def test_tenant_b_cannot_read_tenant_a_alerts(self) -> None:
        """tenant_b_id nos params; tenant_a_id ausente — isolamento no DB."""
        repo, pool = _make_repo()
        tenant_a_id = str(uuid4())
        tenant_b_id = str(uuid4())

        repo.list_with_filters(tenant_id=tenant_b_id)

        for call in pool.mock_cursor.execute.call_args_list:
            _, params = call[0]
            assert tenant_b_id in str(params), "tenant_b_id deve estar nos params"
            assert tenant_a_id not in str(params), "tenant_a_id NÃO deve vazar nos params"

    def test_tenant_id_is_first_real_condition(self) -> None:
        """tenant_id deve ser a primeira condição real (após 1=1)."""
        repo, pool = _make_repo()
        tenant_id = str(uuid4())

        repo.list_with_filters(tenant_id=tenant_id)

        count_call = pool.mock_cursor.execute.call_args_list[0]
        sql = count_call[0][0].lower()
        params = count_call[0][1]
        assert "tenant_id" in sql
        # tenant_id deve ser o primeiro param (índice 0) na tupla
        assert params[0] == tenant_id, "tenant_id deve ser o primeiro parâmetro SQL"
