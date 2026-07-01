"""
Domain service: per-camera liveness monitoring via heartbeat.

Layer: domain/services
Trigger: called from the worker heartbeat handler on every heartbeat ingest.

Logic:
  cameras_online < cameras_total → ensure one camera_gap alert is open
  cameras_online == cameras_total → acknowledge open camera_gap alerts (recovery)
  cameras_total <= 0 → skip (nothing to monitor)

All operations are best-effort: check_camera_liveness() catches all exceptions
so that a liveness failure never interrupts the heartbeat response.

Tenant isolation: every query is scoped by tenant_id (C-01 multi-tenant).

Related:
  app/infrastructure/database/repositories/liveness_alert_repository.py
  app/api/v1/admin/routes.py (worker_heartbeat handler)
"""
import logging
import os

from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.liveness_alert_repository import (
    LivenessAlertRepository,
)

logger = logging.getLogger(__name__)

# Configurable via env — currently informational (logged but not enforced as a
# time gate). Enforcement can be added later via Redis timestamp tracking.
LIVENESS_GAP_THRESHOLD_MINUTES: int = int(
    os.environ.get("LIVENESS_GAP_THRESHOLD_MINUTES", "5")
)


def check_camera_liveness(
    tenant_id: str,
    site_id: str,
    cameras_online: int,
    cameras_total: int,
    pool: DatabasePool,
) -> None:
    """
    Evaluate camera liveness from a single heartbeat observation.

    Best-effort: any internal exception is caught and logged — callers are
    never interrupted (heartbeat response is preserved).

    Args:
        tenant_id:      Tenant UUID string (scopes all DB queries).
        site_id:        Site/schema identifier (used in evidence_key).
        cameras_online: Cameras currently active/streaming (from heartbeat).
        cameras_total:  Total cameras expected for this site.
        pool:           Live DatabasePool instance.
    """
    try:
        _evaluate(tenant_id, site_id, cameras_online, cameras_total, pool)
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
        _ensure_gap_alert(
            repo, tenant_id, site_id, cameras_online, cameras_total, evidence_key
        )
    else:
        _acknowledge_gap_alerts(repo, tenant_id, site_id, evidence_key)


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
        "(threshold=%dmin)",
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
