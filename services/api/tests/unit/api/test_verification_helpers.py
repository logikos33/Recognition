"""
Tests: verification.py helper functions — _call_claude, _update_alert_verification (item-24).

Não testa o Celery task wrapper — apenas a lógica de negócio dos helpers.

Import-order note: test_socket_bridge.py force-sets
sys.modules["app.infrastructure.queue.tasks.verification"] to a MagicMock stub
at module-collection time so it can import socket_bridge. We capture the real
function references here at collection time (before the stub overwrites
sys.modules) and use patch.object() to patch attributes directly on the real
module — bypassing sys.modules lookups entirely.

Histórico: este arquivo injetava MagicMock em sys.modules["celery"] (permanente)
alegando que celery não estava instalado no venv da api — obsoleto (celery é
dependência real hoje) e DANOSO: como unit/api é coletado primeiro, todo módulo
de task importado depois nascia decorado por mocks (mock.Celery().task()...),
quebrando testes de dispatch. Import real, sem stubs.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import app.infrastructure.queue.tasks.verification as _verification_mod
_real_call_claude = _verification_mod._call_claude
_real_update_alert = _verification_mod._update_alert_verification
_real_verify_alert = _verification_mod.verify_alert


class TestCallClaude:

    def _call(self, **kwargs):
        # Use the captured real function — immune to sys.modules overwrites.
        return _real_call_claude(**{"camera_id": "cam-1", "class_name": "no_helmet",
                                    "confidence": 0.75, "module_code": "epi", **kwargs})

    def test_no_api_key_returns_needs_human(self):
        with patch.object(_verification_mod, "_ANTHROPIC_KEY", ""):
            result = self._call()
        assert result["verdict"] == "needs_human"
        assert "adjusted_confidence" in result

    def test_success_parses_json_response(self):
        import json
        mock_msg = MagicMock()
        mock_msg.content[0].text = json.dumps({
            "verdict": "approve",
            "reason": "Confiança alta",
            "adjusted_confidence": 0.85,
        })
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch.object(_verification_mod, "_ANTHROPIC_KEY", "sk-fake"), \
             patch.dict("sys.modules", {"anthropic": MagicMock(Anthropic=MagicMock(return_value=mock_client))}):
            result = self._call()

        assert result["verdict"] == "approve"
        assert result["reason"] == "Confiança alta"
        assert result["adjusted_confidence"] == 0.85

    def test_json_parse_error_returns_needs_human(self):
        mock_msg = MagicMock()
        mock_msg.content[0].text = "not valid json at all"
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch.object(_verification_mod, "_ANTHROPIC_KEY", "sk-fake"), \
             patch.dict("sys.modules", {"anthropic": MagicMock(Anthropic=MagicMock(return_value=mock_client))}):
            result = self._call()

        assert result["verdict"] == "needs_human"

    def test_api_exception_returns_needs_human(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API timeout")

        with patch.object(_verification_mod, "_ANTHROPIC_KEY", "sk-fake"), \
             patch.dict("sys.modules", {"anthropic": MagicMock(Anthropic=MagicMock(return_value=mock_client))}):
            result = self._call()

        assert result["verdict"] == "needs_human"

    def test_response_defaults_injected_when_missing(self):
        import json
        mock_msg = MagicMock()
        mock_msg.content[0].text = json.dumps({})  # missing all keys
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch.object(_verification_mod, "_ANTHROPIC_KEY", "sk-fake"), \
             patch.dict("sys.modules", {"anthropic": MagicMock(Anthropic=MagicMock(return_value=mock_client))}):
            result = self._call(confidence=0.65)

        assert result["verdict"] == "needs_human"
        assert result["reason"] == ""
        assert result["adjusted_confidence"] == 0.65


class TestUpdateAlertVerification:

    def _update(self, verdict, tenant_id="tenant-1", **kwargs):
        _real_update_alert(
            alert_id=str(uuid4()),
            verdict=verdict,
            reason="test",
            confidence=0.8,
            tenant_id=tenant_id,
            **kwargs,
        )

    # _update_alert_verification does `from app.infrastructure.database.connection import DatabasePool`
    # inside the function body (lazy import). Patch at the source module, not at verification.
    _POOL_PATH = "app.infrastructure.database.connection.DatabasePool"

    def _mock_pool(self):
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        # Simulate context manager: `with pool.get_connection() as conn:`
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=mock_conn)
        cm.__exit__ = MagicMock(return_value=False)
        mock_pool.get_connection.return_value = cm
        return mock_pool, mock_cursor

    def test_approve_maps_to_auto_approved(self):
        mock_pool, mock_cursor = self._mock_pool()
        with patch(self._POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            self._update("approve")

        mock_cursor.execute.assert_called_once()
        params = mock_cursor.execute.call_args[0][1]
        assert "auto_approved" in params
        assert "approve" in params  # verification_verdict: terminal, grava normalmente

    def test_reject_maps_to_auto_rejected(self):
        mock_pool, mock_cursor = self._mock_pool()
        with patch(self._POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            self._update("reject")

        params = mock_cursor.execute.call_args[0][1]
        assert "auto_rejected" in params
        assert "reject" in params  # verification_verdict: terminal, grava normalmente

    def test_needs_human_maps_status_mas_NAO_grava_verdict(self):
        """Gate (achado do cético, rodada 2 do contrato A1): `needs_human` é
        estado de TRIAGEM, não veredito terminal. A query é
        `SET verification_status=%s, verification_verdict=%s, ...` — o
        SEGUNDO param (índice 1, o que a fila `verdict IS NULL` lê) tem que
        ficar NULL. Se gravasse a string 'needs_human' ali, no dia em que a
        triagem por IA voltar a concluir, todo alerta que ela manda pro
        humano ganharia `verification_verdict` NOT NULL e SUMIRIA da fila
        honesta — exatamente o que ela deveria mostrar."""
        mock_pool, mock_cursor = self._mock_pool()
        with patch(self._POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            self._update("needs_human")

        query, params = mock_cursor.execute.call_args[0]
        assert "verification_status = %s, verification_verdict = %s" in query
        assert params[0] == "needs_human"  # verification_status: estado de triagem
        assert params[1] is None  # verification_verdict: NUNCA 'needs_human'

    def test_pool_none_returns_silently(self):
        with patch(self._POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            self._update("approve")  # should not raise

    def test_db_exception_is_silenced(self):
        with patch(self._POOL_PATH) as pool_cls:
            pool_cls.get_instance.side_effect = Exception("pool error")
            self._update("approve")  # should not raise

    def test_where_qualifica_tenant_id(self):
        """Achado do cético: o UPDATE só tinha `WHERE id = %s` — um
        `alert_id` de outro tenant era gravável por esta task (C-01)."""
        mock_pool, mock_cursor = self._mock_pool()
        with patch(self._POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            self._update("approve", tenant_id="tenant-42")

        query, params = mock_cursor.execute.call_args[0]
        assert "WHERE id = %s AND tenant_id = %s" in query
        assert params[-1] == "tenant-42"

    def test_sem_tenant_id_nao_grava_nada(self):
        """Sem tenant não há WHERE seguro: `tenant_id = NULL` no SQL nunca
        bate nenhuma linha (semântica de NULL) — pular é mais seguro que
        arriscar um UPDATE sem escopo de tenant."""
        mock_pool, mock_cursor = self._mock_pool()
        with patch(self._POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            self._update("approve", tenant_id=None)

        mock_pool.get_connection.assert_not_called()
        mock_cursor.execute.assert_not_called()


class TestVerifyAlertPropagaTenantId:
    """`verify_alert` (a task Celery) precisa repassar `tenant_id` para
    `_update_alert_verification` — sem isso o gate/escopo em
    TestUpdateAlertVerification fica sem efeito prático: ninguém chamaria com
    tenant de verdade."""

    def test_verify_alert_passa_tenant_id_para_o_update(self):
        with patch.object(
            _verification_mod, "_call_claude",
            return_value={"verdict": "approve", "reason": "ok", "adjusted_confidence": 0.9},
        ), patch.object(_verification_mod, "_update_alert_verification") as mock_update:
            _real_verify_alert(
                alert_id="a-1", camera_id="c-1", class_name="Sem Luvas",
                confidence=0.9, tenant_id="tenant-7", module_code="epi",
            )
        assert mock_update.call_args.kwargs["tenant_id"] == "tenant-7"

    def test_verify_alert_propaga_tenant_id_tambem_no_caminho_de_erro(self):
        with patch.object(_verification_mod, "_call_claude", side_effect=RuntimeError("boom")), \
             patch.object(_verification_mod, "_update_alert_verification") as mock_update:
            try:
                _real_verify_alert(
                    alert_id="a-1", camera_id="c-1", class_name="Sem Luvas",
                    confidence=0.9, tenant_id="tenant-7", module_code="epi",
                )
            except Exception:
                pass  # retry/propagação não é o que este teste cobre
        assert mock_update.call_args[0][-1] == "tenant-7"
