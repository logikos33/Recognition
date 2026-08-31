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

    def test_db_exception_sobe_em_vez_de_virar_fila_vazia(self):
        """`[]` é "fila vazia", e a tela escreve exatamente isso.

        Com a exceção engolida aqui, a rota respondia 200 e o `catch` da
        página nunca disparava: o operador lia "Nenhum alerta aguardando
        revisão humana", ia embora, e os alertas de baixa confiança ficavam
        invisíveis — com o badge repetindo 0 a cada 15s.

        O caminho honesto já existia nas duas pontas (rota com
        `except -> 500`, página com `catch`); só este `return []` impedia que
        fossem alcançados.
        """
        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("DB down")
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            with pytest.raises(Exception, match="DB down"):
                _make_service().get_human_queue(tenant_id="tenant-1")

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
# Teste de mutação: critério fantasma `needs_human` não pode voltar
#
# get_human_queue e get_queue_count filtravam por `verification_status =
# 'needs_human'`, mas essa coluna é escrita SÓ pela task Celery `verify_alert`
# (triagem por IA), que nunca conclui no worker atual. Medido no DEV, tenant
# RVB: 423 alerts, 416 `pending`, 6 `human_rejected`, 1 `human_approved`,
# 0 `needs_human`. A fila filtrava por um conjunto vazio por construção — 0
# resultados sempre, não importa quantos alertas reais existam.
#
# `_FakeDbCursor` simula o WHERE de verdade contra um fixture de alertas
# (não é MagicMock com retorno fixo): ela lê a query que o código realmente
# emitiu e aplica o filtro correspondente aos dados. Assim o teste falha de
# verdade se o WHERE regredir para `needs_human` — não é comparação de string.
# ---------------------------------------------------------------------------

class _FakeDbCursor:
    """Aplica o WHERE emitido pelo código a um fixture de alertas, como o
    Postgres faria. Não reconhece um WHERE fora dos dois esperados aqui —
    preferimos falhar alto a filtrar silenciosamente errado."""

    def __init__(self, alerts: list[dict]):
        self._alerts = alerts
        self.last_query = ""
        self.last_params = ()
        self._result: list[dict] = []

    def execute(self, query: str, params=()):
        self.last_query = query
        self.last_params = params
        if "verification_verdict IS NULL" in query:
            matches = [a for a in self._alerts if a.get("verification_verdict") is None]
        elif "verification_status = 'needs_human'" in query:
            matches = [a for a in self._alerts if a.get("verification_status") == "needs_human"]
        else:
            raise AssertionError(f"WHERE inesperado no fixture do teste: {query!r}")
        self._result = matches

    def fetchall(self):
        return [dict(a) for a in self._result]

    def fetchone(self):
        return {"total": len(self._result)}


def _rvb_like_alerts(tenant_id: str) -> list[dict]:
    """Amostra proporcional ao medido no DEV (416 pending / 6 rejected /
    1 approved / 0 needs_human), reduzida para o teste ficar legível."""
    alerts = []
    for i in range(5):
        alerts.append({
            "id": f"pending-{i}", "tenant_id": tenant_id,
            "verification_status": "pending", "verification_verdict": None,
        })
    alerts.append({
        "id": "rejected-1", "tenant_id": tenant_id,
        "verification_status": "human_rejected", "verification_verdict": "reject",
    })
    alerts.append({
        "id": "approved-1", "tenant_id": tenant_id,
        "verification_status": "human_approved", "verification_verdict": "approve",
    })
    # 0 needs_human de propósito — nunca escrito no banco real (verify_alert
    # não conclui no worker atual).
    return alerts


