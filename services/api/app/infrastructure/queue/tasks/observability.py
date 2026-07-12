"""
Coletor de snapshots de observability — WS11/E2-6.

Grava pontos em public.platform_metrics (migration 088) a cada 60s:
  (a) profundidade (LLEN) das filas Celery estáticas + dinâmicas inference_{schema}
  (b) idade do item mais antigo por fila (best-effort — envelope Celery varia)
  (c) conexões PostgreSQL (pg_stat_activity: active/idle/max)
  (d) Redis INFO (memória, clients) + latência de ping
  (e) delta dos contadores RED da API (apimetrics — app/core/request_metrics.py)
  (f) workers GPU on-premise online (worker:heartbeat:*)
  (g) agregados edge globais (sites por derived_status, cross-tenant)
  (h) sucesso/falha de tasks Celery do dia (celery:stats — signals E2-5)

EXECUÇÃO: NÃO é task Celery agendada — não existe processo celery beat no
deploy (railway_start.py sobe o worker sem -B; habilitar beat acordaria tasks
dormentes de quality com efeitos destrutivos). Roda como daemon thread no
processo worker (run_collector_loop, iniciada em railway_start.py) com lock
Redis `SET obs:collector:lock NX EX 55` — idempotente com múltiplas réplicas.
Também é chamável in-process pelo endpoint POST /admin/observability/collect.

RETENÇÃO: 1x/dia (lock obs:prune:lock) apaga pontos mais antigos que
PLATFORM_METRICS_RETENTION_DAYS (default 30) — em runtime, nunca via migration
(precedente: tasks/retention_expiry.py).
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_STATIC_QUEUES = [
    "inference", "extraction", "training", "versioning",
    "quality_recording", "quality_clips", "quality_cep",
]
_HEARTBEAT_PREFIX = "worker:heartbeat:"
_COLLECT_LOCK_KEY = "obs:collector:lock"
_COLLECT_LOCK_TTL = 55           # < intervalo de 60s
_PRUNE_LOCK_KEY = "obs:prune:lock"
_PRUNE_LOCK_TTL = 82_800         # 23h — garante no máx. 1 prune/dia
_API_PREV_KEY = "obs:apimetrics:prev"
_LOOP_INTERVAL_SECONDS = 60
_DEFAULT_RETENTION_DAYS = 30


def _get_redis() -> Any:
    import redis as _redis  # noqa: PLC0415
    return _redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _ensure_pool() -> Any:
    """Pool DB do processo corrente; inicializa se necessário (daemon thread
    do worker parent não passa por worker_process_init)."""
    from app.infrastructure.database.connection import (  # noqa: PLC0415
        DatabasePool,
        get_database_url,
    )
    pool = DatabasePool.get_instance()
    if pool is None:
        db_url = get_database_url()
        if not db_url:
            return None
        pool = DatabasePool.initialize(db_url, min_conn=1, max_conn=2)
    return pool


def _get_repo() -> Any:
    from app.infrastructure.database.repositories.platform_metrics_repository import (  # noqa: PLC0415
        PlatformMetricsRepository,
    )
    pool = _ensure_pool()
    if pool is None:
        return None
    return PlatformMetricsRepository(pool)


def _dynamic_inference_queues(r: Any) -> list[str]:
    """Filas inference_{schema} dos workers on-premise ativos (heartbeat Redis)."""
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


def _oldest_item_age_seconds(r: Any, queue: str) -> float | None:
    """Idade do item mais antigo da fila via LINDEX -1 (best-effort).

    O envelope Celery não tem timestamp de publicação padronizado — tenta
    headers.timestamp / properties.published_at / headers.eta; retorna None
    se não parseável (UI mostra '—').
    """
    try:
        raw = r.lindex(queue, -1)
        if not raw:
            return None
        envelope = json.loads(raw)
        headers = envelope.get("headers") or {}
        properties = envelope.get("properties") or {}
        ts = (
            headers.get("timestamp")
            or properties.get("published_at")
            or headers.get("eta")
        )
        if ts is None:
            return None
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(ts))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return max((datetime.now(timezone.utc) - dt).total_seconds(), 0.0)
    except Exception:
        return None


def _queue_points(r: Any, queues: list[str]) -> list[dict[str, Any]]:
    """(a)+(b)+(h) — profundidade, idade e ok/fail do dia por fila."""
    points: list[dict[str, Any]] = []
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    for q in queues:
        depth = r.llen(q) or 0
        points.append({
            "scope": "celery", "metric": "queue_depth",
            "value": depth, "labels": {"queue": q},
        })
        age = _oldest_item_age_seconds(r, q)
        if age is not None:
            points.append({
                "scope": "celery", "metric": "queue_oldest_age_s",
                "value": round(age, 1), "labels": {"queue": q},
            })
        stats = r.hgetall(f"celery:stats:{q}:{day}") or {}
        if stats:
            points.append({
                "scope": "celery", "metric": "task_fail_day",
                "value": int(stats.get("fail", 0) or 0), "labels": {"queue": q},
            })
            points.append({
                "scope": "celery", "metric": "task_ok_day",
                "value": int(stats.get("ok", 0) or 0), "labels": {"queue": q},
            })
    return points


def _api_delta_points(r: Any) -> list[dict[str, Any]]:
    """(e) — delta dos contadores RED da hora corrente desde o último ciclo."""
    from app.core.request_metrics import _hour_key, current_hour_snapshot  # noqa: PLC0415

    snap = current_hour_snapshot()
    hour = _hour_key()
    prev_raw = r.get(_API_PREV_KEY)
    prev = json.loads(prev_raw) if prev_raw else None
    if prev and prev.get("hour") == hour:
        d_count = max(snap["count"] - int(prev.get("count", 0)), 0)
        d_4xx = max(snap["err_4xx"] - int(prev.get("err_4xx", 0)), 0)
        d_5xx = max(snap["err_5xx"] - int(prev.get("err_5xx", 0)), 0)
        d_dur = max(snap["dur_ms_sum"] - int(prev.get("dur_ms_sum", 0)), 0)
    else:
        # Virada de hora (ou primeiro ciclo): usa o acumulado da hora corrente
        d_count, d_4xx, d_5xx, d_dur = (
            snap["count"], snap["err_4xx"], snap["err_5xx"], snap["dur_ms_sum"],
        )
    r.set(_API_PREV_KEY, json.dumps({**snap, "hour": hour}), ex=7200)
    avg_ms = round(d_dur / d_count, 1) if d_count else 0.0
    return [
        {"scope": "api", "metric": "http_count", "value": d_count},
        {"scope": "api", "metric": "http_4xx", "value": d_4xx},
        {"scope": "api", "metric": "http_5xx", "value": d_5xx},
        {"scope": "api", "metric": "http_avg_ms", "value": avg_ms},
    ]


def _db_connection_points() -> list[dict[str, Any]]:
    """(c) — conexões do PostgreSQL (pg_stat_activity) + latência de SELECT."""
    pool = _ensure_pool()
    if pool is None:
        return []
    with pool.get_connection() as conn:
        cur = conn.cursor()
        start = time.perf_counter()
        cur.execute(
            "SELECT count(*) FILTER (WHERE state = 'active') AS active, "
            "       count(*) FILTER (WHERE state = 'idle')   AS idle, "
            "       current_setting('max_connections')::int  AS max_conn "
            "FROM pg_stat_activity"
        )
        row = cur.fetchone()
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
    if not row:
        return []
    return [
        {"scope": "db", "metric": "conn_active", "value": int(row["active"] or 0)},
        {"scope": "db", "metric": "conn_idle", "value": int(row["idle"] or 0)},
        {"scope": "db", "metric": "conn_max", "value": int(row["max_conn"] or 0)},
        {"scope": "db", "metric": "latency_ms", "value": latency_ms},
    ]


def _edge_fleet_points() -> list[dict[str, Any]]:
    """(g) — contagem global de sites por derived_status (cross-tenant)."""
    from app.core.edge_offline import derive_site_health_status  # noqa: PLC0415
    from app.infrastructure.database.repositories.edge_heartbeat_repository import (  # noqa: PLC0415
        EdgeHeartbeatRepository,
    )
    pool = _ensure_pool()
    if pool is None:
        return []
    repo = EdgeHeartbeatRepository(pool)
    rows = repo.get_last_heartbeat_per_site_all_tenants()
    counts = {"healthy": 0, "degraded": 0, "critical": 0, "offline": 0}
    for row in rows:
        if row.get("site_status") == "provisioning":
            continue  # provisioning nunca conta como offline (regra da casa)
        status = derive_site_health_status(
            row.get("received_at"), row.get("heartbeat_status")
        )
        counts[status] = counts.get(status, 0) + 1
    return [
        {"scope": "edge", "metric": "sites_total", "value": len(rows)},
        {"scope": "edge", "metric": "sites_offline", "value": counts["offline"]},
        {"scope": "edge", "metric": "sites_degraded", "value": counts["degraded"]},
        {"scope": "edge", "metric": "sites_critical", "value": counts["critical"]},
    ]


def collect_platform_metrics() -> int:
    """Um snapshot completo → INSERT batch em platform_metrics.

    Cada seção é isolada em try/except: fonte indisponível degrada sem
    derrubar o ciclo. Retorna o total de pontos gravados.
    """
    repo = _get_repo()
    if repo is None:
        logger.warning("obs_collect_skipped: DatabasePool indisponível")
        return 0

    points: list[dict[str, Any]] = []
    r: Any = None
    try:
        r = _get_redis()
        start = time.perf_counter()
        r.ping()
        redis_latency_ms = round((time.perf_counter() - start) * 1000, 1)
    except Exception as exc:
        logger.warning("obs_collect_redis_unavailable: %s", exc)
        r = None
        redis_latency_ms = None

    if r is not None:
        try:
            dynamic = _dynamic_inference_queues(r)
            points.extend(_queue_points(r, [*_STATIC_QUEUES, *dynamic]))
            points.append({
                "scope": "workers", "metric": "workers_online",
                "value": len(dynamic),
            })
        except Exception as exc:
            logger.warning("obs_collect_queues_failed: %s", exc)

        try:
            info = r.info()
            points.append({
                "scope": "redis", "metric": "redis_mem_mb",
                "value": round(int(info.get("used_memory", 0)) / 1_048_576, 2),
            })
            points.append({
                "scope": "redis", "metric": "redis_clients",
                "value": int(info.get("connected_clients", 0)),
            })
            if redis_latency_ms is not None:
                points.append({
                    "scope": "redis", "metric": "latency_ms",
                    "value": redis_latency_ms,
                })
        except Exception as exc:
            logger.warning("obs_collect_redis_info_failed: %s", exc)

        try:
            points.extend(_api_delta_points(r))
        except Exception as exc:
            logger.warning("obs_collect_api_failed: %s", exc)

    try:
        points.extend(_db_connection_points())
    except Exception as exc:
        logger.warning("obs_collect_db_failed: %s", exc)

    try:
        points.extend(_edge_fleet_points())
    except Exception as exc:
        logger.warning("obs_collect_edge_failed: %s", exc)

    if r is not None:
        try:
            r.close()
        except Exception:  # noqa: S110
            pass

    inserted = repo.insert_points(points) if points else 0
    logger.info("obs_collect_done: points=%d", inserted)
    return inserted


def prune_old_metrics() -> int:
    """Retenção em runtime — apaga pontos além de PLATFORM_METRICS_RETENTION_DAYS."""
    repo = _get_repo()
    if repo is None:
        return 0
    try:
        days = int(os.environ.get(
            "PLATFORM_METRICS_RETENTION_DAYS", str(_DEFAULT_RETENTION_DAYS)
        ))
    except ValueError:
        days = _DEFAULT_RETENTION_DAYS
    deleted = repo.prune_older_than(days)
    logger.info("obs_prune_done: days=%d deleted=%d", days, deleted)
    return deleted


def run_collector_loop() -> None:
    """Loop infinito (chamar SOMENTE em daemon thread do processo worker).

    IMPORTANTE: dorme ANTES do primeiro ciclo — o Celery prefork forka os
    worker children logo após o boot; criar o pool psycopg2 no processo pai
    antes do fork compartilharia sockets com os filhos (corrupção). Após 60s
    os forks já aconteceram e cada processo tem seu próprio pool.
    """
    logger.info(
        "obs_collector_loop_started: interval=%ds lock=%s",
        _LOOP_INTERVAL_SECONDS, _COLLECT_LOCK_KEY,
    )
    while True:
        time.sleep(_LOOP_INTERVAL_SECONDS)
        try:
            r = _get_redis()
            if r.set(_COLLECT_LOCK_KEY, "1", nx=True, ex=_COLLECT_LOCK_TTL):
                collect_platform_metrics()
            if r.set(_PRUNE_LOCK_KEY, "1", nx=True, ex=_PRUNE_LOCK_TTL):
                prune_old_metrics()
            r.close()
        except Exception as exc:
            logger.warning("obs_collector_cycle_failed: %s", exc)
