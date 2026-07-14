"""INFRA email/smtp_client.py — Envio via SMTP genérico (fallback plugável)."""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_via_smtp(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Envia e-mail via SMTP. Lança RuntimeError se mal configurado."""
    host = os.environ.get("SMTP_HOST", "")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    email_from = os.environ.get("EMAIL_FROM", "")
    if not host or not email_from:
        raise RuntimeError("SMTP_HOST/EMAIL_FROM não configurados")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = to
    if text:
        msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(host, port, timeout=10) as server:
        server.starttls()
        if user and password:
            server.login(user, password)
        server.sendmail(email_from, [to], msg.as_string())
    return True
