"""
INFRASTRUCTURE queue/worker_registry.py — Worker On-Premise Registry.

Layer: infrastructure
Pattern: Redis-backed registry with heartbeat TTL + DB persistence for history

Key exports:
  publish_heartbeat(tenant_schema, metrics)
    Worker on-premise chama a cada 30s.
    SET Redis `worker:heartbeat:{tenant_schema}` com JSON de métricas TTL=90s.
    A cada 5 heartbeats persiste métricas no banco.

  get_worker_status(tenant_schema) → "onpremise" | "railway" | "offline"
    Lê chave Redis. Se presente → "onpremise". Se ausente → "railway" (fallback).

  get_worker_metrics(tenant_schema) → dict | None
    Métricas live do Redis (gpu_pct, vram_used_gb, fps_avg, cameras_active).

  get_all_workers_status() → list[dict]
    JOIN com public.worker_registry + public.tenants + métricas live.

  route_inference_task(tenant_schema) → str
    Fila Celery correta: inference_{schema} se onpremise, senão inference.

  fallback_to_railway(tenant_schema)
    Publica evento Redis para scheduler redirecionar tasks para fila padrão.

Related: backend/worker_onpremise/, backend/app/api/v1/admin/routes.py
"""
import json
import logging
import os
from typing import Any

import redis as _redis

logger = logging.getLogger(__name__)

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
_HEARTBEAT_PREFIX = "worker:heartbeat:"
_HEARTBEAT_TTL = 90   # segundos — worker publica a cada 30s
_HB_COUNT_PREFIX = "worker:hb_count:"
_HB_PERSIST_EVERY = 5  # persistir no banco a cada N heartbeats


def _get_redis() -> Any:
    return _redis.from_url(_REDIS_URL, decode_responses=True)


def publish_heartbeat(tenant_schema: str, metrics: dict[str, Any]) -> None:
    """
    Publica heartbeat do worker on-premise.

    Armazena JSON de métricas no Redis com TTL=90s.
    A cada 5 heartbeats persiste no banco via _persist_worker_metrics().
    """
    try:
        r = _get_redis()
        payload = json.dumps({**metrics, "tenant_schema": tenant_schema})
        r.setex(f"{_HEARTBEAT_PREFIX}{tenant_schema}", _HEARTBEAT_TTL, payload)

        # Contador de persistência
        count_key = f"{_HB_COUNT_PREFIX}{tenant_schema}"
        count = r.incr(count_key)
        if count == 1:
            r.expire(count_key, 300)
        if count >= _HB_PERSIST_EVERY:
            r.delete(count_key)
            _persist_worker_metrics(tenant_schema, metrics)

        r.close()
        logger.debug("worker_heartbeat: schema=%s ttl=%ds", tenant_schema, _HEARTBEAT_TTL)
    except Exception as exc:
        logger.warning("publish_heartbeat_failed: schema=%s err=%s", tenant_schema, exc)


def get_worker_status(tenant_schema: str) -> str:
    """
    Retorna status do worker para o schema.

    Returns:
        "onpremise" — heartbeat Redis ativo (worker físico online)
        "railway"   — sem heartbeat (usando worker Railway como fallback)
        "offline"   — Redis inacessível
    """
    try:
        r = _get_redis()
        val = r.get(f"{_HEARTBEAT_PREFIX}{tenant_schema}")
        r.close()
        return "onpremise" if val else "railway"
    except Exception as exc:
        logger.warning("get_worker_status_failed: schema=%s err=%s", tenant_schema, exc)
        return "offline"


def get_worker_metrics(tenant_schema: str) -> dict[str, Any] | None:
    """Retorna métricas live do Redis ou None se worker offline."""
    try:
        r = _get_redis()
        val = r.get(f"{_HEARTBEAT_PREFIX}{tenant_schema}")
        r.close()
        return json.loads(val) if val else None
    except Exception as exc:
        logger.warning("get_worker_metrics_failed: schema=%s err=%s", tenant_schema, exc)
        return None