class TestFilaCriterioHonestoNaoENeedsHumanFantasma:

    def test_fila_devolve_alertas_pending_com_veredito_nulo(self):
        """A régua desta rodada: alertas `pending`/verdict NULL — o estado
        real de 100% dos alertas do tenant RVB hoje — têm que aparecer na
        fila. Com o critério `needs_human` antigo, este teste falha (0
        resultados) porque nenhum alerta chega a esse status."""
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"))
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        assert len(result) == 5
        assert {a["id"] for a in result} == {f"pending-{i}" for i in range(5)}
        assert all(a["verification_verdict"] is None for a in result)

    def test_fila_nao_devolve_alertas_ja_julgados(self):
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"))
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            result = _make_service().get_human_queue(tenant_id="tenant-1")
        ids = {a["id"] for a in result}
        assert "rejected-1" not in ids
        assert "approved-1" not in ids

    def test_contagem_bate_com_pending_nao_com_needs_human_vazio(self):
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"))
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            count = _make_service().get_queue_count(tenant_id="tenant-1")
        assert count == 5

    def test_query_nao_usa_mais_verification_status_needs_human(self):
        """Assinatura textual do gate: se alguém reintroduzir
        `verification_status = 'needs_human'` no WHERE, este teste falha
        mesmo sem rodar o fixture acima."""
        cursor = _FakeDbCursor(_rvb_like_alerts("tenant-1"))
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(cursor)
            _make_service().get_human_queue(tenant_id="tenant-1")
            _make_service().get_queue_count(tenant_id="tenant-1")
        assert "needs_human" not in cursor.last_query
        assert "verification_verdict IS NULL" in cursor.last_query


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
        mock_cursor.fetchone.return_value = {"total": 7}
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert _make_service().get_queue_count(tenant_id="tenant-1") == 7

    def test_fetchone_none_returns_zero(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert _make_service().get_queue_count(tenant_id="tenant-1") == 0

    def test_db_exception_sobe_em_vez_de_virar_zero(self):
        """0 é uma contagem legítima do badge — não serve de "não sei"."""
        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("DB crash")
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            with pytest.raises(Exception, match="DB crash"):
                _make_service().get_queue_count(tenant_id="tenant-1")

    def test_tenant_id_required_positional_or_keyword(self):
        """tenant_id agora é obrigatório — sem ele, TypeError (achado #14)."""
        with pytest.raises(TypeError):
            _make_service().get_queue_count()  # type: ignore[call-arg]

    def test_query_filters_by_tenant_id(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"total": 0}
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_queue_count(tenant_id="tenant-b")
        query, params = mock_cursor.execute.call_args[0]
        assert "tenant_id = %s" in query
        assert "tenant-b" in params


class TestRazaoDoVeredito:
    """A justificativa do operador é o que alimenta a recalibração de limiar.

    A rota já aceitava `reason` no corpo e o descartava em silêncio: o UPDATE
    não tinha a coluna. Provado no DEV: veredito gravado, `verification_reason`
    vazio.
    """

    def test_a_razao_vai_para_o_update(self):
        from unittest.mock import MagicMock, patch

        from app.domain.services.verification_service import VerificationService

        cur = MagicMock()
        cur.rowcount = 1
        pool = MagicMock()
        pool.get_connection.return_value.__enter__.return_value.cursor.return_value = cur

        with patch("app.domain.services.verification_service._get_pool", return_value=pool):
            VerificationService().human_review(
                alert_id="a1", verdict="reject", user_id="u1", tenant_id="t1",
                reason="a caixa pegou a luva do colega ao lado",
            )

        sql, params = cur.execute.call_args[0]
        assert "verification_reason = %s" in sql
        assert "a caixa pegou a luva do colega ao lado" in params

    def test_sem_razao_grava_nulo_nao_string_vazia(self):
        from unittest.mock import MagicMock, patch

        from app.domain.services.verification_service import VerificationService

        cur = MagicMock()
        cur.rowcount = 1
        pool = MagicMock()
        pool.get_connection.return_value.__enter__.return_value.cursor.return_value = cur

        with patch("app.domain.services.verification_service._get_pool", return_value=pool):
            VerificationService().human_review(
                alert_id="a1", verdict="approve", user_id="u1", tenant_id="t1", reason="",
            )

        _, params = cur.execute.call_args[0]
        assert None in params
