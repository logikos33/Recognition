"""Logging JSON estruturado sem PII — Recognition Platform.

Expõe JsonFormatter para configuração via basicConfig ou addHandler.
Redacta automaticamente valores em campos sensíveis (C-05).
"""
from __future__ import annotations

import json
import logging


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


def configure_json_logging(level: int = logging.INFO) -> None:
    """Configura o root logger para emitir JSON.

    Chamado pelo create_app quando LOG_JSON=true (ou em produção).
    Idempotente: se o root logger já tiver um JsonFormatter, não adiciona outro.
    """
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler.formatter, JsonFormatter):
            return  # já configurado

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.setLevel(level)
    root.addHandler(handler)
