"""
Tests: VerificationService — submit_for_verification, get_human_queue,
human_review, get_queue_count.

All DB calls go through a mocked DatabasePool; verify_alert task is stubbed
via patch.dict(sys.modules) to avoid needing celery installed.
"""
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from app.domain.services.verification_service import VerificationService

_POOL_PATH = "app.domain.services.verification_service.DatabasePool"
_VERIFICATION_MODULE = "app.infrastructure.queue.tasks.verification"


def _make_service() -> VerificationService:
    return VerificationService()


def _pool_with_cursor(mock_cursor):
    """Build a pool mock whose get_connection() yields a conn with mock_cursor."""
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


# ---------------------------------------------------------------------------
# submit_for_verification
# ---------------------------------------------------------------------------

class TestSubmitForVerification:

    def _call(self, mock_task, **kwargs):
        mock_mod = MagicMock()
        mock_mod.verify_alert = mock_task
        with patch.dict(sys.modules, {_VERIFICATION_MODULE: mock_mod}):
            _make_service().submit_for_verification(
                alert_id=kwargs.get("alert_id", "alert-1"),
                camera_id=kwargs.get("camera_id", "cam-1"),
                class_name=kwargs.get("class_name", "no_helmet"),
                confidence=kwargs.get("confidence", 0.7),
                module_code=kwargs.get("module_code", "epi"),
            )
        return mock_task

    def test_calls_verify_alert_delay(self):
        mock_task = MagicMock()
        self._call(mock_task)
        mock_task.delay.assert_called_once()

    def test_passes_correct_kwargs(self):
        mock_task = MagicMock()
        self._call(mock_task, alert_id="a-1", camera_id="c-1",
                   class_name="no_vest", confidence=0.65, module_code="epi")
        kw = mock_task.delay.call_args[1]
        assert kw["alert_id"] == "a-1"
        assert kw["camera_id"] == "c-1"
        assert kw["class_name"] == "no_vest"
        assert kw["confidence"] == 0.65
        assert kw["module_code"] == "epi"

    def test_exception_in_delay_is_swallowed(self):
        mock_task = MagicMock()
        mock_task.delay.side_effect = Exception("broker unreachable")
        # Should not raise — fire-and-forget with error logging
        self._call(mock_task)

    def test_default_module_code_is_epi(self):
        mock_task = MagicMock()
        mock_mod = MagicMock()
        mock_mod.verify_alert = mock_task
        with patch.dict(sys.modules, {_VERIFICATION_MODULE: mock_mod}):
            _make_service().submit_for_verification(
                alert_id="a", camera_id="c", class_name="no_helmet", confidence=0.5
            )
        kw = mock_task.delay.call_args[1]
        assert kw["module_code"] == "epi"


# ---------------------------------------------------------------------------
# get_human_queue
# ---------------------------------------------------------------------------

