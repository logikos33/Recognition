"""Redação de credencial na FRONTEIRA do log — não em cada chamador.

`redact.py` (`redact_url_credentials`) já existe e é aplicado em 3
call-sites hoje (stderr de ffmpeg em `rtsp_clip_stream.py`,
`rtsp_frame_capture.py`, `live_view/hls_transcoder.py`). Esses call-sites
ficam como estão — defesa em profundidade. Mas um chamador pode sempre
esquecer de aplicar a função, e o caso mais perigoso nem passa por
call-site nenhum: uma exceção de conexão RTSP frequentemente carrega a URL
inteira (com senha) na própria mensagem, e o traceback dela vai pro log
sem que ninguém tenha interpolado nada manualmente — inclusive exceção NÃO
capturada, que mata o processo e escreve o traceback cru em stderr antes de
qualquer call-site rodar.

Este módulo resolve isso na saída: um `logging.Formatter` que redige o
texto já formatado (mensagem + args + traceback de `exc_info`, tudo numa
passada só, porque nesse ponto já virou string) instalado no handler do
root logger, mais `sys.excepthook`/`threading.excepthook` que roteiam
qualquer exceção não capturada pelo mesmo logging já redigido — em vez de
cair no default do interpretador, que escreve traceback cru em stderr.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import traceback
from typing import Any

from .redact import redact_url_credentials

# Nunca o texto cru em caso de falha na própria redação — vazar é pior do
# que perder a linha de log.
_SUPPRESSED = "[log suprimido: falha na redação]"

# Mesmo format string usado hoje em todos os entrypoints via
# `logging.basicConfig(level=..., format="%(asctime)s %(levelname)s %(name)s %(message)s")`.
DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

_UNCAUGHT_LOGGER_NAME = "app.uncaught"


class RedactingFormatter(logging.Formatter):
    """`logging.Formatter` que redige credencial de URL no texto já formatado.

    Rodar a redação DEPOIS do `Formatter.format()` padrão é o que garante
    cobertura completa numa passada só: mensagem, `%`-args interpolados E o
    traceback de `exc_info` (quando o record carrega uma exceção) — tudo já
    virou uma única string nesse ponto.

    Nunca levanta: uma falha na formatação ou na redação nunca pode derrubar
    o logging (isso aconteceria bem no meio de um incidente, e o handler de
    erro padrão do `logging` pode inclusive ecoar o texto cru na tentativa
    de reportar o problema). Em qualquer falha, devolve um placeholder fixo
    — nunca o texto original não redigido.
    """

    def format(self, record: logging.LogRecord) -> str:
        try:
            formatted = super().format(record)
            return redact_url_credentials(formatted)
        except Exception:  # noqa: BLE001 — intencional: nunca propagar
            return _SUPPRESSED


def _safe_report(origin: str, exc_type: Any, exc_value: Any, exc_tb: Any) -> None:
    """Loga uma exceção não capturada pelo pipeline de logging (redigido).

    Nunca levanta. Monta o traceback formatado e loga via
    `logging.getLogger(...).error(...)` — a redação em si acontece no
    `RedactingFormatter` do handler instalado por `install_redacted_logging`,
    então aqui só precisamos entregar o texto ao logger com segurança.
    """
    try:
        formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    except Exception:  # noqa: BLE001
        formatted = _SUPPRESSED
    try:
        logging.getLogger(_UNCAUGHT_LOGGER_NAME).error(
            "%s: exceção não capturada\n%s", origin, formatted
        )
    except Exception:  # noqa: BLE001
        pass  # o próprio logging está quebrado — não há mais nada seguro a fazer


def _excepthook(exc_type: type[BaseException], exc_value: BaseException, exc_tb: Any) -> None:
    """Substitui `sys.excepthook`. Preserva o comportamento padrão pra
    `KeyboardInterrupt` (Ctrl-C não deveria virar um ERROR no log)."""
    try:
        if exc_type is not None and issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
    except Exception:  # noqa: BLE001
        pass
    _safe_report("sys.excepthook", exc_type, exc_value, exc_tb)


def _threading_excepthook(args: threading.ExceptHookArgs) -> None:
    """Substitui `threading.excepthook`. Preserva o comportamento padrão de
    ignorar `SystemExit` (mesma checagem que o default do stdlib faz)."""
    try:
        if args.exc_type is not None and issubclass(args.exc_type, SystemExit):
            return
    except Exception:  # noqa: BLE001
        pass
    thread_name = getattr(args.thread, "name", None) or "?"
    _safe_report(
        f"threading.excepthook[{thread_name}]", args.exc_type, args.exc_value, args.exc_traceback
    )


def install_redacted_logging(level: str | None = None) -> None:
    """Equivalente ao `logging.basicConfig(level=os.environ.get("LOG_LEVEL",
    "INFO"), format=DEFAULT_FORMAT)` usado hoje em todos os entrypoints do
    agente, mas com um handler cujo formatter é `RedactingFormatter` — cobre
    a saída inteira (mensagem, args, traceback) numa fronteira só, sem
    depender de cada chamador lembrar de redigir manualmente.

    Também instala `sys.excepthook` e `threading.excepthook`: o caso mais
    perigoso é justamente a exceção NÃO capturada, cujo traceback (erro de
    conexão RTSP costuma trazer a URL com a senha inteira) iria direto pro
    stderr cru do default do interpretador.

    Idempotente: chamar de novo (comum em testes, ou processos que
    reiniciam subsistemas) não empilha um segundo handler no root logger —
    a checagem é "já existe um handler com RedactingFormatter?", não uma
    flag de módulo, então também se autocorrige se algo removeu o handler.
    """
    resolved_level = level if level is not None else os.environ.get("LOG_LEVEL", "INFO")
    root = logging.getLogger()

    has_redacting_handler = any(
        isinstance(getattr(handler, "formatter", None), RedactingFormatter)
        for handler in root.handlers
    )
    if not has_redacting_handler:
        handler = logging.StreamHandler()
        handler.setFormatter(RedactingFormatter(DEFAULT_FORMAT))
        root.addHandler(handler)

    root.setLevel(resolved_level)

    sys.excepthook = _excepthook
    threading.excepthook = _threading_excepthook
