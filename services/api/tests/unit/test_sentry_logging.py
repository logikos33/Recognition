"""Tests for task-014: Sentry opt-in + JSON logging estruturado.

Eval cases (spec):
  1. create_app() SEM SENTRY_DSN → não inicializa Sentry e NÃO quebra [crítico p/ CI]
  2. create_app() COM SENTRY_DSN fake → inicializa sem erro (mockar sentry_sdk.init)
  3. logging: um log do blueprint /edge sai como JSON parseável
  4. assert que token/segredo de exemplo NÃO aparece no output (REDACTED)
  5. ruff + pytest verdes
"""
from __future__ import annotations

import io
import json
import logging
import os
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Sentry opt-in
# ---------------------------------------------------------------------------

class TestSentryOptIn:

    def test_create_app_without_sentry_dsn_does_not_break(self, app):
        """Spec: sem SENTRY_DSN → no-op; app criado normalmente."""
        # `app` fixture já cria a app sem SENTRY_DSN — se chegou aqui, passou.
        assert app is not None

    def test_create_app_without_dsn_does_not_call_sentry_init(self):
        """Sem DSN, sentry_sdk.init NUNCA deve ser chamado."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SENTRY_DSN", None)

            mock_sentry = MagicMock()
            with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
                from app import _init_sentry
                _init_sentry("testing")

            mock_sentry.init.assert_not_called()

    def test_create_app_with_fake_dsn_calls_sentry_init(self):
        """Com SENTRY_DSN fake, sentry_sdk.init deve ser chamado com o DSN."""
        fake_dsn = "https://fake@sentry.io/123456"

        mock_sentry = MagicMock()
        with patch.dict(os.environ, {"SENTRY_DSN": fake_dsn}):
            with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
                from app import _init_sentry
                _init_sentry("testing")

            mock_sentry.init.assert_called_once()
            call_kwargs = mock_sentry.init.call_args
            dsn_used = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("dsn")
            assert dsn_used == fake_dsn

    def test_sentry_init_with_fake_dsn_no_pii(self):
        """send_default_pii deve ser False (C-05)."""
        fake_dsn = "https://fake@sentry.io/999"

        mock_sentry = MagicMock()
        with patch.dict(os.environ, {"SENTRY_DSN": fake_dsn}):
            with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
                from app import _init_sentry
                _init_sentry("testing")

        call_kwargs = mock_sentry.init.call_args.kwargs
        assert call_kwargs.get("send_default_pii") is False, (
            "send_default_pii deve ser False para cumprir C-05"
        )

    def test_sentry_init_failure_does_not_break_app(self):
        """Se sentry_sdk.init levantar, create_app continua sem exceção."""
        fake_dsn = "https://bad@sentry.io/0"

        mock_sentry = MagicMock()
        mock_sentry.init.side_effect = RuntimeError("sentry explodiu")

        with patch.dict(os.environ, {"SENTRY_DSN": fake_dsn}):
            with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
                from app import _init_sentry
                # Não deve levantar exceção
                _init_sentry("testing")


# ---------------------------------------------------------------------------
# JSON logging
# ---------------------------------------------------------------------------

class TestJsonLogging:

    def _get_json_handler(self) -> tuple[logging.StreamHandler, io.StringIO]:
        from app.core.logging_config import JsonFormatter
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())
        return handler, stream

    def test_edge_log_is_json_parseable(self):
        """Um log do namespace edge deve sair como JSON válido."""
        handler, stream = self._get_json_handler()

        test_logger = logging.getLogger("app.api.v1.edge.routes.test_json")
        test_logger.propagate = False
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.INFO)

        try:
            test_logger.info("edge_heartbeat: device=%s status=%s", "device-001", "healthy")
        finally:
            test_logger.removeHandler(handler)

        output = stream.getvalue().strip()
        assert output, "Log não produziu saída"

        parsed = json.loads(output)  # levanta se não for JSON válido
        assert "level" in parsed, "Campo 'level' ausente no JSON"
        assert "message" in parsed, "Campo 'message' ausente no JSON"
        assert "logger" in parsed, "Campo 'logger' ausente no JSON"
        assert parsed["level"] == "INFO"

    def test_secret_value_not_in_log_output(self):
        """C-05: valor secreto passado via extra={'token': ...} é REDACTED no log."""
        handler, stream = self._get_json_handler()
        SECRET = "SUPER_SECRET_TOKEN_12345"  # noqa: S105

        test_logger = logging.getLogger("app.api.v1.edge.routes.test_secret")
        test_logger.propagate = False
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.WARNING)

        try:
            test_logger.warning("auth attempt", extra={"token": SECRET})
        finally:
            test_logger.removeHandler(handler)

        output = stream.getvalue().strip()
        assert SECRET not in output, (
            f"Segredo '{SECRET}' NÃO deve aparecer no log (C-05)"
        )

        parsed = json.loads(output)
        assert parsed.get("token") == "[REDACTED]", (
            "Campo 'token' deve aparecer como '[REDACTED]', não com o valor real"
        )

    def test_public_key_pem_redacted(self):
        """C-05: public_key_pem passado como extra é REDACTED."""
        handler, stream = self._get_json_handler()
        FAKE_KEY = "-----BEGIN PUBLIC KEY-----\nMIIBIjAN..."  # noqa: S105

        test_logger = logging.getLogger("app.api.v1.edge.routes.test_key")
        test_logger.propagate = False
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        try:
            test_logger.debug("device enrolled", extra={"public_key_pem": FAKE_KEY})
        finally:
            test_logger.removeHandler(handler)

        output = stream.getvalue().strip()
        assert FAKE_KEY not in output
        parsed = json.loads(output)
        assert parsed.get("public_key_pem") == "[REDACTED]"

    def test_normal_fields_not_redacted(self):
        """Campos normais (site_id, status) não são redactados."""
        handler, stream = self._get_json_handler()

        test_logger = logging.getLogger("app.api.v1.edge.routes.test_normal")
        test_logger.propagate = False
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.INFO)

        try:
            test_logger.info("site ok", extra={"status": "healthy"})
        finally:
            test_logger.removeHandler(handler)

        parsed = json.loads(stream.getvalue().strip())
        assert parsed.get("status") == "healthy"

    def test_configure_json_logging_idempotent(self):
        """configure_json_logging() pode ser chamado 2x sem duplicar handlers."""
        from app.core.logging_config import JsonFormatter, configure_json_logging

        root = logging.getLogger()
        initial_json_handlers = [
            h for h in root.handlers if isinstance(h.formatter, JsonFormatter)
        ]

        configure_json_logging()
        configure_json_logging()  # segunda chamada — deve ser no-op

        final_json_handlers = [
            h for h in root.handlers if isinstance(h.formatter, JsonFormatter)
        ]

        # Não deve ter adicionado mais handlers do que o necessário
        assert len(final_json_handlers) <= len(initial_json_handlers) + 1
