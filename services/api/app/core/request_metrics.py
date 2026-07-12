"""
CORE request_metrics.py — Instrumentação RED (Rate/Errors/Duration) da API.

Layer: core
Pattern: Flask before/after_request hooks + contadores horários em Redis

Contadores em hash Redis `apimetrics:{YYYYMMDDHH}` (UTC):
  count       — total de requests
  err_4xx     — respostas 4xx
  err_5xx     — respostas 5xx
  dur_ms_sum  — soma das durações em ms (int)

Regras:
  - EXPIRE 48h por chave (2 dias de histórico horário)
  - Falha de Redis é SILENCIOSA (logger.debug) — nunca derruba a request
  - Paths de polling de infraestrutura (/health, /streams) são excluídos
    para não poluir a taxa com health checks

Consumidores:
  - GET /api/v1/admin/health/metrics (errors_24h / avg_response_ms reais)
  - Coletor de observability (snapshot http_count/http_5xx/http_avg_ms
    para a série platform_metrics)

Related: app/api/v1/admin/routes.py, app/infrastructure/queue/tasks/observability.py
"""
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Flask, g, request

logger = logging.getLogger(__name__)

_KEY_PREFIX = "apimetrics:"
_KEY_TTL_SECONDS = 172_800  # 48h
_EXCLUDED_PREFIXES = ("/health", "/api/v1/health", "/streams", "/api/streams")

_redis_client: Any = None


def _get_redis() -> Any:
    """Cliente Redis lazy com timeouts curtos (métrica nunca atrasa request)."""
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


def _hour_key(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return f"{_KEY_PREFIX}{dt.strftime('%Y%m%d%H')}"


def _is_excluded(path: str) -> bool:
    return any(path.startswith(p) for p in _EXCLUDED_PREFIXES)


def register_request_metrics(app: Flask) -> None:
    """Registra hooks before/after_request de instrumentação RED."""

    @app.before_request
    def _mark_start() -> None:
        g._req_metrics_start = time.perf_counter()

    @app.after_request
    def _record(response):  # type: ignore[no-untyped-def]
        try:
            if _is_excluded(request.path):
                return response
            start = getattr(g, "_req_metrics_start", None)
            dur_ms = (
                int((time.perf_counter() - start) * 1000)
                if start is not None
                else 0
            )
            key = _hour_key()
            r = _get_redis()
            pipe = r.pipeline(transaction=False)
            pipe.hincrby(key, "count", 1)
            if 400 <= response.status_code < 500:
                pipe.hincrby(key, "err_4xx", 1)
            elif response.status_code >= 500:
                pipe.hincrby(key, "err_5xx", 1)
            pipe.hincrby(key, "dur_ms_sum", dur_ms)
            pipe.expire(key, _KEY_TTL_SECONDS)
            pipe.execute()
        except Exception as exc:  # métrica nunca derruba a request
            logger.debug("request_metrics_record_failed: %s", exc)
        return response


def aggregate_last_hours(hours: int = 24) -> dict[str, float]:
    """Soma os contadores das últimas N chaves horárias (default 24h).

    Retorna dict com count, err_4xx, err_5xx, dur_ms_sum e avg_ms derivado.
    Redis indisponível → zeros (degrada sem levantar exceção).
    """
    totals: dict[str, int] = {"count": 0, "err_4xx": 0, "err_5xx": 0, "dur_ms_sum": 0}
    try:
        r = _get_redis()
        now = datetime.now(timezone.utc)
        pipe = r.pipeline(transaction=False)
        for i in range(hours):
            pipe.hgetall(_hour_key(now - timedelta(hours=i)))
        for h in pipe.execute():
            for k in totals:
                totals[k] += int((h or {}).get(k, 0) or 0)
    except Exception as exc:
        logger.debug("request_metrics_aggregate_failed: %s", exc)
    avg_ms = (totals["dur_ms_sum"] / totals["count"]) if totals["count"] else 0.0
    return {**totals, "avg_ms": round(avg_ms, 1)}


def current_hour_snapshot() -> dict[str, int]:
    """Contadores brutos da hora corrente (o coletor calcula deltas).

    Redis indisponível → zeros (nunca levanta exceção).
    """
    empty = {"count": 0, "err_4xx": 0, "err_5xx": 0, "dur_ms_sum": 0}
    try:
        r = _get_redis()
        h = r.hgetall(_hour_key()) or {}
        return {k: int(h.get(k, 0) or 0) for k in empty}
    except Exception as exc:
        logger.debug("request_metrics_snapshot_failed: %s", exc)
        return empty
