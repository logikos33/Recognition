"""Logging JSON estruturado sem PII — Recognition Platform.

Expõe JsonFormatter para configuração via basicConfig ou addHandler.
Redacta automaticamente valores em campos sensíveis (C-05).

Também centraliza a separação por severidade (INFO/DEBUG → stdout,
WARNING+ → stderr — ver configure_json_logging/configure_text_logging) e o
silêncio do access log nativo do worker gevent/geventwebsocket (ver
_silence_gevent_access_log), consolidados aqui porque ambos mexem em
handlers/loggers globais no boot da app.
"""
from __future__ import annotations

import json
import logging
import sys


_REDACTED_KEYS = frozenset(
    {"token", "public_key", "public_key_pem", "fingerprint", "password", "secret", "api_key"}
)

# Standard LogRecord instance attributes — never copy these as "extra" fields.
_STANDARD_RECORD_FIELDS = frozenset({
    "name", "msg", "args", "created", "filename", "funcName",
    "levelname", "levelno", "lineno", "message", "module",
    "msecs", "pathname", "process", "processName", "relativeCreated",
    "stack_info", "thread", "threadName", "exc_info", "exc_text",
    "asctime", "taskName",
})


class JsonFormatter(logging.Formatter):
    """Formatter que emite cada log como uma linha JSON parseável.

    - Redacta campos extras com nomes sensíveis (C-05: sem PII/segredos no log).
    - Inclui: level, logger, message, ts (e exc_info se presente).
    - Trunca tenant_id/site_id a 8 chars se presentes como extra (ofuscação leve).
    """

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "ts": self.formatTime(record, self.datefmt),
        }

        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)

        # Copy extra fields set via logger.info(..., extra={...}), redacting sensitive keys.
        for key, val in record.__dict__.items():
            if key.startswith("_") or key in _STANDARD_RECORD_FIELDS:
                continue
            if key in _REDACTED_KEYS:
                entry[key] = "[REDACTED]"
            elif key in ("tenant_id", "site_id") and isinstance(val, str) and len(val) > 8:
                entry[key] = val[:8] + "..."
            else:
                entry[key] = val

        return json.dumps(entry, default=str)


class _BelowLevelFilter(logging.Filter):
    """Deixa passar só records com level < max_level.

    Usado no handler de stdout para não duplicar em stdout o que já sai em
    stderr (cada record vai para exatamente UM dos dois handlers).
    """

    def __init__(self, max_level: int) -> None:
        super().__init__()
        self._max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self._max_level


# Marker attribute — identifica os handlers criados por este módulo, para as
# checagens de idempotência em configure_json_logging/configure_text_logging
# (não dá pra confiar só em isinstance(handler.formatter, ...) no caso texto,
# já que logging.Formatter não é uma classe exclusiva nossa).
_SPLIT_HANDLER_MARKER = "_epi_split_stream_handler"


def _build_split_handlers(
    formatter: logging.Formatter, level: int
) -> tuple[logging.Handler, logging.Handler]:
    """stdout leva INFO/DEBUG, stderr leva WARNING+.

    Railway (e a maioria dos coletores de log de container) trata TUDO que
    sai em stderr como [err] — inclusive INFO. Antes desta função, o app
    mandava tudo para stderr (StreamHandler() sem stream= usa stderr por
    padrão), o que inutilizava qualquer filtro por severidade no dashboard.
    Duas streams físicas resolvem isso sem precisar mudar o coletor.
    """
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.addFilter(_BelowLevelFilter(logging.WARNING))
    stdout_handler.setFormatter(formatter)
    setattr(stdout_handler, _SPLIT_HANDLER_MARKER, True)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)
    setattr(stderr_handler, _SPLIT_HANDLER_MARKER, True)

    return stdout_handler, stderr_handler


def _silence_gevent_access_log() -> None:
    """Silencia SÓ o access log do worker WebSocket (gevent), preservando
    warnings/erros do mesmo módulo (handshake inválido, protocolo não
    suportado etc.).

    Em produção o SERVICE_TYPE=api roda com
    geventwebsocket.gunicorn.workers.GeventWebSocketWorker (ver
    railway_start.py), cujo WebSocketHandler herda de gevent.pywsgi.WSGIHandler
    puro — NÃO de gunicorn.workers.ggevent.PyWSGIHandler. Ou seja, ele
    NUNCA passa pelo `--access-logfile` do gunicorn; loga cada requisição via
    `logging.getLogger("geventwebsocket.handler").info(...)` direto (ver
    geventwebsocket/handler.py:WebSocketHandler.log_request/logger), e essa
    linha propaga pro root logger e duplica a de app.core.middleware.

    Como o processo gunicorn é substituído via os.execvp em railway_start.py
    (troca a imagem do processo inteira), a ÚNICA janela onde um setLevel
    aqui tem efeito é dentro do próprio processo do worker — ou seja, durante
    create_app() (chamado por gunicorn ao importar `app:create_app()`). Por
    isso mora aqui, não em railway_start.py.

    setLevel(WARNING) não desliga o logger: handshake WebSocket malformado,
    protocolo não suportado etc. continuam sendo logados (WARNING) — só a
    linha de access log (INFO) some.
    """
    logging.getLogger("geventwebsocket.handler").setLevel(logging.WARNING)


def configure_json_logging(level: int = logging.INFO) -> None:
    """Configura o root logger para emitir JSON, com INFO/DEBUG em stdout e
    WARNING+ em stderr.

    Chamado pelo create_app quando LOG_JSON=true (ou em produção).
    Idempotente: se o root logger já tiver os handlers split, não adiciona de novo.
    """
    root = logging.getLogger()
    if any(
        isinstance(h.formatter, JsonFormatter) and getattr(h, _SPLIT_HANDLER_MARKER, False)
        for h in root.handlers
    ):
        return  # já configurado

    stdout_handler, stderr_handler = _build_split_handlers(JsonFormatter(), level)
    root.setLevel(level)
    root.addHandler(stdout_handler)
    root.addHandler(stderr_handler)
    _silence_gevent_access_log()


def configure_text_logging(level: int = logging.INFO) -> None:
    """Equivalente texto de configure_json_logging (dev/test, LOG_JSON não setada).

    Mesmo split por severidade: INFO/DEBUG → stdout, WARNING+ → stderr.
    Idempotente, mesmo padrão de configure_json_logging.
    """
    root = logging.getLogger()
    if any(getattr(h, _SPLIT_HANDLER_MARKER, False) for h in root.handlers):
        return  # já configurado

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    stdout_handler, stderr_handler = _build_split_handlers(formatter, level)
    root.setLevel(level)
    root.addHandler(stdout_handler)
    root.addHandler(stderr_handler)
    _silence_gevent_access_log()
