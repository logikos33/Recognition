"""Tests: redação de credencial na FRONTEIRA do log (formatter + excepthooks).

`test_redact.py` cobre `redact_url_credentials()` isolada — o achado real do
DEV 2026-07-31 (stderr de ffmpeg vazando a senha do gravador). Este arquivo
cobre a camada de cima: a garantia aqui não depende de call-site nenhum
lembrar de chamar `redact_url_credentials()`, nem da exceção ser capturada —
o `RedactingFormatter` redige a saída já formatada (mensagem + traceback), e
os excepthooks garantem que até uma exceção NÃO capturada passa por ele.
"""

from __future__ import annotations

import io
import logging
import sys
import threading

import pytest

from app import logging_setup
from app.logging_setup import RedactingFormatter, install_redacted_logging

URL_FALSA = "rtsp://admin:senha-falsa-teste@192.0.2.10:554/cam"
SEGREDO = "senha-falsa-teste"


def _string_handler() -> tuple[logging.Handler, io.StringIO]:
    """Handler de teste: escreve em StringIO através do RedactingFormatter.
    Não usa caplog — caplog vê o LogRecord cru, e o que importa aqui é o
    texto JÁ FORMATADO (é aí que a redação acontece)."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(RedactingFormatter(logging_setup.DEFAULT_FORMAT))
    return handler, buf


@pytest.fixture(autouse=True)
def _isolated_root_logger():
    """Isola cada teste do estado global do root logger e dos excepthooks.

    `install_redacted_logging()` mexe nos dois, e são recursos globais do
    processo — outros módulos de teste da suíte (que exercitam entrypoints
    reais como `main()`/`run_daemon()`) também mexem neles. Sem isso, a
    ordem de execução dos testes vira parte do resultado.
    """
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    saved_excepthook = sys.excepthook
    saved_threading_excepthook = threading.excepthook

    for handler in saved_handlers:
        root.removeHandler(handler)

    yield

    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in saved_handlers:
        root.addHandler(handler)
    root.setLevel(saved_level)
    sys.excepthook = saved_excepthook
    threading.excepthook = saved_threading_excepthook


def test_message_with_url_is_redacted_user_preserved():
    handler, buf = _string_handler()
    logger = logging.getLogger("test.logging_setup.message")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    logger.info("conectando em %s", URL_FALSA)

    out = buf.getvalue()
    assert "admin:***@" in out
    assert SEGREDO not in out


def test_traceback_from_exc_info_is_redacted():
    handler, buf = _string_handler()
    logger = logging.getLogger("test.logging_setup.exc_info")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    try:
        raise ConnectionError(f"falha ao conectar em {URL_FALSA}")
    except ConnectionError:
        logger.exception("erro de conexão")

    out = buf.getvalue()
    assert "Traceback (most recent call last)" in out
    assert "admin:***@" in out
    assert SEGREDO not in out


def test_text_without_url_passes_through_unchanged():
    handler, buf = _string_handler()
    logger = logging.getLogger("test.logging_setup.plain")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    logger.info("Connection timed out")

    assert "Connection timed out" in buf.getvalue()


def test_sys_excepthook_redacts_uncaught_exception():
    handler, buf = _string_handler()
    root = logging.getLogger()
    # Pré-instala o handler de teste (já com RedactingFormatter) ANTES de
    # install_redacted_logging(): a checagem de idempotência da função vê um
    # handler com RedactingFormatter já presente e não adiciona um segundo
    # (que escreveria em sys.stderr de verdade) — toda a saída cai aqui.
    root.addHandler(handler)

    install_redacted_logging()
    assert sys.excepthook is not sys.__excepthook__

    try:
        raise ConnectionError(f"falha ao conectar em {URL_FALSA}")
    except ConnectionError:
        exc_info = sys.exc_info()

    sys.excepthook(*exc_info)

    out = buf.getvalue()
    assert "admin:***@" in out
    assert SEGREDO not in out


def test_sys_excepthook_preserves_keyboard_interrupt_default_behavior(monkeypatch):
    handler, buf = _string_handler()
    root = logging.getLogger()
    root.addHandler(handler)
    install_redacted_logging()

    calls: list[tuple] = []
    monkeypatch.setattr(sys, "__excepthook__", lambda *a: calls.append(a))

    try:
        raise KeyboardInterrupt()
    except KeyboardInterrupt:
        exc_info = sys.exc_info()

    sys.excepthook(*exc_info)

    # KeyboardInterrupt vai pro default do interpretador, não pro logging.
    assert calls == [exc_info]
    assert buf.getvalue() == ""


def test_threading_excepthook_redacts_uncaught_exception():
    handler, buf = _string_handler()
    root = logging.getLogger()
    root.addHandler(handler)

    install_redacted_logging()

    try:
        raise ConnectionError(f"falha ao conectar em {URL_FALSA}")
    except ConnectionError:
        exc_type, exc_value, exc_tb = sys.exc_info()

    args = threading.ExceptHookArgs((exc_type, exc_value, exc_tb, threading.current_thread()))
    threading.excepthook(args)

    out = buf.getvalue()
    assert "admin:***@" in out
    assert SEGREDO not in out


def test_install_redacted_logging_is_idempotent():
    # Não assume root.handlers == [] no baseline: o próprio plugin de
    # logging do pytest mantém handler(s) de captura no root durante a
    # execução do teste. O que importa é que install_redacted_logging()
    # não empilha um handler novo a cada chamada.
    root = logging.getLogger()
    baseline = len(root.handlers)

    install_redacted_logging()
    handler_count = len(root.handlers)
    assert handler_count == baseline + 1

    install_redacted_logging()
    install_redacted_logging()
    assert len(root.handlers) == handler_count


def test_redacting_formatter_never_raises_on_bad_record():
    """Um record cuja interpolação `%`-args falha não pode derrubar o
    logging nem vazar o texto cru — vira o placeholder fixo."""
    formatter = RedactingFormatter(logging_setup.DEFAULT_FORMAT)
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="valor=%d",
        args=("não é um número",),  # %d com string -> TypeError na formatação
        exc_info=None,
    )

    out = formatter.format(record)

    assert out == "[log suprimido: falha na redação]"
