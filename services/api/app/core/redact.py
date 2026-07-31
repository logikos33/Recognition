"""Redação de credencial em texto que vai pra log/resposta de API.

Motivo (achado real no DEV, 2026-07-31): o stderr do ffmpeg era logado cru e
despejava a senha do gravador do cliente em texto puro nos logs do Railway:

    ffmpeg_stderr: ... Error opening input file rtsp://Admin:<SENHA>@192.168.35.18:554/...

Log vaza pra todo lado — Railway, `railway logs`, print colado em chat/ticket,
export de observabilidade. Credencial de CFTV do cliente não pode passar por
nenhum desses. A regra aqui é redigir na ORIGEM (onde o texto é capturado),
não na hora de logar: assim o segredo nunca chega a existir em buffer, tail de
stderr, ou objeto de exceção que alguém possa serializar depois.
"""
from __future__ import annotations

import re

# rtsp://user:senha@host  ->  rtsp://user:***@host
# Casa qualquer esquema (rtsp/rtsps/http/https) porque o mesmo par
# usuário:senha aparece em URL de ONVIF/CGI, não só de RTSP.
_URL_USERINFO = re.compile(
    r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)"
    r"(?P<user>[^:/?#\[\]@\s]+)"
    r":(?P<secret>[^/?#\[\]@\s]*)"
    r"(?P<at>@)"
)

_REDACTED = "***"


def redact_url_credentials(text: str) -> str:
    """Troca a senha de qualquer URL com userinfo por `***`.

    Preserva o usuário de propósito: ele é útil pra diagnosticar ("o login
    está errado?") e não é o segredo. Texto sem URL passa intacto.
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