def get_all_workers_status() -> list[dict[str, Any]]:
    """
    Lista todos os workers registrados no banco com status live do Redis.

    Retorna lista de dicts com campos do worker_registry + status + live_metrics.
    """
    try:
        from app.infrastructure.database.connection import DatabasePool

        pool = DatabasePool.get_instance()
        if pool is None:
            return []

        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                    SELECT
                        wr.id, wr.tenant_id, wr.tenant_schema,
                        wr.hostname, wr.tailscale_ip, wr.software_version,
                        wr.gpu_model, wr.gpu_vram_gb,
                        wr.registered_at, wr.last_heartbeat_at,
                        wr.status, wr.active,
                        t.name AS tenant_name, t.slug AS tenant_slug
                    FROM public.worker_registry wr
                    JOIN public.tenants t ON t.id = wr.tenant_id
                    WHERE wr.active = true
                    ORDER BY t.name
                """)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            workers = []
            for row in rows:
                w = dict(zip(cols, row, strict=False))
                schema = w["tenant_schema"]
                w["status"] = get_worker_status(schema)
                w["live_metrics"] = get_worker_metrics(schema)
                # Serializar UUIDs e timestamps
                for k in ("id", "tenant_id"):
                    if w.get(k):
                        w[k] = str(w[k])
                for k in ("registered_at", "last_heartbeat_at"):
                    if w.get(k):
                        w[k] = w[k].isoformat()
                workers.append(w)
        return workers

    except Exception as exc:
        logger.warning("get_all_workers_status_failed: err=%s", exc)
        # Fallback: apenas Redis scan (sem DB)
        return _scan_redis_workers()


def _scan_redis_workers() -> list[dict[str, Any]]:
    """Fallback quando DB indisponível — só dados do Redis."""
    try:
        r = _get_redis()
        result = []
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=f"{_HEARTBEAT_PREFIX}*", count=100)
            for key in keys:
                schema = key[len(_HEARTBEAT_PREFIX):]
                val = r.get(key)
                metrics = json.loads(val) if val else {}
                result.append({
                    "tenant_schema": schema,
                    "status": "onpremise",
                    "live_metrics": metrics,
                })
            if cursor == 0:
                break
        r.close()
        return result
    except Exception:
        return []


def route_inference_task(tenant_schema: str) -> str:
    """
    Retorna fila Celery correta para inferência do tenant.

    Se worker on-premise ativo → inference_{tenant_schema}
    Senão → inference (fila padrão Railway)
    """
    status = get_worker_status(tenant_schema)
    return f"inference_{tenant_schema}" if status == "onpremise" else "inference"


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


def _persist_worker_metrics(tenant_schema: str, metrics: dict[str, Any]) -> None:
    """
    Persiste métricas no banco e atualiza last_heartbeat_at no worker_registry.
    Chamado a cada 5 heartbeats para não sobrecarregar o banco.
    """
    try:
        from app.infrastructure.database.connection import DatabasePool

        pool = DatabasePool.get_instance()
        if pool is None:
            return

        with pool.get_connection() as conn, conn.cursor() as cur:
            # Buscar ou criar registro no worker_registry
            cur.execute(
                "SELECT id FROM public.worker_registry "
                "WHERE tenant_schema = %s AND active = true LIMIT 1",
                (tenant_schema,),
            )
            row = cur.fetchone()

            if not row:
                # Auto-registrar worker ao primeiro heartbeat com banco
                cur.execute(
                    "SELECT id FROM public.tenants WHERE schema_name = %s LIMIT 1",
                    (tenant_schema,),
                )
                tenant_row = cur.fetchone()
                if not tenant_row:
                    return
                tenant_id = tenant_row[0]

                cur.execute(
                    """
                        INSERT INTO public.worker_registry
                          (tenant_id, tenant_schema, hostname, software_version,
                           gpu_model, status)
                        VALUES (%s, %s, %s, %s, %s, 'online')
                        RETURNING id
                        """,
                    (
                        str(tenant_id),
                        tenant_schema,
                        metrics.get("hostname"),
                        metrics.get("software_version"),
                        metrics.get("gpu_model"),
                    ),
                )
                worker_row = cur.fetchone()
                worker_id = worker_row[0]
            else:
                worker_id = row[0]

            # Inserir métricas
            cur.execute(
                """
                    INSERT INTO public.worker_metrics
                      (worker_id, gpu_pct, vram_used_gb, fps_avg, cameras_active)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                (
                    str(worker_id),
                    metrics.get("gpu_pct"),
                    metrics.get("vram_used_gb"),
                    metrics.get("fps_avg"),
                    metrics.get("cameras_active"),
                ),
            )

            # Atualizar last_heartbeat_at e status
            cur.execute(
                """
                    UPDATE public.worker_registry
                    SET last_heartbeat_at = NOW(), status = 'online',
                        hostname = COALESCE(%s, hostname),
                        software_version = COALESCE(%s, software_version),
                        gpu_model = COALESCE(%s, gpu_model)
                    WHERE id = %s
                    """,
                (
                    metrics.get("hostname"),
                    metrics.get("software_version"),
                    metrics.get("gpu_model"),
                    str(worker_id),
                ),
            )

    except Exception as exc:
        logger.warning("persist_worker_metrics_failed: schema=%s err=%s", tenant_schema, exc)
