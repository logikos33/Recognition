"""
CORE rate_limiting.py — Identificador e limites dinâmicos por tenant para flask-limiter.

Layer: core
Pattern: Strategy (key_func + limit provider dinâmico)

Key exports:
  - get_rate_limit_identifier(): chave "tenant:<id>:user:<id>" quando há JWT, senão
    "ip:<remote_addr>" — usada por decorators de ROTA que já vivem atrás de
    @jwt_required (training job creation, test de câmera, upload de vídeo).
  - get_ip_identifier(): chave SEMPRE por IP, nunca por identidade — piso do bucket
    geral, bucket de preflight OPTIONS e fallback do bucket de vídeo HLS.
  - is_anonymous_request(): True quando a request não carrega tenant_id+sub via JWT.
  - get_tenant_rate_limit(): string de limite dinâmica ("N per minute") lida de
    tenants.rate_limit_per_minute (override) ou plans.api_rate_per_minute (default do
    tier), com cache in-process de 60s. Fallback: DEFAULT_API_LIMIT.
  - register_tenant_rate_limits(app, limiter): aplica os 3 buckets do "bucket geral" a
    todos os blueprints da API, exceto os isentos.

Desenho dos buckets do bucket geral (task rate-limit do live view, 04/08 — medido em
produção: flask-limiter global de 300/min POR IP derrubava .m3u8/.ts E o preflight
OPTIONS de /stream/start; 152.233.23.194 no log):
  - "tenant-api-global"    (chave: usuário) — DEFAULT_API_LIMIT, plano/override do
    tenant. Exempt quando anônimo (is_anonymous_request) — sem isso, uma request sem
    JWT caía neste bucket com chave `ip:...` e herdava o teto de PLANO (mais apertado
    que o piso de IP abaixo).
  - "tenant-api-global-ip" (chave: IP)       — DEFAULT_IP_LIMIT. SEMPRE ativo: única
    defesa pra quem não tem JWT, e defesa em profundidade (soma-se ao limite por
    usuário) quando autenticado — várias contas na mesma fábrica não podem somar mais
    que este teto.
  - "tenant-api-options"   (chave: IP, só OPTIONS) — OPTIONS_IP_LIMIT. Preflight CORS é
    mecânica do navegador sem credencial, mas não fica sem limite (vetor de DoS).

Os dois primeiros buckets excluem OPTIONS via `methods=` — é isso que tira o preflight
do bucket geral. Rotas com decorator próprio (@limiter.limit/@limiter.shared_limit —
login, register, progress-callback, test_camera, serve_hls, ...) já saem
automaticamente destes 3 buckets: é o mecanismo padrão do flask-limiter
(override_defaults=True por padrão suprime os limites de blueprint quando a rota tem
limite decorado — mesmo comportamento que login/register já usavam antes desta task).

Constraints:
  - Fail-open: erro de DB/JWT nunca bloqueia a request — cai no limite default.
  - Zero SQL aqui — leitura via TenantPolicyRepository (regra inviolável).
  - Desligado em TESTING via RATELIMIT_ENABLED=False (configurado no create_app).

Related: app/extensions.py (limiter), app/core/middleware.py (handler 429),
         app/api/v1/cameras/stream_handlers.py (buckets hls-video-* do serve_hls),
         app/infrastructure/database/repositories/tenant_policy_repository.py,
         services/api/RATE_LIMITING_PLAN.md
"""
import logging
import time

from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)

# Limite default POR USUÁRIO quando tenant não tem plano/override configurado.
DEFAULT_API_LIMIT = "300 per minute"

# Piso POR IP do bucket geral — nunca removido (ver docstring do módulo).
DEFAULT_IP_LIMIT = "900 per minute"

# Preflight CORS (OPTIONS) — bucket próprio, bem acima do tráfego real de qualquer
# cliente legítimo (é só mecânica de handshake, não trabalho de verdade).
OPTIONS_IP_LIMIT = "2000 per minute"

