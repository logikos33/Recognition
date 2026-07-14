"""INFRA email/resend_client.py — Envio via Resend HTTP API."""
import os

import requests

_RESEND_API_URL = "https://api.resend.com/emails"


def send_via_resend(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Envia e-mail via Resend. Lança RuntimeError se mal configurado."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    email_from = os.environ.get("EMAIL_FROM", "")
    if not api_key or not email_from:
        raise RuntimeError("RESEND_API_KEY/EMAIL_FROM não configurados")

    payload: dict = {"from": email_from, "to": [to], "subject": subject, "html": html}
    if text:
        payload["text"] = text

    resp = requests.post(
        _RESEND_API_URL,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10,
    )
    resp.raise_for_status()
    return True
