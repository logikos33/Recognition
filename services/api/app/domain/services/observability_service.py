"""
DOMAIN observability_service.py — agregações do dashboard de observability (WS11).

Consumido exclusivamente pelas rotas superadmin /api/v1/admin/observability/*
(app/api/v1/admin/observability_routes.py). Cada seção do summary degrada de
forma isolada (fonte indisponível → campo null/parcial, nunca 500).

Related: app/infrastructure/queue/tasks/observability.py (coletor),
         app/core/request_metrics.py (RED da API),
         infra/migrations/088_platform_metrics.sql
"""
import glob
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Whitelist janela → (segundos da janela, segundos do bucket)
WINDOW_BUCKETS: dict[str, tuple[int, int]] = {
    "1h": (3_600, 60),
    "6h": (21_600, 300),
    "24h": (86_400, 900),
    "7d": (604_800, 3_600),
}

_STATIC_QUEUES = [
    "inference", "extraction", "training", "versioning",
    "quality_recording", "quality_clips", "quality_cep",
]
_HEARTBEAT_PREFIX = "worker:heartbeat:"
_CELERY_INSPECT_CACHE_KEY = "obs:celery:inspect"
_CELERY_INSPECT_CACHE_TTL = 30  # segundos


def _get_redis() -> Any:
    import redis as _redis  # noqa: PLC0415
    return _redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _pool() -> Any:
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
    return DatabasePool.get_instance()


# ---------------------------------------------------------------------------
# Seções do summary
# ---------------------------------------------------------------------------

def _db_section() -> dict[str, Any]:
    pool = _pool()
    if pool is None:
        return {"status": "critical", "details": "pool indisponível"}
    try:
        with pool.get_connection() as conn:
            cur = conn.cursor()
            start = time.perf_counter()
            cur.execute(
                "SELECT count(*) FILTER (WHERE state = 'active') AS active, "
                "       count(*) FILTER (WHERE state = 'idle')   AS idle, "
                "       current_setting('max_connections')::int  AS max_conn "
                "FROM pg_stat_activity"
            )
            row = cur.fetchone() or {}
            latency = round((time.perf_counter() - start) * 1000, 1)
        return {
            "status": "healthy",
            "latency_ms": latency,
            "connections": {
                "active": int(row.get("active") or 0),
                "idle": int(row.get("idle") or 0),
                "max": int(row.get("max_conn") or 0),
            },
        }
    except Exception as exc:
        logger.warning("obs_summary_db_failed: %s", exc)
        return {"status": "critical", "details": str(exc)}


def _redis_section(r: Any | None) -> dict[str, Any]:
    if r is None:
        return {"status": "critical", "details": "redis indisponível"}
    try:
        start = time.perf_counter()
        r.ping()
        latency = round((time.perf_counter() - start) * 1000, 1)
        info = r.info()
        return {
            "status": "healthy",
            "latency_ms": latency,
            "mem_mb": round(int(info.get("used_memory", 0)) / 1_048_576, 2),
            "clients": int(info.get("connected_clients", 0)),
        }
    except Exception as exc:
        logger.warning("obs_summary_redis_failed: %s", exc)
        return {"status": "critical", "details": str(exc)}


def _r2_section() -> dict[str, Any]:
    try:
        from app.infrastructure.storage.r2_storage import R2Storage  # noqa: PLC0415
        start = time.perf_counter()
        r2 = R2Storage()
        r2.exists("health-check-probe")
        latency = round((time.perf_counter() - start) * 1000, 1)
        return {"status": "healthy", "latency_ms": latency}
    except Exception as exc:
        logger.warning("obs_summary_r2_failed: %s", exc)
        return {"status": "degraded", "details": str(exc)}


def _dynamic_inference_queues(r: Any) -> list[str]:
    queues: list[str] = []
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor, match=f"{_HEARTBEAT_PREFIX}*", count=100)
        for key in keys:
            schema = key[len(_HEARTBEAT_PREFIX):]
            if schema:
                queues.append(f"inference_{schema}")
        if cursor == 0:
            break
    return queues


