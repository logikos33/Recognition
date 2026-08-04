"""Tests: logging_config — split stdout/stderr por severidade + silêncio do
access log nativo do worker gevent/geventwebsocket.

Contexto (log de produção 04/08): antes desta mudança TODO log saía por
stderr (StreamHandler() sem stream= usa stderr por padrão), o que faz
Railway marcar tudo como [err] e inutiliza qualquer filtro por severidade no
dashboard. Este arquivo cobre:
  - INFO/DEBUG → stdout, WARNING+ → stderr (sem duplicar entre as duas)
  - idempotência de configure_text_logging (mesmo padrão de
    configure_json_logging em tests/unit/test_sentry_logging.py)
  - _silence_gevent_access_log(): silencia só o access log INFO do worker
    gevent, preservando warnings/erros do mesmo módulo
"""
import io
import logging

from app.core.logging_config import (
    _SPLIT_HANDLER_MARKER,
    _build_split_handlers,
    _silence_gevent_access_log,
    configure_text_logging,
)


class TestSplitStreamHandlers:
    """INFO/DEBUG → stdout, WARNING+ → stderr, cada record em exatamente um dos dois."""

    def setup_method(self) -> None:
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        formatter = logging.Formatter("%(levelname)s %(message)s")
        self.stdout_handler, self.stderr_handler = _build_split_handlers(formatter, logging.DEBUG)
        # Troca só o alvo físico pelos buffers de teste — mantém o setLevel/filter reais.
        self.stdout_handler.stream = self.stdout
        self.stderr_handler.stream = self.stderr

        self.logger = logging.getLogger("test.logging_config.split")
        self.logger.propagate = False
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.stdout_handler)
        self.logger.addHandler(self.stderr_handler)

    def teardown_method(self) -> None:
        self.logger.removeHandler(self.stdout_handler)
        self.logger.removeHandler(self.stderr_handler)

    def test_info_goes_to_stdout_only(self) -> None:
        self.logger.info("informational line")
        assert "informational line" in self.stdout.getvalue()
        assert "informational line" not in self.stderr.getvalue()

    def test_debug_goes_to_stdout_only(self) -> None:
        self.logger.debug("debug line")
        assert "debug line" in self.stdout.getvalue()
        assert "debug line" not in self.stderr.getvalue()

    def test_warning_goes_to_stderr_only(self) -> None:
        self.logger.warning("warning line")
        assert "warning line" in self.stderr.getvalue()
        assert "warning line" not in self.stdout.getvalue()

    def test_error_goes_to_stderr_only(self) -> None:
        self.logger.error("error line")
        assert "error line" in self.stderr.getvalue()
        assert "error line" not in self.stdout.getvalue()

    def test_no_duplicate_across_streams(self) -> None:
        self.logger.warning("single warning")
        assert self.stdout.getvalue().count("single warning") == 0
        assert self.stderr.getvalue().count("single warning") == 1


class TestConfigureTextLoggingIdempotent:
    """Mesmo padrão de test_configure_json_logging_idempotent (test_sentry_logging.py)."""

    def setup_method(self) -> None:
        root = logging.getLogger()
        self._pre_existing = [h for h in root.handlers if getattr(h, _SPLIT_HANDLER_MARKER, False)]
        for h in self._pre_existing:
            root.removeHandler(h)

    def teardown_method(self) -> None:
        root = logging.getLogger()
        for h in [h for h in root.handlers if getattr(h, _SPLIT_HANDLER_MARKER, False)]:
            root.removeHandler(h)
        for h in self._pre_existing:
            root.addHandler(h)

    def test_first_call_adds_stdout_and_stderr_handlers(self) -> None:
        root = logging.getLogger()
        configure_text_logging()
        added = [h for h in root.handlers if getattr(h, _SPLIT_HANDLER_MARKER, False)]
        assert len(added) == 2

    def test_second_call_does_not_duplicate(self) -> None:
        root = logging.getLogger()
        configure_text_logging()
        after_first = len([h for h in root.handlers if getattr(h, _SPLIT_HANDLER_MARKER, False)])

        configure_text_logging()
        after_second = len([h for h in root.handlers if getattr(h, _SPLIT_HANDLER_MARKER, False)])

        assert after_second == after_first


class TestSilenceGeventAccessLog:
    """Silencia SÓ o access log (INFO) de geventwebsocket.handler — não os
    warnings/erros do handshake WebSocket."""

    def teardown_method(self) -> None:
        logging.getLogger("geventwebsocket.handler").setLevel(logging.NOTSET)

    def test_sets_level_to_warning(self) -> None:
        gevent_logger = logging.getLogger("geventwebsocket.handler")
        gevent_logger.setLevel(logging.NOTSET)

        _silence_gevent_access_log()

        assert gevent_logger.level == logging.WARNING

    def test_access_log_info_suppressed_but_warning_kept(self) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))

        gevent_logger = logging.getLogger("geventwebsocket.handler")
        gevent_logger.handlers.clear()
        gevent_logger.propagate = False
        gevent_logger.addHandler(handler)

        _silence_gevent_access_log()

        gevent_logger.info('100.64.0.11 - - "GET /streams/1/stream.m3u8 HTTP/1.1" 200 588 0.0625')
        gevent_logger.warning("Bad server protocol in headers")

        output = stream.getvalue()
        assert "GET /streams" not in output, "access log (INFO) deve ficar mudo"
        assert "Bad server protocol" in output, "warnings do módulo continuam visíveis"

        gevent_logger.removeHandler(handler)
