"""
Recognition — Health check endpoint.

Usado pelo Railway healthcheck. Sem JWT.
NUNCA expõe strings de conexão ou detalhes internos.
"""
import logging

from flask import Blueprint, jsonify

from app.core.auth import jwt_required_custom

health_bp = Blueprint("health", __name__)
logger = logging.getLogger(__name__)


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


def _check_database() -> bool:
    """SELECT 1 para verificar conectividade."""
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
    """PING para verificar conectividade Redis."""
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


def _count_active_cameras(schema: str) -> int:
    """Conta câmeras com status active no schema do tenant."""
    try:
        from app.infrastructure.database.connection import DatabasePool

        pool = DatabasePool.get_instance()
        if pool is None:
            return 0
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f'SELECT COUNT(*) FROM "{schema}".cameras WHERE status = %s',  # noqa: S608
                ('active',)
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0
    except Exception:
        logger.warning("health_metrics: could not count active cameras")
        return 0