def _celery_section(r: Any | None) -> dict[str, Any]:
    if r is None:
        return {"status": "degraded", "queues": [], "details": "redis indisponível"}
    from app.infrastructure.queue.tasks.observability import (  # noqa: PLC0415
        _oldest_item_age_seconds,
    )
    try:
        dynamic = _dynamic_inference_queues(r)
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y%m%d")
        yesterday = (now - timedelta(days=1)).strftime("%Y%m%d")
        queues = []
        for q in [*_STATIC_QUEUES, *dynamic]:
            ok = fail = 0
            for day in (today, yesterday):
                stats = r.hgetall(f"celery:stats:{q}:{day}") or {}
                ok += int(stats.get("ok", 0) or 0)
                fail += int(stats.get("fail", 0) or 0)
            age = _oldest_item_age_seconds(r, q)
            queues.append({
                "name": q,
                "depth": int(r.llen(q) or 0),
                "oldest_age_s": round(age, 1) if age is not None else None,
                "ok_24h": ok,
                "fail_24h": fail,
                "dynamic": q not in _STATIC_QUEUES,
            })
        return {"status": "healthy", "queues": queues}
    except Exception as exc:
        logger.warning("obs_summary_celery_failed: %s", exc)
        return {"status": "degraded", "queues": [], "details": str(exc)}


def _workers_section(r: Any | None) -> dict[str, Any]:
    online = 0
    if r is not None:
        try:
            online = len(_dynamic_inference_queues(r))
        except Exception as exc:
            logger.warning("obs_summary_workers_redis_failed: %s", exc)
    total = online
    pool = _pool()
    if pool is not None:
        try:
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT count(*) AS total FROM public.worker_registry "
                    "WHERE active = true"
                )
                row = cur.fetchone() or {}
                total = int(row.get("total") or 0)
        except Exception as exc:
            logger.warning("obs_summary_workers_db_failed: %s", exc)
    return {"online": online, "total": max(total, online)}


def _edge_section() -> dict[str, Any]:
    try:
        from app.core.edge_offline import derive_site_health_status  # noqa: PLC0415
        from app.infrastructure.database.repositories.edge_heartbeat_repository import (  # noqa: PLC0415
            EdgeHeartbeatRepository,
        )
        pool = _pool()
        if pool is None:
            return {"sites_total": 0, "sites_offline": 0, "sites_degraded": 0,
                    "sites_critical": 0}
        repo = EdgeHeartbeatRepository(pool)
        rows = repo.get_last_heartbeat_per_site_all_tenants()
        counts = {"healthy": 0, "degraded": 0, "critical": 0, "offline": 0}
        for row in rows:
            if row.get("site_status") == "provisioning":
                continue
            status = derive_site_health_status(
                row.get("received_at"), row.get("heartbeat_status")
            )
            counts[status] = counts.get(status, 0) + 1
        return {
            "sites_total": len(rows),
            "sites_offline": counts["offline"],
            "sites_degraded": counts["degraded"],
            "sites_critical": counts["critical"],
        }
    except Exception as exc:
        logger.warning("obs_summary_edge_failed: %s", exc)
        return {"sites_total": 0, "sites_offline": 0, "sites_degraded": 0,
                "sites_critical": 0}


def _api_section() -> dict[str, Any]:
    try:
        from app.core.request_metrics import aggregate_last_hours  # noqa: PLC0415
        agg = aggregate_last_hours(1)
        errors = agg["err_4xx"] + agg["err_5xx"]
        err_rate = round(errors * 100.0 / agg["count"], 2) if agg["count"] else 0.0
        return {
            "req_1h": int(agg["count"]),
            "err_rate_pct": err_rate,
            "avg_ms": agg["avg_ms"],
        }
    except Exception as exc:
        logger.warning("obs_summary_api_failed: %s", exc)
        return {"req_1h": 0, "err_rate_pct": 0.0, "avg_ms": 0.0}


def _find_migrations_dir() -> str | None:
    override = os.environ.get("MIGRATIONS_DIR")
    if override and os.path.isdir(override):
        return override
    here = os.path.abspath(__file__)
    current = os.path.dirname(here)
    for _ in range(8):
        candidate = os.path.join(current, "infra", "migrations")
        if os.path.isdir(candidate):
            return candidate
        current = os.path.dirname(current)
    return None


def _migrations_section() -> dict[str, Any]:
    applied: set[str] = set()
    latest: str | None = None
    pool = _pool()
    if pool is not None:
        try:
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT version FROM schema_migrations")
                applied = {str(row["version"]) for row in cur.fetchall()}
                latest = max(applied) if applied else None
        except Exception as exc:
            logger.warning("obs_summary_migrations_db_failed: %s", exc)

    files: list[str] = []
    migrations_dir = _find_migrations_dir()
    if migrations_dir:
        files = sorted(
            os.path.basename(f)
            for f in glob.glob(os.path.join(migrations_dir, "*.sql"))
        )
    pending = [f for f in files if f.split("_")[0] not in applied] if applied else []
    return {
        "latest_applied": latest,
        "applied_count": len(applied),
        "files_count": len(files) if files else None,
        "pending": pending,
    }


