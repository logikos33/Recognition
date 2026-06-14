"""
CORE rate_limiting.py — Identificador e limites dinâmicos por tenant para flask-limiter.

Layer: core
Pattern: Strategy (key_func + limit provider dinâmico)

Key exports:
  - get_rate_limit_identifier(): chave do bucket — "tenant:<id>:user:<id>" quando há JWT,
    senão "ip:<remote_addr>" (endpoints públicos).
  - get_tenant_rate_limit(): string de limite dinâmica ("N per minute") lida de
    tenants.rate_limit_per_minute (override) ou plans.api_rate_per_minute (default do tier),
    com cache in-process de 60s. Fallback: DEFAULT_API_LIMIT.
  - register_tenant_rate_limits(app, limiter): aplica shared_limit dinâmico a todos os
    blueprints da API, exceto os isentos (health, frontend estático).

Constraints:
  - Fail-open: erro de DB/JWT nunca bloqueia a request — cai no limite default.
  - Zero SQL aqui — leitura via TenantPolicyRepository (regra inviolável).
  - Desligado em TESTING via RATELIMIT_ENABLED=False (configurado no create_app).

Related: app/extensions.py (limiter), app/core/middleware.py (handler 429),
         app/infrastructure/database/repositories/tenant_policy_repository.py,
         services/api/RATE_LIMITING_PLAN.md
"""
import logging
import time

from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)

# Limite default (por usuário/IP) quando tenant não tem plano/override configurado
DEFAULT_API_LIMIT = "300 per minute"

# Blueprints que NUNCA recebem rate limit (monitoramento / assets)
EXEMPT_BLUEPRINTS = frozenset({"health"})

# Cache in-process: tenant_id → (limite_str, timestamp). TTL curto — mudanças de
# plano propagam em até 60s sem precisar de restart.
_CACHE_TTL_SECONDS = 60
_tenant_limit_cache: dict[str, tuple[str, float]] = {}


def _get_jwt_claims() -> dict:
    """Retorna claims do JWT atual (vazio se ausente/inválido). Nunca levanta."""
    try:
        from flask_jwt_extended import get_jwt, verify_jwt_in_request
        verify_jwt_in_request(optional=True)
        return get_jwt() or {}
    except Exception:
        return {}


def get_rate_limit_identifier() -> str:
    """Chave do bucket de rate limit: tenant+user quando autenticado, senão IP."""
    claims = _get_jwt_claims()
    tenant_id = claims.get("tenant_id")
    user_id = claims.get("sub")
    if tenant_id and user_id:
        return f"tenant:{tenant_id}:user:{user_id}"
    return f"ip:{get_remote_address()}"


def get_tenant_rate_limit() -> str:
    """Limite dinâmico por tenant — lido do plano/override com cache de 60s."""
    claims = _get_jwt_claims()
    tenant_id = claims.get("tenant_id")
    if not tenant_id:
        return DEFAULT_API_LIMIT

    now = time.monotonic()
    cached = _tenant_limit_cache.get(tenant_id)
    if cached and (now - cached[1]) < _CACHE_TTL_SECONDS:
        return cached[0]

    limit = DEFAULT_API_LIMIT
    try:
        from app.infrastructure.database.connection import DatabasePool
        from app.infrastructure.database.repositories.tenant_policy_repository import (
            TenantPolicyRepository,
        )
        pool = DatabasePool.get_instance()
        if pool is not None:
            rpm = TenantPolicyRepository(pool).get_rate_limit_per_minute(tenant_id)
            if rpm and rpm > 0:
                limit = f"{rpm} per minute"
    except Exception as exc:  # fail-open — nunca derrubar request por erro de leitura
        logger.warning("tenant_rate_limit_lookup_failed: tenant=%s err=%s", tenant_id, exc)

    _tenant_limit_cache[tenant_id] = (limit, now)
    return limit


def clear_limit_cache() -> None:
    """Limpa o cache de limites (uso em testes)."""
    _tenant_limit_cache.clear()


def register_tenant_rate_limits(app, limiter) -> None:  # type: ignore[no-untyped-def]
    """Aplica limite global por tenant a todos os blueprints da API.

    Usa shared_limit (scope único) — o tenant consome um bucket global
    independente do blueprint atingido. Blueprints em EXEMPT_BLUEPRINTS
    e rotas fora de blueprint (frontend estático) ficam de fora.
    """
    shared = limiter.shared_limit(
        get_tenant_rate_limit,
        scope="tenant-api-global",
        key_func=get_rate_limit_identifier,
    )
    for name, bp in app.blueprints.items():
        if name in EXEMPT_BLUEPRINTS:
            continue
        shared(bp)
