"""
INFRASTRUCTURE queue/worker_registry.py — Worker On-Premise Registry.

Layer: infrastructure
Pattern: Redis-backed registry with heartbeat TTL

Key exports:
  publish_heartbeat(tenant_schema)
    Worker on-premise chama a cada 30s.
    SET Redis `worker:heartbeat:{tenant_schema}` com TTL=90s.

  get_worker_status(tenant_schema) → "onpremise" | "railway" | "offline"
    Lê chave Redis. Se presente → "onpremise". Se ausente → "railway" (fallback).

  get_all_workers_status() → dict[str, str]
    SCAN Redis `worker:heartbeat:*` e retorna {schema: status}.

  fallback_to_railway(tenant_schema)
    Publica evento Redis para scheduler redirecionar tasks para fila padrão.

Related: backend/worker_onpremise/, backend/app/api/v1/admin/routes.py
"""
import logging
import os
from typing import Any

import redis as _redis

logger = logging.getLogger(__name__)

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
_HEARTBEAT_PREFIX = "worker:heartbeat:"
_HEARTBEAT_TTL = 90   # segundos — worker publica a cada 30s


def _get_redis() -> Any:
    return _redis.from_url(_REDIS_URL, decode_responses=True)


def publish_heartbeat(tenant_schema: str) -> None:
    """Publica heartbeat do worker on-premise. Chamar a cada 30s."""
    try:
        r = _get_redis()
        r.setex(f"{_HEARTBEAT_PREFIX}{tenant_schema}", _HEARTBEAT_TTL, "onpremise")
        r.close()
        logger.debug("worker_heartbeat: schema=%s ttl=%ds", tenant_schema, _HEARTBEAT_TTL)
    except Exception as exc:
        logger.warning("publish_heartbeat_failed: schema=%s err=%s", tenant_schema, exc)


def get_worker_status(tenant_schema: str) -> str:
    """
    Retorna status do worker para o schema.

    Returns:
        "onpremise" — heartbeat Redis ativo (worker físico online)
        "railway"   — sem heartbeat (usando worker Railway)
        "offline"   — Redis inacessível
    """
    try:
        r = _get_redis()
        val = r.get(f"{_HEARTBEAT_PREFIX}{tenant_schema}")
        r.close()
        return val or "railway"
    except Exception as exc:
        logger.warning("get_worker_status_failed: schema=%s err=%s", tenant_schema, exc)
        return "offline"


def get_all_workers_status() -> dict[str, str]:
    """
    SCAN Redis para todas as chaves de heartbeat.

    Returns:
        {"rvb": "onpremise", "admin": "railway", ...}
    """
    try:
        r = _get_redis()
        prefix = _HEARTBEAT_PREFIX
        result: dict[str, str] = {}
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=f"{prefix}*", count=100)
            for key in keys:
                schema = key[len(prefix):]
                val = r.get(key)
                result[schema] = val or "railway"
            if cursor == 0:
                break
        r.close()
        return result
    except Exception as exc:
        logger.warning("get_all_workers_status_failed: err=%s", exc)
        return {}


def fallback_to_railway(tenant_schema: str) -> None:
    """
    Publica evento de fallback para o scheduler redirecionar tasks
    de `inference_{tenant_schema}` para a fila `inference` padrão Railway.
    """
    try:
        r = _get_redis()
        r.publish(f"worker:fallback:{tenant_schema}", "railway")
        r.delete(f"{_HEARTBEAT_PREFIX}{tenant_schema}")
        r.close()
        logger.info("worker_fallback_triggered: schema=%s", tenant_schema)
    except Exception as exc:
        logger.warning("fallback_to_railway_failed: schema=%s err=%s", tenant_schema, exc)
