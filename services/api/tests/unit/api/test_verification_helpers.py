"""
Tests: verification.py helper functions — _call_claude, _update_alert_verification (item-24).

Não testa o Celery task wrapper — apenas a lógica de negócio dos helpers.

NOTE: celery is not installed in the api venv (only in worker/inference).
We inject a MagicMock into sys.modules so the task file can be imported
without a running Celery broker — safe because we only test plain functions.

Import-order note: test_socket_bridge.py force-sets
sys.modules["app.infrastructure.queue.tasks.verification"] to a MagicMock stub
at module-collection time so it can import socket_bridge. We capture the real
function references here at collection time (before the stub overwrites
sys.modules) and use patch.object() to patch attributes directly on the real
module — bypassing sys.modules lookups entirely.
"""
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4


# Inject celery stubs before any module-level import of verification.py.
# celery is not installed in the api venv; stub out all required sub-modules.
# Force-set (not setdefault) so our stubs win regardless of collection order.
for _mod_name in ("celery", "celery.signals", "celery.app", "celery.app.base"):
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()

# Import the real module NOW, before test_socket_bridge.py can overwrite
# sys.modules["app.infrastructure.queue.tasks.verification"] with its stub.
# We hold a direct reference to the real module object and its functions so
# later sys.modules mutations cannot affect us.
import app.infrastructure.queue.tasks.verification as _verification_mod  # noqa: E402
_real_call_claude = _verification_mod._call_claude
_real_update_alert = _verification_mod._update_alert_verification


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

    def _update(self, verdict, **kwargs):
        _real_update_alert(
            alert_id=str(uuid4()),
            verdict=verdict,
            reason="test",
            confidence=0.8,
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

    def test_reject_maps_to_auto_rejected(self):
        mock_pool, mock_cursor = self._mock_pool()
        with patch(self._POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            self._update("reject")

        params = mock_cursor.execute.call_args[0][1]
        assert "auto_rejected" in params

    def test_needs_human_maps_to_needs_human(self):
        mock_pool, mock_cursor = self._mock_pool()
        with patch(self._POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            self._update("needs_human")

        params = mock_cursor.execute.call_args[0][1]
        assert "needs_human" in params

    def test_pool_none_returns_silently(self):
        with patch(self._POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            self._update("approve")  # should not raise

    def test_db_exception_is_silenced(self):
        with patch(self._POOL_PATH) as pool_cls:
            pool_cls.get_instance.side_effect = Exception("pool error")
            self._update("approve")  # should not raise
