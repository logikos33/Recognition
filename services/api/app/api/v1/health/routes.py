"""Health check endpoints (Railway healthcheck + admin metrics)."""
import logging
import re
import time

from flask import Blueprint, jsonify

from app.api.v1.health.readiness import STALE_AFTER_SECONDS, cache as _readiness_cache
from app.core.auth import jwt_required_custom

health_bp = Blueprint("health", __name__)
logger = logging.getLogger(__name__)

# Marca de boot do PROCESSO (não do request) — usada só por /livez.
_PROCESS_STARTED_AT = time.monotonic()


@health_bp.route("/health")
@health_bp.route("/api/v1/health")
def health_check() -> tuple:
    """
    ---
    tags:
      - health
    summary: Health check do sistema
    description: Verifica conectividade com PostgreSQL e Redis
    responses:
      200:
        description: Sistema saudável
        schema:
          properties:
            status: {type: string, example: healthy}
            checks:
              type: object
              properties:
                database: {type: boolean}
                redis: {type: boolean}
      503:
        description: Sistema degradado
    """
    checks: dict[str, bool] = {
        "database": _check_database(),
        "redis": _check_redis(),
    }
    all_healthy = all(checks.values())
    status_code = 200 if checks["database"] else 503

    return (
        jsonify(
            {
                "status": "healthy" if all_healthy else "degraded",
                "checks": checks,
            }
        ),
        status_code,
    )


@health_bp.route("/livez")
def liveness_check() -> tuple:
    """
    ---
    tags:
      - health
    summary: Liveness — o processo está de pé?
    description: |
      NUNCA toca DB/Redis/R2. Só confirma que o processo Python responde a
      HTTP. Serve para "reiniciar se travou" — não para "promover deploy":
      isso é o /readyz. Sempre 200 enquanto o processo estiver vivo.
    responses:
      200:
        description: Processo vivo
    """
    uptime = time.monotonic() - _PROCESS_STARTED_AT
    return jsonify({"status": "alive", "uptime_seconds": round(uptime, 1)}), 200


@health_bp.route("/readyz")
def readiness_check() -> tuple:
    """
    ---
    tags:
      - health
    summary: Readiness — dependências + invariantes de config (única barreira de promoção)
    description: |
      Railway só chama isto NA PROMOÇÃO do deploy. O handler NUNCA toca
      dependência diretamente — só lê o cache mantido por um refresher de
      fundo (ver readiness.py). Invariantes determinísticos (worker_class,
      storage_backend) reprovam duro na primeira leitura ruim. Dependências
      transitórias (DB, Redis) só reprovam após falhas consecutivas do
      refresher (backoff). Cache com mais de 30s (refresher morto) = 503
      com stale=true, mesmo que o último conteúdo dissesse "tudo bem"
      (fail closed — nunca serve um "ready" congelado).
    responses:
      200:
        description: Pronto para receber tráfego
      503:
        description: Não pronto (invariante quebrado, dependência down, ou cache stale)
    """
    state = _readiness_cache.get_state()
    age = time.monotonic() - state.checked_at

    if age > STALE_AFTER_SECONDS:
        logger.error(
            "readyz_stale: cache com %.1fs (refresher parece morto) — fail closed", age
        )
        return (
            jsonify(
                {
                    "status": "not_ready",
                    "ready": False,
                    "stale": True,
                    "age_seconds": round(age, 1),
                    "invariants": state.invariants,
                    "dependencies": state.dependencies,
                }
            ),
            503,
        )

    return (
        jsonify(
            {
                "status": "ready" if state.ready else "not_ready",
                "ready": state.ready,
                "stale": False,
                "age_seconds": round(age, 1),
                "invariants": state.invariants,
                "dependencies": state.dependencies,
            }
        ),
        200 if state.ready else 503,
    )


@health_bp.route("/status")
def status_check() -> tuple:
    """
    ---
    tags:
      - health
    summary: Diagnóstico rico — NUNCA consumido por automação que reinicia
    description: |
      Agrega o que /health já mostra + detalhe por dependência (latência,
      última checagem via cache de /readyz). Uso humano/observabilidade —
      não é chamado pelo healthcheck do Railway nem por nada que promove ou
      reinicia deploy. Pode fazer I/O direto (sem cache) porque não está no
      caminho de promoção.
    responses:
      200:
        description: Snapshot de diagnóstico
    """
    db_start = time.perf_counter()
    db_ok = _check_database()
    db_latency_ms = round((time.perf_counter() - db_start) * 1000, 1)

    redis_start = time.perf_counter()
    redis_ok = _check_redis()
    redis_latency_ms = round((time.perf_counter() - redis_start) * 1000, 1)

    readiness_state = _readiness_cache.get_state()
    readiness_age = time.monotonic() - readiness_state.checked_at

    return (
        jsonify(
            {
                "status": "healthy" if db_ok and redis_ok else "degraded",
                "checks": {
                    "database": {"ok": db_ok, "latency_ms": db_latency_ms},
                    "redis": {"ok": redis_ok, "latency_ms": redis_latency_ms},
                },
                "readiness_cache": {
                    "ready": readiness_state.ready,
                    "age_seconds": round(readiness_age, 1),
                    "stale": readiness_age > STALE_AFTER_SECONDS,
                    "invariants": readiness_state.invariants,
                    "dependencies": readiness_state.dependencies,
                },
            }
        ),
        200,
    )


def _check_database() -> bool:
    try:
        from app.infrastructure.database.connection import DatabasePool

        pool = DatabasePool.get_instance()
        if pool is None:
            return False
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
        return True
    except Exception:
        logger.warning("health_check: database unavailable")
        return False


def _check_redis() -> bool:
    try:
        import os

        import redis

        url = os.environ.get("REDIS_URL", "")
        if not url:
            return False
        client = redis.from_url(url, socket_timeout=3)
        client.ping()
        return True
    except Exception:
        logger.warning("health_check: redis unavailable")
        return False


@health_bp.route("/api/v1/health/metrics")
@jwt_required_custom
def health_metrics(**kwargs: object) -> tuple:
    """
    ---
    tags:
      - health
    summary: Métricas de saúde para o footer global (requer autenticação)
    responses:
      200:
        description: Métricas coletadas
    """
    from app.core.auth import get_tenant_schema

    schema = get_tenant_schema()

    db_ok = _check_database()
    redis_ok = _check_redis()
    cameras_active = _count_active_cameras(schema)

    return jsonify({
        "database": db_ok,
        "redis": redis_ok,
        "cameras_active": cameras_active,
    }), 200


_SCHEMA_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _count_active_cameras(schema: str) -> int:
    if not _SCHEMA_RE.match(schema):
        logger.warning("health_metrics: invalid schema identifier '%s'", schema)
        return 0
    try:
        from app.infrastructure.database.connection import DatabasePool

        pool = DatabasePool.get_instance()
        if pool is None:
            return 0
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (schema,))
            cur.execute("SELECT COUNT(*) AS count FROM cameras WHERE status = 'active'")
            row = cur.fetchone()
            return int(row["count"]) if row else 0
    except Exception as exc:
        logger.warning(
            "health_metrics: could not count active cameras (%s: %s)",
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        return 0
