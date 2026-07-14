"""
INFRA email — Envio de e-mail plugável por env (ADR-0042 Fase 2).

Layer: infrastructure
Pattern: Strategy (provider escolhido em runtime via EMAIL_PROVIDER)

Key exports:
  - send_email(to, subject, html, text): envia via Resend (default) ou SMTP,
    conforme EMAIL_PROVIDER. Best-effort — nunca lança, retorna bool.

Constraints:
  - Nenhuma credencial hardcoded — tudo via os.environ (RESEND_API_KEY,
    EMAIL_FROM, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD).
  - Trocar de provedor não deve exigir mudança nas rotas que chamam send_email.

Related: app/domain/services/password_reset_service.py, ADR-0042.
"""
import logging
import os

from app.infrastructure.email.resend_client import send_via_resend
from app.infrastructure.email.smtp_client import send_via_smtp

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Envia e-mail via provedor configurado em EMAIL_PROVIDER (default: resend).

    Best-effort: qualquer falha é logada e retorna False — nunca propaga
    exceção para o chamador (envio de e-mail não pode derrubar a request).
    """
    provider = os.environ.get("EMAIL_PROVIDER", "resend").lower()
    try:
        if provider == "smtp":
            return send_via_smtp(to, subject, html, text)
        return send_via_resend(to, subject, html, text)
    except Exception as exc:
        logger.error(
            "email_send_failed provider=%s to=%s: %s", provider, to, exc, exc_info=True
        )
        return False
