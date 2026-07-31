"""Redação de credencial em texto que vai pra log ou mensagem de erro.

Gêmeo de `services/api/app/core/redact.py`. Duplicado, não importado, pelo
mesmo motivo já documentado em `onvif_recorder_client.py` (C-04): `services/api`
e `services/edge-sync-agent` são processos com deploy e requirements
independentes, e o único pacote compartilhado (`recognition_shared`) só tem DTO
pydantic, sem lógica.

Motivo (achado real no DEV, 2026-07-31): o ffmpeg ecoa a URL de entrada inteira
quando falha em conectar, com a senha do gravador do cliente em texto puro. O
módulo original já tomava o cuidado de nunca interpolar a URL nas mensagens —
mas o `stderr` do ffmpeg carrega a URL por conta própria, e ia direto pro log.
"""

from __future__ import annotations

import re

_URL_USERINFO = re.compile(
    r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)"
    r"(?P<user>[^:/?#\[\]@\s]+)"
    r":(?P<secret>[^/?#\[\]@\s]*)"
    r"(?P<at>@)"
)

_REDACTED = "***"


def redact_url_credentials(text: str) -> str:
    """Troca a senha de qualquer URL com userinfo por `***`.

    Preserva o usuário: útil pra diagnóstico ("o login está errado?") e não é
    o segredo. Texto sem URL passa intacto.
    """
    if not text:
        return text
    return _URL_USERINFO.sub(
        lambda m: f"{m.group('scheme')}{m.group('user')}:{_REDACTED}{m.group('at')}",
        text,
    )


def redact_bytes(raw: bytes, encoding: str = "utf-8") -> str:
    """Decodifica e redige — atalho pra stderr de subprocesso."""
    if not raw:
        return ""
    return redact_url_credentials(raw.decode(encoding, errors="replace"))
