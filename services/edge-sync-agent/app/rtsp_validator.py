"""RTSPUrlValidator — SSRF / command-injection guard before any URL reaches
a network client (ffmpeg subprocess or an HTTP SOAP call to the gravador).

Ported from services/api/app/core/validators.py::RTSPUrlValidator (task-091
investigation: services/edge-sync-agent cannot import app.* from the
monolith — separate deploy, separate requirements.txt — so this is a
deliberate 1:1 copy, not a shared import). Keep the two copies in sync by
hand if the validation rules ever change; see task-091 PR for the full
"port vs shared package" reasoning.

Same 5 layers as the monolith original: size cap, dangerous-character
blocklist, scheme allowlist, hostname required + IP-class rejection
(loopback/link-local/multicast/reserved/unspecified), port range.
"""

from __future__ import annotations

import ipaddress
import logging
import re
from urllib.parse import urlparse

from .recorder_client import RecorderError

logger = logging.getLogger(__name__)

_MAX_URL_LENGTH = 2048
_ALLOWED_SCHEMES = frozenset({"rtsp", "rtsps", "http", "https"})
_MIN_PORT = 1
_MAX_PORT = 65535

# '&' is intentionally NOT blocked — legitimate RTSP/HTTP query separator
# (e.g. ?channel=1&subtype=0). Credentials containing '&' must be
# percent-encoded by the caller before validation (same rule as monolith).
_DANGEROUS_CHARS = re.compile(r"[;|$`\n\r]")


class RTSPUrlValidator:
    """Multi-layer validation of stream/playback URLs (RTSP and HTTP/ONVIF/ISAPI)."""

    @classmethod
    def validate(cls, url: str) -> str:
        """Validates a stream URL. Returns it unchanged or raises RecorderError.

        Raises RecorderError (not a bespoke exception type) so callers in
        this package can treat "bad URL" and "recorder unreachable" the
        same way evidence_api.py already does — no silent fallback, no
        separate exception hierarchy to wire through the mini-API.
        """
        if not url:
            raise RecorderError("URL de stream não pode ser vazia")

        if len(url) > _MAX_URL_LENGTH:
            raise RecorderError(f"URL excede tamanho máximo ({_MAX_URL_LENGTH} chars)")

        if _DANGEROUS_CHARS.search(url):
            raise RecorderError("URL contém caracteres não permitidos")

        try:
            parsed = urlparse(url)
            _ = parsed.port  # force port parsing to catch invalid ports early
        except ValueError as exc:
            raise RecorderError(f"URL malformada: {exc}") from exc

        if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
            raise RecorderError(
                f"Scheme '{parsed.scheme}' não permitido. "
                f"Aceitos: {', '.join(sorted(_ALLOWED_SCHEMES))}"
            )

        if not parsed.hostname:
            raise RecorderError("URL deve ter hostname")

        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_loopback:
                raise RecorderError("Endereço loopback não permitido")
            if ip.is_link_local:
                raise RecorderError("Endereço link-local não permitido (169.254.x.x / fe80::)")
            if ip.is_multicast:
                raise RecorderError("Endereço multicast não permitido")
            if ip.is_reserved:
                raise RecorderError("Endereço reservado não permitido")
            if ip.is_unspecified:
                raise RecorderError("Endereço 0.0.0.0 não permitido")
        except ValueError:
            pass  # hostname, not an IP literal — OK

        if parsed.port is not None and not (_MIN_PORT <= parsed.port <= _MAX_PORT):
            raise RecorderError(
                f"Porta {parsed.port} fora do range permitido ({_MIN_PORT}-{_MAX_PORT})"
            )

        logger.debug("recorder_url_validated scheme=%s host=%s", parsed.scheme, parsed.hostname)
        return url