def _collected_at() -> str | None:
    try:
        from app.infrastructure.database.repositories.platform_metrics_repository import (  # noqa: PLC0415
            PlatformMetricsRepository,
        )
        pool = _pool()
        if pool is None:
            return None
        row = PlatformMetricsRepository(pool).last_recorded_at()
        ts = row.get("last_recorded_at") if row else None
        return str(ts) if ts else None
    except Exception as exc:
        logger.warning("obs_summary_collected_at_failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# API pública do service
# ---------------------------------------------------------------------------

def get_summary() -> dict[str, Any]:
    """Resumo consolidado da plataforma (visão geral do dashboard).

    Regras de status geral IGUAIS ao /admin/health/platform:
    critical se DB/Redis critical; degraded se R2/Celery degraded.
    """
    r: Any | None
    try:
        r = _get_redis()
        r.ping()
    except Exception as exc:
        logger.warning("obs_summary_redis_conn_failed: %s", exc)
        r = None

    db = _db_section()
    redis_s = _redis_section(r)
    r2 = _r2_section()
    celery_s = _celery_section(r)

    statuses = [db["status"], redis_s["status"], r2["status"], celery_s["status"]]
    if "critical" in statuses:
        overall = "critical"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    summary = {
        "status": overall,
        "services": {
            "database": {k: v for k, v in db.items() if k != "connections"},
            "redis": redis_s,
            "r2": r2,
            "celery": {"status": celery_s["status"]},
        },
        "db": db,
        "celery": celery_s,
        "workers": _workers_section(r),
        "edge": _edge_section(),
        "api": _api_section(),
        "migrations": _migrations_section(),
        "collected_at": _collected_at(),
    }

    if r is not None:
        try:
            r.close()
        except Exception:  # noqa: S110
            pass
    return summary


def get_timeseries(
    scope: str,
    metric: str,
    window: str,
    tenant_id: str | None = None,
    queue: str | None = None,
) -> dict[str, Any]:
    """Série temporal bucketizada de platform_metrics.

    window DEVE estar em WINDOW_BUCKETS (validado na rota — whitelist).
    """
    window_seconds, bucket_seconds = WINDOW_BUCKETS[window]
    since = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)

    from app.infrastructure.database.repositories.platform_metrics_repository import (  # noqa: PLC0415
        PlatformMetricsRepository,
    )
    pool = _pool()
    if pool is None:
        return {"points": [], "window": window, "bucket_seconds": bucket_seconds}
    repo = PlatformMetricsRepository(pool)
    rows = repo.timeseries(
        scope=scope,
        metric=metric,
        since=since,
        bucket_seconds=bucket_seconds,
        tenant_id=tenant_id,
        label_queue=queue,
    )
    points = [
        {
            "bucket": str(row["bucket"]),
            "avg": float(row["avg_value"]) if row.get("avg_value") is not None else None,
            "max": float(row["max_value"]) if row.get("max_value") is not None else None,
            "samples": int(row.get("samples") or 0),
        }
        for row in rows
    ]
    return {"points": points, "window": window, "bucket_seconds": bucket_seconds}


def get_edge_fleet() -> list[dict[str, Any]]:
    """Visão FROTA cross-tenant (superadmin) — último heartbeat por site."""
    from app.core.edge_offline import derive_site_health_status  # noqa: PLC0415
    from app.infrastructure.database.repositories.edge_heartbeat_repository import (  # noqa: PLC0415
        EdgeHeartbeatRepository,
    )
    pool = _pool()
    if pool is None:
        return []
    repo = EdgeHeartbeatRepository(pool)
    rows = repo.get_last_heartbeat_per_site_all_tenants()

    def _num(row: dict, key: str) -> float | None:
        return float(row[key]) if row.get(key) is not None else None

    sites = []
    for row in rows:
        last_hb = row.get("received_at")
        sites.append({
            "site_id": str(row["site_id"]),
            "name": row["site_name"],
            "tenant_id": str(row["tenant_id"]),
            "tenant_name": row.get("tenant_name"),
            "tenant_slug": row.get("tenant_slug"),
            "deployment_mode": row.get("deployment_mode"),
            "site_status": row.get("site_status"),
            "derived_status": derive_site_health_status(
                last_hb, row.get("heartbeat_status")
            ),
            "last_heartbeat_at": str(last_hb) if last_hb else None,
            "inference_fps": _num(row, "inference_fps"),
            "cameras_online": row.get("cameras_online"),
            "cameras_total": row.get("cameras_total"),
            "cpu_pct": _num(row, "cpu_pct"),
            "gpu_pct": _num(row, "gpu_pct"),
            "gpu_temp_c": _num(row, "gpu_temp_c"),
            "cpu_temp_c": _num(row, "cpu_temp_c"),
            "decode_fps": _num(row, "decode_fps"),
            "dropped_frames": row.get("dropped_frames"),
            "queue_depth": row.get("queue_depth"),
            "edge_version": row.get("edge_version"),
        })
    return sites