class TestGetHumanQueue:

    def test_pool_none_returns_empty(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        assert result == []

    def test_returns_list_of_dicts(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": "a1", "camera_name": "Cam A", "verification_status": "needs_human"},
        ]
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        assert len(result) == 1
        assert result[0]["id"] == "a1"

    def test_empty_fetchall_returns_empty_list(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        assert result == []

    def test_camera_id_filter_adds_param(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_human_queue(tenant_id="tenant-1", camera_id="cam-42")
        call_args = mock_cursor.execute.call_args
        query, params = call_args[0]
        assert "camera_id" in query
        assert "cam-42" in params

    def test_db_exception_returns_empty(self):
        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("DB down")
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        assert result == []

    def test_limit_passed_as_last_param(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_human_queue(tenant_id="tenant-1", limit=10)
        _, params = mock_cursor.execute.call_args[0]
        assert 10 in params

    def test_tenant_id_required_positional_or_keyword(self):
        """tenant_id agora é obrigatório — sem ele, TypeError (achado #14)."""
        with pytest.raises(TypeError):
            _make_service().get_human_queue()  # type: ignore[call-arg]

    def test_query_filters_by_tenant_id(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_human_queue(tenant_id="tenant-1")
        query, params = mock_cursor.execute.call_args[0]
        assert "a.tenant_id = %s" in query
        assert "tenant-1" in params

    def test_camera_join_uses_cameras_not_ip_cameras(self):
        """Regressão: join stale em `ip_cameras` (renomeada na migration 013)
        quebrava a query inteira contra o schema real — ver anti-padrões no
        CLAUDE.md. Deve usar `cameras`."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_human_queue(tenant_id="tenant-1")
        query, _ = mock_cursor.execute.call_args[0]
        assert "JOIN cameras " in query
        assert "ip_cameras" not in query


# ---------------------------------------------------------------------------
# human_review
# ---------------------------------------------------------------------------

class TestHumanReview:

    def test_invalid_verdict_raises_value_error(self):
        with pytest.raises(ValueError, match="verdict"):
            _make_service().human_review("alert-1", "maybe", "user-1", "tenant-1")

    def test_pool_none_raises_runtime_error(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            with pytest.raises(RuntimeError, match="Database"):
                _make_service().human_review("a-1", "approve", "u-1", "tenant-1")

    def test_approve_sets_human_approved_status(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().human_review("a-1", "approve", "u-1", "tenant-1")
        assert result is True
        params = mock_cursor.execute.call_args[0][1]
        assert "human_approved" in params

    def test_reject_sets_human_rejected_status(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().human_review("a-1", "reject", "u-1", "tenant-1")
        assert result is True
        params = mock_cursor.execute.call_args[0][1]
        assert "human_rejected" in params

    def test_no_rows_affected_returns_false(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().human_review("a-1", "approve", "u-1", "tenant-1")
        assert result is False

    def test_user_id_included_in_query_params(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().human_review("alert-xyz", "approve", "user-99", "tenant-1")
        params = mock_cursor.execute.call_args[0][1]
        assert any("user-99" in str(p) for p in params)

    def test_gate_nao_volta_a_exigir_needs_human(self):
        """FALHA se o gate voltar a `verification_status = 'needs_human'`.

        Nenhum alerta alcança esse estado: a coluna nasce `DEFAULT 'pending'`
        (migration 016) e `submit_for_verification` não tem NENHUM chamador no
        repositório. Com o gate, o veredito humano é INGRAVÁVEL e a coluna fica
        NULL em 100% das linhas — que é exatamente o estado medido no DEV
        (334/334 com `verification_verdict` NULL). C-01 continua no WHERE.
        """
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert _make_service().human_review(
                "a1", "reject", "u1", tenant_id="t1"
            ) is True
        query, _ = mock_cursor.execute.call_args[0]
        assert "needs_human" not in query
        assert "tenant_id = %s" in query

    def test_veredito_humano_carimba_prefixo_user_em_verified_by(self):
        """FALHA se o prefixo 'user:' sumir de `verified_by`.

        É a ÚNICA prova de que quem julgou foi gente: a task Celery grava o
        MESMO 'approve'/'reject' com verified_by='claude-haiku'
        (infrastructure/queue/tasks/verification.py). Sem o prefixo, a tela
        apresenta decisão de máquina como julgamento humano.
        """
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().human_review("a1", "approve", "u-42", tenant_id="t1")
        _, params = mock_cursor.execute.call_args[0]
        assert "user:u-42" in params

    def test_tenant_id_required_positional_or_keyword(self):
        """tenant_id agora é obrigatório — sem ele, TypeError (achado #14)."""
        with pytest.raises(TypeError):
            _make_service().human_review("a-1", "approve", "u-1")  # type: ignore[call-arg]

    def test_query_filters_by_tenant_id(self):
        """UPDATE deve incluir `tenant_id = %s` no WHERE — sem isso, um
        operador de um tenant podia revisar alerta de outro (achado #14)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().human_review("a-1", "approve", "u-1", "tenant-b")
        query, params = mock_cursor.execute.call_args[0]
        assert "tenant_id = %s" in query
        assert "tenant-b" in params

    def test_update_does_not_require_needs_human(self):
        """O veredito humano vale para QUALQUER alerta do tenant.

        FALHAVA antes: o WHERE terminava em
        `AND verification_status = 'needs_human'`, e como nada chama
        `submit_for_verification` nenhum alerta chega a esse status — a rota
        devolvia 404 para 100% dos alertas reais e `verification_verdict`
        ficava NULL nos 334 do shadow. O `tenant_id` NÃO pode ser afrouxado
        junto (C-01): é o que continua barrando IDOR cross-tenant.
        """
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert _make_service().human_review("a-1", "approve", "u-1", "tenant-b") is True
        query, params = mock_cursor.execute.call_args[0]
        assert "needs_human" not in query
        assert "tenant_id = %s" in query
        assert "tenant-b" in params

    def test_cross_tenant_alert_id_does_not_match_other_tenant(self):
        """tenant_a_id nunca aparece nos params quando o request é do tenant_b."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # simula: WHERE não bate pois alerta é do tenant_a
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().human_review("alert-of-tenant-a", "approve", "u-1", "tenant-b")
        _, params = mock_cursor.execute.call_args[0]
        assert "tenant-b" in params
        assert result is False


# ---------------------------------------------------------------------------
# get_queue_count
# ---------------------------------------------------------------------------

class TestGetQueueCount:

    def test_pool_none_returns_zero(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            assert _make_service().get_queue_count(tenant_id="tenant-1") == 0

    def test_returns_count_from_db(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (7,)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert _make_service().get_queue_count(tenant_id="tenant-1") == 7

    def test_fetchone_none_returns_zero(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert _make_service().get_queue_count(tenant_id="tenant-1") == 0

    def test_db_exception_returns_zero(self):
        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("DB crash")
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            assert _make_service().get_queue_count(tenant_id="tenant-1") == 0

    def test_tenant_id_required_positional_or_keyword(self):
        """tenant_id agora é obrigatório — sem ele, TypeError (achado #14)."""
        with pytest.raises(TypeError):
            _make_service().get_queue_count()  # type: ignore[call-arg]

    def test_query_filters_by_tenant_id(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_queue_count(tenant_id="tenant-b")
        query, params = mock_cursor.execute.call_args[0]
        assert "tenant_id = %s" in query
        assert "tenant-b" in params
