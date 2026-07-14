"""
DOMAIN password_reset_service.py — Recuperação de senha self-service (ADR-0042 Fase 2).

Layer: domain
Pattern: Service (framework-agnostic, dependências injetadas)

Fluxo:
  1. request_reset(email): se a conta existir e estiver ativa, gera token
     opaco, grava pwreset:{token} -> user_id no Redis (TTL 30min) e envia
     e-mail com link de reset. SEMPRE "sucesso" do ponto de vista do
     chamador — nunca revela se o e-mail existe (evita enumeração).
  2. reset_password(token, new_password): valida o token no Redis, troca o
     hash da senha, limpa force_password_reset, apaga o token e invalida
     todas as sessões ativas do usuário.

Related: app/infrastructure/email/, app/domain/services/session_service.py,
         app/api/v1/auth/routes.py, ADR-0042.
"""
import logging
import os
import secrets

from app.core.auth import hash_password
from app.core.exceptions import ValidationError
from app.infrastructure.database.repositories.session_repository import SessionRepository
from app.infrastructure.database.repositories.user_repository import UserRepository
from app.infrastructure.email import send_email

logger = logging.getLogger(__name__)

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
_TOKEN_PREFIX = "pwreset:"
_TOKEN_TTL_SECONDS = 1800  # 30 min


def _get_redis():  # type: ignore[no-untyped-def]
    import redis as _redis
    return _redis.from_url(_REDIS_URL, decode_responses=True)


class PasswordResetService:
    """Use cases de recuperação de senha self-service."""

    def __init__(self, user_repo: UserRepository, session_repo: SessionRepository) -> None:
        self._user_repo = user_repo
        self._session_repo = session_repo

    def request_reset(self, email: str) -> None:
        """Envia e-mail de reset se a conta existir. Nunca vaza existência."""
        email = email.strip().lower()
        if not email:
            return

        user = self._user_repo.get_by_email(email)
        if not user or not user.get("is_active"):
            logger.info("password_reset_requested_unknown_or_inactive email=%s", email)
            return

        token = secrets.token_urlsafe(32)
        try:
            r = _get_redis()
            r.setex(f"{_TOKEN_PREFIX}{token}", _TOKEN_TTL_SECONDS, str(user["id"]))
            r.close()
        except Exception as exc:
            logger.error("password_reset_token_store_failed email=%s: %s", email, exc, exc_info=True)
            return

        frontend_url = os.environ.get("FRONTEND_URL", "").rstrip("/")
        reset_url = f"{frontend_url}/reset-password?token={token}"
        sent = send_email(
            to=email,
            subject="Recognition — Redefinição de senha",
            html=_reset_email_html(user.get("name") or email, reset_url),
            text=f"Redefina sua senha em: {reset_url} (expira em 30 minutos)",
        )
        if not sent:
            logger.error("password_reset_email_send_failed email=%s", email)

    def reset_password(self, token: str, new_password: str) -> None:
        """Valida o token, troca a senha e invalida sessões ativas."""
        if not token or not new_password:
            raise ValidationError("Token e nova senha são obrigatórios")
        if len(new_password) < 6:
            raise ValidationError("Senha: mínimo 6 caracteres")

        try:
            r = _get_redis()
            user_id = r.get(f"{_TOKEN_PREFIX}{token}")
        except Exception as exc:
            logger.error("password_reset_token_lookup_failed: %s", exc, exc_info=True)
            raise ValidationError("Token inválido ou expirado") from exc

        if not user_id:
            raise ValidationError("Token inválido ou expirado")

        password_hash = hash_password(new_password)
        updated = self._user_repo.reset_password(user_id, password_hash)
        if not updated:
            raise ValidationError("Token inválido ou expirado")

        try:
            r.delete(f"{_TOKEN_PREFIX}{token}")
            r.close()
        except Exception as exc:
            logger.warning("password_reset_token_cleanup_failed: %s", exc)

        from app.domain.services.session_service import invalidate_all_sessions
        invalidate_all_sessions(self._session_repo, user_id)


def _reset_email_html(name: str, reset_url: str) -> str:
    return (
        '<div style="font-family:sans-serif;max-width:480px;margin:0 auto;">'
        "<h2>Redefinição de senha</h2>"
        f"<p>Olá, {name}.</p>"
        "<p>Recebemos uma solicitação para redefinir sua senha no Recognition.</p>"
        f'<p><a href="{reset_url}" style="background:#2563eb;color:#fff;padding:10px 20px;'
        'border-radius:6px;text-decoration:none;display:inline-block;">Redefinir senha</a></p>'
        "<p>Se você não solicitou, ignore este e-mail. O link expira em 30 minutos.</p>"
        "</div>"
    )
