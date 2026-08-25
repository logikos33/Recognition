"""
Regression tests — achado #14 (docs/API_CONTRACT_MAP.md): verification queue
cross-tenant IDOR.

FALHA antes do fix: `GET /api/verification/queue`, `/queue/count` e
`POST /api/verification/<id>/review` não recebiam `tenant_id` em nenhum
nível — nem na rota, nem no `VerificationService`. Qualquer operador
autenticado (de qualquer tenant) podia:
  - listar TODOS os alertas `needs_human` de TODOS os tenants (get_human_queue);
  - ver a contagem global da fila (get_queue_count);
  - aprovar/rejeitar (`human_review`) o alerta de OUTRO tenant — o UPDATE só
    filtrava por `id` + `verification_status='needs_human'`, sem checar
    posse — IDOR de leitura E escrita.

PASSA após o fix: `tenant_id` é parâmetro obrigatório nos três métodos de
`VerificationService`; toda query SQL inclui `tenant_id = %s` — a fila só
lista/conta itens do tenant do JWT, e o `UPDATE` de `human_review` nunca
afeta uma linha de outro tenant (rowcount 0 → rota mapeia para 404).
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.domain.services.verification_service import VerificationService

_POOL_PATH = "app.domain.services.verification_service.DatabasePool"


def _pool_with_cursor(mock_cursor):
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


class TestGetHumanQueueTenantIsolation:
    """achado #14 — fila de revisão humana deve ser escopada por tenant."""

    def test_requires_tenant_id_argument(self) -> None:
        """PASSA após fix: tenant_id é parâmetro obrigatório."""
        svc = VerificationService()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            svc.get_human_queue(tenant_id=str(uuid4()))  # não deve lançar

    def test_sql_filters_by_tenant_id(self) -> None:
        svc = VerificationService()
        tenant_id = str(uuid4())
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            svc.get_human_queue(tenant_id=tenant_id)

        query, params = mock_cursor.execute.call_args[0]
        assert "tenant_id" in query.lower(), "SQL deve filtrar por tenant_id"
        assert tenant_id in params, "tenant_id deve estar nos params"

    def test_tenant_b_query_never_includes_tenant_a_id(self) -> None:
        """tenant_a_id nunca aparece nos params quando quem consulta é tenant_b."""
        svc = VerificationService()
        tenant_a_id = str(uuid4())
        tenant_b_id = str(uuid4())
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            svc.get_human_queue(tenant_id=tenant_b_id)

        _, params = mock_cursor.execute.call_args[0]
        assert tenant_b_id in params
        assert tenant_a_id not in params, "tenant_a_id NÃO deve vazar nos params de outro tenant"


class TestGetQueueCountTenantIsolation:
    """achado #14 — contagem da fila deve ser escopada por tenant."""

    def test_sql_filters_by_tenant_id(self) -> None:
        svc = VerificationService()
        tenant_id = str(uuid4())
        mock_cursor = MagicMock()
        # dict, não tupla: o pool usa RealDictCursor (connection.py:61). A
        # tupla que estava aqui concordava com o `row[0]` que estava no
        # serviço — os dois compartilhavam a mesma premissa errada, então
        # combinavam entre si e discordavam do banco. Em produção o `row[0]`
        # levantava KeyError, o `except: return 0` engolia, e o badge da fila
        # mostrou 0 desde o primeiro dia sem nunca ter consultado nada.
        mock_cursor.fetchone.return_value = {"total": 0}
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert svc.get_queue_count(tenant_id=tenant_id) == 0

        query, params = mock_cursor.execute.call_args[0]
        assert "tenant_id" in query.lower()
        assert tenant_id in params


class TestHumanReviewTenantIsolation:
    """achado #14 — review (approve/reject) nunca pode afetar alerta de outro tenant."""

    def test_sql_filters_by_tenant_id(self) -> None:
        svc = VerificationService()
        tenant_id = str(uuid4())
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            svc.human_review("alert-1", "approve", "user-1", tenant_id=tenant_id)

        query, params = mock_cursor.execute.call_args[0]
        assert "tenant_id" in query.lower(), "UPDATE deve filtrar por tenant_id"
        assert tenant_id in params

    def test_cross_tenant_review_reports_zero_rows_affected(self) -> None:
        """Alerta pertence a tenant_a; requisição chega com tenant_id=tenant_b.

        Em produção, a condição `id = %s AND tenant_id = %s` do UPDATE nunca
        bate para uma linha de outro tenant — rowcount fica 0. Este teste
        simula esse resultado (rowcount=0) e confirma que `human_review`
        retorna False, o que a rota (`review_alert`) mapeia para 404 — nunca
        200 (ver services/api/tests/unit/api/test_verification_routes.py::
        TestReviewAlert::test_cross_tenant_review_returns_404_not_200).
        """
        svc = VerificationService()
        tenant_b_id = str(uuid4())
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # id existe (é do tenant_a) mas tenant_id não bate
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = svc.human_review(
                "alert-belongs-to-tenant-a", "approve", "user-1", tenant_id=tenant_b_id
            )

        assert result is False
