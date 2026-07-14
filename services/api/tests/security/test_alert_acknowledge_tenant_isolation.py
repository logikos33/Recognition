"""
Regression tests — THREAT_MODEL.md gap #1: cross-tenant write em alerts.acknowledge.

FALHA antes do fix: AlertRepository.acknowledge(alert_id) executava
`UPDATE alerts SET acknowledged = TRUE WHERE id = %s RETURNING *` — sem
`AND tenant_id = %s` — e a rota POST /api/alerts/<id>/acknowledge chamava
esse método passando só o alert_id, sem tenant_id. Qualquer usuário
autenticado de QUALQUER tenant podia marcar como reconhecido (mutar) um
alerta de outro tenant, bastando saber ou adivinhar o UUID.

PASSA após o fix: acknowledge() exige tenant_id como parâmetro obrigatório;
o SQL sempre inclui `AND tenant_id = %s`; um alerta de outro tenant nunca é
encontrado (fetchone vazio) e a rota responde 404 — mesmo padrão de
get_evidence_key, sem diferenciar "não existe" de "é de outro tenant"
(evita enumeração cross-tenant via diferença de status code, SECURITY.md).
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.alert_repository import AlertRepository


class _MockPool:
    def __init__(self) -> None:
        self.mock_cursor = MagicMock()
        self.mock_cursor.fetchone.return_value = None
        self.mock_conn = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self.mock_conn


def _make_repo() -> tuple["AlertRepository", "_MockPool"]:
    pool = _MockPool()
    return AlertRepository(pool), pool  # type: ignore[arg-type]


class TestAcknowledgeTenantIsolation:
    """acknowledge() deve exigir tenant_id para impedir mutação cross-tenant."""

    def test_requires_tenant_id_argument(self) -> None:
        """FALHA antes do fix (TypeError — sem parâmetro tenant_id). PASSA após fix."""
        repo, _ = _make_repo()
        repo.acknowledge(uuid4(), tenant_id=str(uuid4()))  # não deve lançar TypeError

    def test_sql_filters_by_tenant_id(self) -> None:
        """SQL deve conter `tenant_id = %s` — não só `id = %s`."""
        repo, pool = _make_repo()
        tenant_id = str(uuid4())
        alert_id = uuid4()

        repo.acknowledge(alert_id, tenant_id=tenant_id)

        assert pool.mock_cursor.execute.call_count == 1
        sql, params = pool.mock_cursor.execute.call_args[0]
        assert "tenant_id" in sql.lower(), "SQL de UPDATE deve filtrar por tenant_id"
        assert str(alert_id) in params
        assert tenant_id in params

    def test_tenant_b_params_never_contain_tenant_a_id(self) -> None:
        """params da mutação usam o tenant do requisitante — nunca vazam outro tenant_id."""
        repo, pool = _make_repo()
        tenant_a_id = str(uuid4())
        tenant_b_id = str(uuid4())
        alert_id = uuid4()

        repo.acknowledge(alert_id, tenant_id=tenant_b_id)

        _, params = pool.mock_cursor.execute.call_args[0]
        assert tenant_b_id in params
        assert tenant_a_id not in params

    def test_cross_tenant_alert_no_row_returns_none(self) -> None:
        """Alerta de outro tenant (ou inexistente) — UPDATE não afeta linhas → None (404 na rota)."""
        repo, pool = _make_repo()
        pool.mock_cursor.fetchone.return_value = None

        result = repo.acknowledge(uuid4(), tenant_id=str(uuid4()))

        assert result is None

    def test_own_tenant_alert_is_acknowledged(self) -> None:
        """Regressão: alerta do PRÓPRIO tenant continua sendo reconhecido normalmente."""
        repo, pool = _make_repo()
        alert_id = uuid4()
        tenant_id = str(uuid4())
        pool.mock_cursor.fetchone.return_value = {
            "id": str(alert_id), "tenant_id": tenant_id, "acknowledged": True,
        }

        result = repo.acknowledge(alert_id, tenant_id=tenant_id)

        assert result is not None
        assert result["acknowledged"] is True
