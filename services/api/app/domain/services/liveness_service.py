"""
Domain service: per-camera liveness monitoring via heartbeat.

Layer: domain/services
Trigger: called from the worker heartbeat handler on every heartbeat ingest.

Logic:
  cameras_online < cameras_total → gap observed. The FIRST heartbeat that
    observes the gap starts a timer (tracked in Redis, since heartbeats land
    on different gunicorn worker processes — no shared in-memory state).
    Only once the gap has PERSISTED for more than LIVENESS_GAP_THRESHOLD_MINUTES
    does a camera_gap alert get created (idempotent — one open alert per site).
    A gap that resolves before the threshold elapses never creates an alert
    (this is the "silent failure containment" behaviour task-040 asks for —
    without the time gate, any momentary network blip would alert, creating
    noise).
  cameras_online == cameras_total → acknowledge open camera_gap alerts
    (recovery) and clear the Redis gap timer, so the NEXT gap (if any) starts
    counting from zero again instead of reusing a stale timestamp.
  cameras_total <= 0 → skip (nothing to monitor)

All operations are best-effort: check_camera_liveness() catches all exceptions
so that a liveness failure never interrupts the heartbeat response.

Tenant isolation: every query/Redis key is scoped by tenant_id (C-01
multi-tenant) AND site_id, so a slow/gapped site on one tenant never affects
another tenant's (or another site's) timer or alerts.

Related:
  app/infrastructure/database/repositories/liveness_alert_repository.py
  app/api/v1/admin/routes.py (worker_heartbeat handler)
  app/api/v1/cameras/local_stream_manager.py (epi:stream:* Redis key convention
    this module follows for its own epi:liveness:* keys)
"""
import logging
import os
import time
from typing import Any

from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.liveness_alert_repository import (
    LivenessAlertRepository,
)

logger = logging.getLogger(__name__)

# Time gate: a gap must persist longer than this before a camera_gap alert is
# created. Enforced via a Redis-tracked "first seen" timestamp (see
# _get_or_start_gap_timer below) — this is a real enforcement, not advisory.
LIVENESS_GAP_THRESHOLD_MINUTES: int = int(
    os.environ.get("LIVENESS_GAP_THRESHOLD_MINUTES", "5")
)

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

# TTL for the Redis gap-timer key: generous multiple of the threshold so the
# key survives comfortably until the enforcement check fires, but still
# self-cleans (doesn't grow unbounded) if a tenant/site stops sending
# heartbeats entirely. Floor of 30min protects very small thresholds.
_GAP_TIMER_TTL_SECONDS: int = max(LIVENESS_GAP_THRESHOLD_MINUTES * 60 * 3, 1800)


def _get_redis() -> Any:
    import redis as _redis

    return _redis.from_url(_REDIS_URL, socket_timeout=2, decode_responses=True)


def _gap_timer_key(tenant_id: str, site_id: str) -> str:
    """Redis key tracking when a gap was FIRST observed for tenant+site.

    Follows the epi:<domain>:<scope>:<field> convention used by
    local_stream_manager.py (epi:stream:{camera_id}:active).
    """
    return f"epi:liveness:{tenant_id}:{site_id}:gap_since"


def check_camera_liveness(
    tenant_id: str,
    site_id: str,
    cameras_online: int,
    cameras_total: int,
    pool: DatabasePool,
    redis_client: Any = None,
) -> None:
    """
    Evaluate camera liveness from a single heartbeat observation.

    Best-effort: any internal exception is caught and logged — callers are
    never interrupted (heartbeat response is preserved).

    Args:
        tenant_id:      Tenant UUID string (scopes all DB queries + Redis keys).
        site_id:        Site/schema identifier (used in evidence_key + Redis key).
        cameras_online: Cameras currently active/streaming (from heartbeat).
        cameras_total:  Total cameras expected for this site.
        pool:           Live DatabasePool instance.
        redis_client:   Optional injected Redis client (tests). Defaults to a
                        fresh client built from REDIS_URL.
    """
    try:
        _evaluate(tenant_id, site_id, cameras_online, cameras_total, pool, redis_client)
    except Exception as exc:
        logger.warning(
            "liveness_check_error: site=%s tenant=%s err=%s",
            site_id,
            tenant_id,
            exc,
        )


# ---------------------------------------------------------------------------
# Internal helpers — not part of public API
# ---------------------------------------------------------------------------


def _evaluate(
    tenant_id: str,
    site_id: str,
    cameras_online: int,
    cameras_total: int,
    pool: DatabasePool,
    redis_client: Any = None,
) -> None:
    """Core evaluation logic (may raise — callers must handle)."""
    if cameras_total <= 0:
        logger.debug(
            "liveness_skip: site=%s cameras_total=%d (nothing to monitor)",
            site_id,
            cameras_total,
        )
        return

    evidence_key = f"heartbeat/{site_id}"
    repo = LivenessAlertRepository(pool)

    if cameras_online < cameras_total:
        _handle_gap(
            repo, tenant_id, site_id, cameras_online, cameras_total, evidence_key, redis_client
        )
    else:
        # Recovery: clear the timer first (best-effort, never blocks the
        # DB-side acknowledgement below even if Redis is unreachable).
        _clear_gap_timer(tenant_id, site_id, redis_client)
        _acknowledge_gap_alerts(repo, tenant_id, site_id, evidence_key)


