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
from typing import Callable, Sequence

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


def _restart_secondary_units(units: Sequence[str], *, runner: Callable = subprocess.run) -> None:
    """Best-effort restart of the OTHER units that run out of the same
    `current` symlink (frame-collector, live-view, ...) so they pick up the
    release this cycle just applied — the debt this closes: the updater used
    to recycle only `unit_name` (edge-sync-agent), so those units kept
    running the OLD release's code until someone SSHed in and restarted them
    by hand (see docs/REGISTRO_DE_DECISOES.md D-42's operational note).

    Deliberately NOT part of the health-check contract: only edge-sync-agent
    talks to the cloud and touches the heartbeat sentinel, so there's no
    independent signal to validate these against. A failed restart here is
    logged loudly (it's real operational signal — the unit is now serving
    stale code) but never raises and never influences rollback: the primary
    unit's health is still the sole source of truth for "is this release
    good".
    """
    for unit in units:
        try:
            result = runner(
                ["systemctl", "--user", "restart", unit],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.error("ota_secondary_restart_error unit=%s %s", unit, exc)
            continue
        if getattr(result, "returncode", 0) == 0:
            logger.info("ota_secondary_restart_ok unit=%s", unit)
        else:
            logger.error(
                "ota_secondary_restart_failed unit=%s rc=%s stderr=%s",
                unit,
                result.returncode,
                (result.stderr or "").strip(),
            )


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
    secondary_unit_names: Sequence[str] = (),
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

    `unit_name` (edge-sync-agent) is the only unit whose health actually
    gates this cycle's outcome — it's the one with a heartbeat sentinel to
    validate against. `secondary_unit_names` (frame-collector, live-view,
    ...) run out of the same `current` symlink but are recycled best-effort,
    AFTER `unit_name`'s fate for this cycle is decided (updated or rolled
    back) — never before, so a secondary is never pushed onto a release that
    turns out to fail `unit_name`'s health check.
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
        _restart_secondary_units(secondary_unit_names, runner=runner)
        return UpdateResult("updated", target_ref)

    logger.error("ota_health_failed ref=%s — rolling back to %s", target_ref, previous_ref)
    if previous_ref is None:
        logger.critical(
            "ota_rollback_impossible ref=%s: sem release anterior — "
            "deixando no ar (pode estar degradado); intervenção manual",
            target_ref,
        )
        # Secondaries are deliberately left untouched here: `current` is
        # still pointing at the release that JUST failed `unit_name`'s
        # health check (there's nothing known-good to fall back to), so
        # cycling frame-collector/live-view onto it buys nothing and only
        # adds risk on top of a state that already needs a human.
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
    # Recycle secondaries here too, matching wherever `current` ends up —
    # back at `previous_ref` after this rollback — mirroring the success-path
    # call above. Both call sites fire only once unit_name's fate for the
    # cycle is settled, so a secondary is never restarted onto a release
    # that's still mid-validation; leaving this call out of the rollback
    # branch would make that guarantee depend on secondaries never having
    # been touched earlier in the cycle, which is true today but fragile.
    _restart_secondary_units(secondary_unit_names, runner=runner)
    return UpdateResult(
        "rollback", previous_ref, rolled_back=True, healthy=rollback_healthy
    )
