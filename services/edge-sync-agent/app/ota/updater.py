"""Orchestrates one OTA cycle: compare target_ref vs current, build + smoke-check
+ swap + restart + verify, roll back on failed post-restart health.

**Runs as a SEPARATE process/unit from the daemon it updates — this is not a
detail, it's load-bearing.** `systemctl --user restart edge-sync-agent` kills
the whole edge-sync-agent process (and everything in its cgroup) almost
immediately after being issued. If this orchestration ran as a thread *inside*
that same process (the way config_poller/uploader/heartbeat do), the restart
would kill the very code trying to verify it and roll back on failure —
silently defeating the one thing this feature exists for ("nunca bricar o
box"). So this module is invoked by its own systemd --user timer/oneshot unit
(`edge-sync-agent-updater.service`, PR-D/OTA deploy), decoupled from the
daemon's cgroup. See docs/runbooks/edge-ota.md.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import release_manager as rm

logger = logging.getLogger(__name__)

_DEFAULT_HEALTH_RETRIES = 5
_DEFAULT_HEALTH_INTERVAL_S = 6.0
_DEFAULT_HEARTBEAT_FRESH_S = 90.0  # > heartbeat interval (45s, PR-B) with margin
_DEFAULT_KEEP_LAST = 3


@dataclass
class UpdateResult:
    action: str  # "noop" | "updated" | "rollback"
    ref: str
    rolled_back: bool = False
    healthy: bool = True


def _service_active(unit: str, *, runner: Callable = subprocess.run) -> bool:
    result = runner(
        ["systemctl", "--user", "is-active", unit], capture_output=True, text=True, timeout=15
    )
    return result.stdout.strip() == "active"


def _restart_service(unit: str, *, runner: Callable = subprocess.run) -> None:
    runner(["systemctl", "--user", "restart", unit], capture_output=True, text=True, timeout=30)


def _heartbeat_fresh(
    sentinel_path: str, max_age_s: float, *, clock: Callable[[], float] = time.time
) -> bool:
    p = Path(sentinel_path)
    if not p.exists():
        return False
    return (clock() - p.stat().st_mtime) <= max_age_s


def _wait_for_health(
    unit: str,
    sentinel_path: str,
    *,
    retries: int,
    interval_s: float,
    heartbeat_fresh_s: float,
    runner: Callable = subprocess.run,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> bool:
    for attempt in range(1, retries + 1):
        sleep(interval_s)
        if _service_active(unit, runner=runner) and _heartbeat_fresh(
            sentinel_path, heartbeat_fresh_s, clock=clock
        ):
            return True
        logger.warning("ota_health_check_retry attempt=%d/%d", attempt, retries)
    return False


def run_once(
    *,
    source_repo: str,
    releases_root: str,
    current_symlink: str,
    unit_name: str,
    sentinel_path: str,
    fetch_target_ref: Callable[[], str],
    keep_last: int = _DEFAULT_KEEP_LAST,
    health_retries: int = _DEFAULT_HEALTH_RETRIES,
    health_interval_s: float = _DEFAULT_HEALTH_INTERVAL_S,
    heartbeat_fresh_s: float = _DEFAULT_HEARTBEAT_FRESH_S,
    runner: Callable = subprocess.run,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> UpdateResult:
    """One OTA cycle. Idempotent / safe to call repeatedly (e.g. from a
    systemd timer) — a no-op once `current` already matches `target_ref`.
    """
    target_ref = fetch_target_ref()
    active_ref = rm.current_ref(current_symlink, releases_root)

    if target_ref == active_ref:
        logger.info("ota_noop ref=%s already current", target_ref)
        return UpdateResult("noop", active_ref or "")

    logger.info("ota_update_start from=%s to=%s", active_ref, target_ref)
    try:
        rm.fetch(source_repo, runner=runner)
        service_dir = rm.build_release(source_repo, releases_root, target_ref, runner=runner)
        rm.smoke_check(service_dir, runner=runner)
    except rm.ReleaseError as exc:
        logger.error("ota_build_failed ref=%s %s — mantendo release atual", target_ref, exc)
        return UpdateResult("noop", active_ref or "", healthy=True)

    previous_ref = active_ref
    rm.swap_current(current_symlink, service_dir)
    _restart_service(unit_name, runner=runner)

    healthy = _wait_for_health(
        unit_name,
        sentinel_path,
        retries=health_retries,
        interval_s=health_interval_s,
        heartbeat_fresh_s=heartbeat_fresh_s,
        runner=runner,
        sleep=sleep,
        clock=clock,
    )
    if healthy:
        logger.info("ota_update_ok ref=%s", target_ref)
        keep = {target_ref}
        if previous_ref:
            keep.add(previous_ref)
        rm.prune_releases(releases_root, keep, keep_last=keep_last)
        return UpdateResult("updated", target_ref)

    logger.error("ota_health_failed ref=%s — rolling back to %s", target_ref, previous_ref)
    if previous_ref is None:
        logger.critical(
            "ota_rollback_impossible ref=%s: sem release anterior — "
            "deixando no ar (pode estar degradado); intervenção manual",
            target_ref,
        )
        return UpdateResult("rollback", target_ref, rolled_back=False, healthy=False)

    prev_service_dir = rm.service_dir_for(releases_root, previous_ref)
    rm.swap_current(current_symlink, prev_service_dir)
    _restart_service(unit_name, runner=runner)
    rollback_healthy = _wait_for_health(
        unit_name,
        sentinel_path,
        retries=health_retries,
        interval_s=health_interval_s,
        heartbeat_fresh_s=heartbeat_fresh_s,
        runner=runner,
        sleep=sleep,
        clock=clock,
    )
    if not rollback_healthy:
        logger.critical(
            "ota_rollback_unhealthy ref=%s — intervenção manual necessária", previous_ref
        )
    return UpdateResult(
        "rollback", previous_ref, rolled_back=True, healthy=rollback_healthy
    )
