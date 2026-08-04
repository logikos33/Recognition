"""
CORE login_account_limiter.py — Limite de tentativas de login por CONTA (D-34).

Layer: core
Pattern: contador em Redis (INCR + EXPIRE, janela fixa) + client lazy fail-open
(mesmo desenho de app/core/request_metrics.py e
app/domain/services/session_service.py).

Contexto (D-32, docs/REGISTRO_DE_DECISOES.md): o rate limit de login existente
(flask-limiter, `@limiter.limit("10 per minute")` em app/api/v1/auth/routes.py)
é por IP. Atrás do ProxyFix (`x_for=1`), esse "IP" é o edge de conexão da
Railway, que varia por conexão TCP — em produção-DEV, 15 tentativas de login
falhas em conexões distintas para a MESMA conta não dispararam nenhum 429. A
defesa OWASP contra credential stuffing / brute-force é contar por CONTA
(e-mail), não só por IP. Este módulo COMPLEMENTA o limite por IP (que
continua intocado, como defesa em profundidade) — não o substitui.

Chave Redis: `login_fail:{email normalizado}`. INCR + EXPIRE (janela fixa
desde a 1ª falha — suficiente para este caso de uso, não precisa de sliding
window).

Fail-open DELIBERADO: se o Redis estiver indisponível, este módulo NUNCA
bloqueia login nem levanta exceção — apenas loga em DEBUG e segue como se a
conta não tivesse falhas registradas. Disponibilidade de login > rigor do
contador quando a infraestrutura de contagem está fora do ar (mesma filosofia
de request_metrics.py e do blocklist de JWT revogado em session_service.py).

Related: app/api/v1/auth/routes.py (chamador — rota /login),
         app/extensions.py (limiter por IP, intocado),
         docs/REGISTRO_DE_DECISOES.md (D-32, D-34)
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_KEY_PREFIX = "login_fail:"

# Teto de falhas por conta e janela (segundos) — configuráveis por env,
# defaults conforme D-34 (10 falhas / 15 minutos).
MAX_FAILURES: int = int(os.environ.get("LOGIN_ACCOUNT_MAX_FAILURES", "10"))
WINDOW_SECONDS: int = int(os.environ.get("LOGIN_ACCOUNT_WINDOW_SECONDS", "900"))

_redis_client: Any = None


def _get_redis() -> Any:
    """Cliente Redis lazy, module-level, com socket_timeout curto.

    Usa SEMPRE `config.REDIS_URL` (instância principal) — nunca
    `SEGMENTS_REDIS_URL`. Este é um controle de segurança (contador de
    brute-force por conta), não um cache de segmento de vídeo.
    """
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        import redis as _redis  # noqa: PLC0415
        url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        _redis_client = _redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _redis_client


def _key(email: str) -> str:
    return f"{_KEY_PREFIX}{email}"


def is_blocked(email: str) -> bool:
    """True se a conta já excedeu MAX_FAILURES falhas na janela atual.

    Fail-open: qualquer erro de Redis (indisponível, timeout, etc.) retorna
    False — nunca bloqueia um login por falha de infraestrutura de contagem.
    """
    if not email:
        return False
    try:
        r = _get_redis()
        raw = r.get(_key(email))
        count = int(raw) if raw else 0
        return count >= MAX_FAILURES
    except Exception as exc:  # nunca derrubar/bloquear login por erro de infra
        logger.debug("login_account_limiter_check_failed: %s", exc)
        return False


def register_failure(email: str) -> None:
    """Incrementa o contador de falhas da conta; arma o TTL na 1ª falha da janela.

    Fail-open: qualquer erro de Redis é ignorado — nunca propaga, nunca
    impede a resposta de erro de credenciais já em curso.
    """
    if not email:
        return
    try:
        r = _get_redis()
        key = _key(email)
        count = r.incr(key)
        if count == 1:
            r.expire(key, WINDOW_SECONDS)
    except Exception as exc:
        logger.debug("login_account_limiter_register_failure_failed: %s", exc)


def reset(email: str) -> None:
    """Zera o contador de falhas da conta — chamado em login bem-sucedido
    (recomendação OWASP: sucesso reseta o contador de brute-force).

    Fail-open: qualquer erro de Redis é ignorado — nunca propaga.
    """
    if not email:
        return
    try:
        r = _get_redis()
        r.delete(_key(email))
    except Exception as exc:
        logger.debug("login_account_limiter_reset_failed: %s", exc)
