"""
DOMAIN session_service.py — Sessões concorrentes: "última sessão ganha".

Layer: domain
Pattern: Service (framework-agnostic, dependências injetadas)

Fluxo:
  1. No login, register_login_session() grava a sessão em public.active_sessions.
  2. Se tenants.single_session = true, revoga as sessões anteriores do usuário
     (UPDATE revoked_at) e escreve cada jti revogado no Redis
     (key revoked_jti:<jti>, TTL = expiração restante do token).
  3. is_jti_revoked() é consultado pelo token_in_blocklist_loader do
     flask-jwt-extended em toda request autenticada.

TODO (GAP arquitetural — documentado conforme combinado):
  - Não existem refresh tokens: o access token vive JWT_EXPIRY_HOURS (24h default).
    A revogação efetiva depende exclusivamente do blocklist Redis; se o Redis
    estiver indisponível, a checagem FALHA ABERTA (token antigo continua válido
    até expirar). Mitigação futura: refresh tokens curtos + access de 15min,
    ou checagem de active_sessions no banco com cache.
  - register_login_session é best-effort: falha de banco/Redis não impede login
    (disponibilidade > enforcement nesta fase).

Related: app/infrastructure/database/repositories/session_repository.py,
         app/infrastructure/database/repositories/tenant_policy_repository.py,
         app/api/v1/auth/routes.py (login), app/__init__.py (blocklist loader)
"""
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_REVOKED_PREFIX = "revoked_jti:"


def _get_redis():  # type: ignore[no-untyped-def]
    import redis as _redis
    return _redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        socket_timeout=2,
        decode_responses=True,
    )


def register_login_session(
    session_repo: Any,
    policy_repo: Any,
    user_id: str,
    tenant_id: str,
    jti: str,
    expires_at: Any,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    redis_client: Any = None,
) -> dict[str, Any]:
    """Registra sessão de login e aplica política single_session do tenant.

    Best-effort: exceções são logadas e NUNCA propagadas — login não pode
    falhar por causa de bookkeeping de sessão.

    Returns:
        {"registered": bool, "revoked_count": int}
    """
    result = {"registered": False, "revoked_count": 0}
    try:
        session_repo.create_session(
            user_id=user_id,
            tenant_id=tenant_id,
            jti=jti,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )
        result["registered"] = True

        policy = policy_repo.get_seat_policy(tenant_id)
        if policy.get("single_session"):
            revoked = session_repo.revoke_other_sessions(user_id, keep_jti=jti)
            result["revoked_count"] = len(revoked)
            if revoked:
                _blocklist_jtis(revoked, redis_client)
                logger.info(
                    "single_session_enforced: user=%s revoked=%d",
                    user_id, len(revoked),
                )
    except Exception as exc:
        logger.warning("register_login_session_failed: user=%s err=%s", user_id, exc)
    return result


def _blocklist_jtis(revoked: list[dict[str, Any]], redis_client: Any = None) -> None:
    """Escreve jtis revogados no Redis com TTL = tempo restante até expirar."""
    try:
        r = redis_client or _get_redis()
        now = datetime.now(timezone.utc)
        for row in revoked:
            jti = row.get("jti")
            if not jti:
                continue
            expires_at = row.get("expires_at")
            ttl = 86400  # fallback: 24h (JWT_EXPIRY_HOURS default)
            if isinstance(expires_at, datetime):
                exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
                ttl = max(60, int((exp - now).total_seconds()))
            r.setex(f"{_REVOKED_PREFIX}{jti}", ttl, "1")
        if redis_client is None:
            r.close()
    except Exception as exc:
        logger.warning("blocklist_jtis_failed: err=%s", exc)


def is_jti_revoked(jti: str, redis_client: Any = None) -> bool:
    """Checa blocklist Redis. Fail-open: erro de Redis → token aceito (ver TODO)."""
    if not jti:
        return False
    try:
        r = redis_client or _get_redis()
        revoked = bool(r.exists(f"{_REVOKED_PREFIX}{jti}"))
        if redis_client is None:
            r.close()
        return revoked
    except Exception:
        return False