# Métodos cobertos pelos buckets "gerais" (usuário + piso IP) — deliberadamente SEM
# "OPTIONS": preflight tem bucket próprio (tenant-api-options). Sem esta exclusão, o
# preflight de QUALQUER rota consumia o mesmo bucket de 300/min e derrubava o live
# view (achado de produção, 04/08: OPTIONS .../stream/start -> 429).
_GENERAL_BUCKET_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")

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
    """Chave do bucket de rate limit: tenant+user quando autenticado, senão IP.

    Usada por decorators de ROTA (não pelo bucket geral) que precisam de uma
    única chave "usuário OU IP" — training job creation, test de câmera,
    upload de vídeo. Todas já vivem atrás de @jwt_required, então na prática
    sempre resolvem por usuário.
    """
    claims = _get_jwt_claims()
    tenant_id = claims.get("tenant_id")
    user_id = claims.get("sub")
    if tenant_id and user_id:
        return f"tenant:{tenant_id}:user:{user_id}"
    return f"ip:{get_remote_address()}"


def get_ip_identifier() -> str:
    """Chave SEMPRE por IP — nunca por identidade de usuário.

    Usada pelo piso do bucket geral, pelo bucket de preflight OPTIONS e como
    fallback do bucket de vídeo HLS quando não há token de playback no path.
    """
    return f"ip:{get_remote_address()}"


def is_authenticated_request() -> bool:
    """True quando a request carrega tenant_id+sub (identidade completa) via JWT."""
    claims = _get_jwt_claims()
    return bool(claims.get("tenant_id") and claims.get("sub"))


def is_anonymous_request() -> bool:
    """True quando a request NÃO carrega identidade de tenant+usuário via JWT.

    exempt_when do bucket "tenant-api-global" (por usuário): sem isso, uma
    request anônima cairia nesse bucket com a chave `ip:...` e herdaria o
    teto de PLANO (DEFAULT_API_LIMIT, mais apertado), em vez do piso de IP
    (DEFAULT_IP_LIMIT) pensado pra tráfego sem identidade.
    """
    return not is_authenticated_request()


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


def _ip_floor_limit() -> str:
    """Callable (não string literal) — permite monkeypatch de DEFAULT_IP_LIMIT em teste."""
    return DEFAULT_IP_LIMIT


def _options_limit() -> str:
    """Callable (não string literal) — permite monkeypatch de OPTIONS_IP_LIMIT em teste."""
    return OPTIONS_IP_LIMIT


def clear_limit_cache() -> None:
    """Limpa o cache de limites (uso em testes)."""
    _tenant_limit_cache.clear()


def register_tenant_rate_limits(app, limiter) -> None:  # type: ignore[no-untyped-def]
    """Aplica os 3 buckets do "bucket geral" a todos os blueprints da API.

    Cada bucket é um shared_limit independente (scope próprio) aplicado à
    granularidade de blueprint — mesmo padrão já usado por "tenant-api-global"
    antes desta task, só que agora com 3 buckets simultâneos em vez de 1 (ver
    docstring do módulo pro desenho completo). Blueprints em EXEMPT_BLUEPRINTS
    ficam de fora dos 3.
    """
    user_bucket = limiter.shared_limit(
        get_tenant_rate_limit,
        scope="tenant-api-global",
        key_func=get_rate_limit_identifier,
        methods=list(_GENERAL_BUCKET_METHODS),
        exempt_when=is_anonymous_request,
    )
    ip_floor_bucket = limiter.shared_limit(
        _ip_floor_limit,
        scope="tenant-api-global-ip",
        key_func=get_ip_identifier,
        methods=list(_GENERAL_BUCKET_METHODS),
    )
    options_bucket = limiter.shared_limit(
        _options_limit,
        scope="tenant-api-options",
        key_func=get_ip_identifier,
        methods=["OPTIONS"],
    )
    for name, bp in app.blueprints.items():
        if name in EXEMPT_BLUEPRINTS:
            continue
        user_bucket(bp)
        ip_floor_bucket(bp)
        options_bucket(bp)