def _celery_workers_cached(r: Any) -> list[dict[str, Any]]:
    """Workers Celery via inspect (timeout 2s) com cache Redis de 30s."""
    try:
        cached = r.get(_CELERY_INSPECT_CACHE_KEY)
        if cached:
            return json.loads(cached)
    except Exception:  # noqa: S110
        pass
    workers: list[dict[str, Any]] = []
    try:
        from app.infrastructure.queue.celery_app import celery as celery_app  # noqa: PLC0415
        inspector = celery_app.control.inspect(timeout=2)
        active = inspector.active() or {}
        stats = inspector.stats() or {}
        for worker_name, worker_stats in stats.items():
            workers.append({
                "worker_id": worker_name,
                "status": "online",
                "active_tasks": len(active.get(worker_name, [])),
                "pool": (worker_stats.get("pool", {}) or {}).get(
                    "implementation", "unknown"
                ),
            })
        try:
            r.setex(_CELERY_INSPECT_CACHE_KEY, _CELERY_INSPECT_CACHE_TTL,
                    json.dumps(workers))
        except Exception:  # noqa: S110
            pass
    except Exception as exc:
        logger.warning("obs_streams_celery_inspect_failed: %s", exc)
    return workers


def get_streams_aggregate() -> dict[str, Any]:
    """Status de streams de TODAS as câmeras ativas em UMA resposta.

    Mata o N+1 da antiga StreamHealthPage (um GET /cameras/<id>/stream/status
    por câmera). Mesma fonte de verdade: chave Redis epi:stream:{id}:active
    + service:gateway:health (app/api/v1/cameras/stream_handlers.py).
    """
    cameras: list[dict[str, Any]] = []
    pool = _pool()
    rows: list[dict[str, Any]] = []
    if pool is not None:
        try:
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT c.id, c.name, c.location, c.is_active, c.tenant_id, "
                    "       t.name AS tenant_name "
                    "FROM public.cameras c "
                    "LEFT JOIN public.tenants t ON t.id = c.tenant_id "
                    "WHERE c.is_active = true "
                    "ORDER BY t.name NULLS LAST, c.name "
                    "LIMIT 500"
                )
                rows = cur.fetchall()
        except Exception as exc:
            logger.warning("obs_streams_cameras_failed: %s", exc)

    gateway_online = False
    celery_workers: list[dict[str, Any]] = []
    try:
        r = _get_redis()
        gateway_online = bool(r.exists("service:gateway:health"))
        if rows:
            pipe = r.pipeline(transaction=False)
            for row in rows:
                pipe.ttl(f"epi:stream:{row['id']}:active")
            ttls = pipe.execute()
        else:
            ttls = []
        for row, ttl in zip(rows, ttls, strict=False):
            streaming = ttl is not None and int(ttl) > 0
            cameras.append({
                "id": str(row["id"]),
                "name": row["name"],
                "location": row.get("location"),
                "tenant_id": str(row["tenant_id"]) if row.get("tenant_id") else None,
                "tenant_name": row.get("tenant_name"),
                "streaming": streaming,
                "ttl_seconds": int(ttl) if streaming else None,
            })
        celery_workers = _celery_workers_cached(r)
        r.close()
    except Exception as exc:
        logger.warning("obs_streams_redis_failed: %s", exc)
        # Redis fora: devolve câmeras sem status live (streaming=None → UI '—')
        cameras = [
            {
                "id": str(row["id"]),
                "name": row["name"],
                "location": row.get("location"),
                "tenant_id": str(row["tenant_id"]) if row.get("tenant_id") else None,
                "tenant_name": row.get("tenant_name"),
                "streaming": None,
                "ttl_seconds": None,
            }
            for row in rows
        ]

    return {
        "gateway_online": gateway_online,
        "cameras": cameras,
        "cameras_total": len(cameras),
        "cameras_streaming": sum(1 for c in cameras if c["streaming"]),
        "celery_workers": celery_workers,
    }