def _handle_gap(
    repo: LivenessAlertRepository,
    tenant_id: str,
    site_id: str,
    cameras_online: int,
    cameras_total: int,
    evidence_key: str,
    redis_client: Any = None,
) -> None:
    """Apply the N-minute time gate before ensuring a camera_gap alert exists."""
    gap_since = _get_or_start_gap_timer(tenant_id, site_id, redis_client)
    elapsed_seconds = time.time() - gap_since
    threshold_seconds = LIVENESS_GAP_THRESHOLD_MINUTES * 60

    if elapsed_seconds < threshold_seconds:
        logger.debug(
            "liveness_gap_within_grace_period: site=%s tenant=%s cameras=%d/%d "
            "elapsed=%.0fs threshold=%dmin",
            site_id,
            tenant_id,
            cameras_online,
            cameras_total,
            elapsed_seconds,
            LIVENESS_GAP_THRESHOLD_MINUTES,
        )
        return

    _ensure_gap_alert(
        repo, tenant_id, site_id, cameras_online, cameras_total, evidence_key
    )


def _get_or_start_gap_timer(
    tenant_id: str, site_id: str, redis_client: Any = None
) -> float:
    """
    Return the epoch timestamp (seconds) of when the gap was FIRST observed
    for this tenant+site, atomically starting the timer at "now" if absent.

    Cross-process safe: heartbeats can land on different gunicorn workers, so
    the timer lives in Redis (SET NX), not in-process memory.
    """
    key = _gap_timer_key(tenant_id, site_id)
    r = redis_client or _get_redis()
    try:
        now = time.time()
        started = r.set(key, str(now), nx=True, ex=_GAP_TIMER_TTL_SECONDS)
        if started:
            return now
        existing = r.get(key)
        if existing is None:
            # Lost a race against TTL expiry between the failed SET NX and
            # this GET — treat as a fresh gap starting now.
            r.set(key, str(now), ex=_GAP_TIMER_TTL_SECONDS)
            return now
        return float(existing)
    finally:
        if redis_client is None:
            r.close()


def _clear_gap_timer(tenant_id: str, site_id: str, redis_client: Any = None) -> None:
    """
    Reset the gap timer on recovery so the next gap starts counting from zero.

    Failures are logged, never raised: DB-side acknowledgement must still
    proceed even if Redis happens to be unreachable at recovery time.
    """
    try:
        r = redis_client or _get_redis()
        try:
            r.delete(_gap_timer_key(tenant_id, site_id))
        finally:
            if redis_client is None:
                r.close()
    except Exception as exc:
        logger.warning(
            "liveness_gap_timer_clear_failed: site=%s tenant=%s err=%s",
            site_id,
            tenant_id,
            exc,
        )


def _ensure_gap_alert(
    repo: LivenessAlertRepository,
    tenant_id: str,
    site_id: str,
    cameras_online: int,
    cameras_total: int,
    evidence_key: str,
) -> None:
    """Open a camera_gap alert if one is not already active for this site."""
    existing = repo.get_open_gap_alert(tenant_id, evidence_key)
    if existing:
        logger.debug(
            "liveness_gap_alert_exists: site=%s alert_id=%s cameras=%d/%d",
            site_id,
            existing.get("id"),
            cameras_online,
            cameras_total,
        )
        return

    camera_id = repo.find_camera_for_tenant(tenant_id)
    if not camera_id:
        logger.warning(
            "liveness_gap_no_anchor_camera: site=%s tenant=%s cameras=%d/%d "
            "— no active camera found to anchor alert",
            site_id,
            tenant_id,
            cameras_online,
            cameras_total,
        )
        return

    alert = repo.create_gap_alert(
        camera_id=camera_id,
        tenant_id=tenant_id,
        evidence_key=evidence_key,
        cameras_online=cameras_online,
        cameras_total=cameras_total,
    )
    logger.warning(
        "liveness_gap_alert_created: site=%s tenant=%s cameras=%d/%d alert_id=%s "
        "(persisted >%dmin)",
        site_id,
        tenant_id,
        cameras_online,
        cameras_total,
        alert.get("id") if alert else None,
        LIVENESS_GAP_THRESHOLD_MINUTES,
    )


def _acknowledge_gap_alerts(
    repo: LivenessAlertRepository,
    tenant_id: str,
    site_id: str,
    evidence_key: str,
) -> None:
    """Acknowledge all open camera_gap alerts when cameras are back to full count."""
    count = repo.acknowledge_gap_alerts(tenant_id, evidence_key)
    if count > 0:
        logger.info(
            "liveness_recovery: site=%s tenant=%s acknowledged=%d gap alert(s)",
            site_id,
            tenant_id,
            count,
        )
