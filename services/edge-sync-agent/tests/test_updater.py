"""Tests for updater.run_once: version comparison, build->swap->restart->health
flow, and rollback on failed post-restart health. subprocess/git/venv/time are
always mocked or driven via tmp_path — no real git/venv/network/sleep."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.ota.release_manager import SERVICE_SUBDIR
from app.ota.updater import UpdateResult, run_once


def _ok(stdout=""):
    r = MagicMock()
    r.returncode = 0
    r.stdout = stdout
    r.stderr = ""
    return r


def _healthy_runner():
    """Fakes git/venv/systemctl without ever shelling out for real:
    - `git worktree add <dir> <ref>` -> creates <dir>/SERVICE_SUBDIR (what git
      would really do), so later filesystem checks (prune, current_ref) see a
      real release tree.
    - `python3 -m venv <dir>` -> creates <dir>/bin (just enough to make
      "already built" checks work on retry).
    - `systemctl --user is-active ...` -> reports 'active' (service side of
      the health check passes, so tests can isolate the sentinel-freshness
      half of "serviço de pé + heartbeat volta a reportar").
    - anything else (pip install, systemctl restart) -> just succeeds.
    """

    def _run(args, **kwargs):
        if "worktree" in args:
            release_dir = args[-2]
            Path(release_dir, SERVICE_SUBDIR).mkdir(parents=True, exist_ok=True)
        elif args[:2] == ["python3", "-m"] and "venv" in args:
            Path(args[-1], "bin").mkdir(parents=True, exist_ok=True)
        elif "is-active" in args:
            return _ok(stdout="active")
        return _ok()

    return MagicMock(side_effect=_run)


def _healthy_runner_with_secondary_failure(bad_unit):
    """Same fakes as `_healthy_runner()`, except `systemctl --user restart
    <bad_unit>` reports failure (non-zero rc, as a real "unit not found" or
    crashed-on-start would) — unit_name's own restart/health path is
    untouched, so tests using this can isolate "one secondary fails to
    restart" from everything else."""

    def _run(args, **kwargs):
        if "worktree" in args:
            release_dir = args[-2]
            Path(release_dir, SERVICE_SUBDIR).mkdir(parents=True, exist_ok=True)
        elif args[:2] == ["python3", "-m"] and "venv" in args:
            Path(args[-1], "bin").mkdir(parents=True, exist_ok=True)
        elif "is-active" in args:
            return _ok(stdout="active")
        elif "restart" in args and args[-1] == bad_unit:
            return MagicMock(returncode=1, stdout="", stderr="unit not found")
        return _ok()

    return MagicMock(side_effect=_run)


def _mkcurrent(tmp_path, ref):
    """Points `current` at an existing release for `ref` (as if already deployed)."""
    service_dir = tmp_path / "releases" / ref / SERVICE_SUBDIR
    service_dir.mkdir(parents=True)
    current = tmp_path / "current"
    current.symlink_to(service_dir)
    return current, service_dir


def _mkcurrent_bootstrap(tmp_path):
    """Points `current` straight at a raw checkout, NOT under releases/<ref>/ —
    matches deploy/install.sh's `_bootstrap_current_symlink` (first-ever
    install, before any OTA cycle has run)."""
    service_dir = tmp_path / "recognition-src" / SERVICE_SUBDIR
    service_dir.mkdir(parents=True)
    current = tmp_path / "current"
    current.symlink_to(service_dir)
    return current, service_dir


def _base_kwargs(tmp_path, **overrides):
    kwargs = dict(
        source_repo=str(tmp_path / "src"),
        releases_root=str(tmp_path / "releases"),
        current_symlink=str(tmp_path / "current"),
        unit_name="edge-sync-agent",
        sentinel_path=str(tmp_path / "heartbeat.ok"),
        runner=_healthy_runner(),
        sleep=lambda _s: None,
        health_interval_s=0.0,
    )
    kwargs.update(overrides)
    return kwargs


def _fresh_sentinel(path, clock_time):
    Path(path).write_text("")
    os.utime(path, (clock_time, clock_time))


# ── no-op ────────────────────────────────────────────────────────────────────

def test_noop_when_target_ref_matches_current(tmp_path):
    _mkcurrent(tmp_path, "abc123")
    runner = MagicMock()

    result = run_once(
        fetch_target_ref=lambda: "abc123", **_base_kwargs(tmp_path, runner=runner)
    )

    assert result == UpdateResult("noop", "abc123")
    runner.assert_not_called()  # never touches git/venv when already current


def test_first_ever_install_active_ref_is_none(tmp_path):
    """No `current` symlink yet -> active_ref is None, any target triggers an update."""
    runner = _healthy_runner()

    def clock():
        return 1_700_000_100.0

    def _fetch():
        return "abc123"

    _fresh_sentinel(tmp_path / "heartbeat.ok", 1_700_000_100.0)

    result = run_once(
        fetch_target_ref=_fetch,
        health_retries=1,
        clock=clock,
        **_base_kwargs(tmp_path, runner=runner),
    )

    assert result.action == "updated"
    assert result.ref == "abc123"


# ── successful update ────────────────────────────────────────────────────────

def test_successful_update_swaps_current_and_prunes(tmp_path):
    _mkcurrent(tmp_path, "old-ref")
    runner = _healthy_runner()

    def clock():
        return 1_700_000_100.0

    _fresh_sentinel(tmp_path / "heartbeat.ok", 1_700_000_100.0)

    result = run_once(
        fetch_target_ref=lambda: "new-ref",
        health_retries=1,
        clock=clock,
        **_base_kwargs(tmp_path, runner=runner),
    )

    assert result == UpdateResult("updated", "new-ref")
    assert os.readlink(tmp_path / "current") == str(
        tmp_path / "releases" / "new-ref" / SERVICE_SUBDIR
    )
    restart_calls = [c for c in runner.call_args_list if "restart" in c.args[0]]
    assert len(restart_calls) == 1
    assert restart_calls[0].args[0] == ["systemctl", "--user", "restart", "edge-sync-agent"]


def test_successful_update_keeps_new_and_previous_release(tmp_path):
    _mkcurrent(tmp_path, "old-ref")
    (tmp_path / "releases" / "ancient-ref" / SERVICE_SUBDIR).mkdir(parents=True)
    os.utime(tmp_path / "releases" / "ancient-ref", (1_000, 1_000))

    def clock():
        return 1_700_000_100.0

    _fresh_sentinel(tmp_path / "heartbeat.ok", 1_700_000_100.0)

    run_once(
        fetch_target_ref=lambda: "new-ref",
        health_retries=1,
        keep_last=2,
        clock=clock,
        **_base_kwargs(tmp_path, runner=_healthy_runner()),
    )

    remaining = {p.name for p in (tmp_path / "releases").iterdir()}
    assert remaining == {"new-ref", "old-ref"}
    assert "ancient-ref" not in remaining


# ── secondary units (frame-collector, live-view, ...) ─────────────────────────
# OTA used to recycle only unit_name (edge-sync-agent) — frame-collector and
# live-view kept running the OLD release's code until someone restarted them
# by hand on the box (docs/REGISTRO_DE_DECISOES.md D-42's operational note).

def test_successful_update_restarts_secondary_units_after_primary_health_ok(tmp_path):
    _mkcurrent(tmp_path, "old-ref")
    runner = _healthy_runner()

    def clock():
        return 1_700_000_100.0

    _fresh_sentinel(tmp_path / "heartbeat.ok", 1_700_000_100.0)

    result = run_once(
        fetch_target_ref=lambda: "new-ref",
        health_retries=1,
        clock=clock,
        secondary_unit_names=("edge-frame-collector", "edge-live-view"),
        **_base_kwargs(tmp_path, runner=runner),
    )

    assert result == UpdateResult("updated", "new-ref")
    restart_calls = [c.args[0] for c in runner.call_args_list if "restart" in c.args[0]]
    # unit_name restarts (and is validated) FIRST; secondaries only get
    # recycled once that verdict is in — never before, never in parallel.
    assert restart_calls == [
        ["systemctl", "--user", "restart", "edge-sync-agent"],
        ["systemctl", "--user", "restart", "edge-frame-collector"],
        ["systemctl", "--user", "restart", "edge-live-view"],
    ]


def test_secondary_restart_failure_does_not_block_or_rollback(tmp_path):
    """A secondary failing to restart is real operational signal (logged
    loudly — see the caller's log assertions in prod) but it is NOT a
    release failure: only unit_name's health decides updated vs rollback."""
    _mkcurrent(tmp_path, "old-ref")
    runner = _healthy_runner_with_secondary_failure("edge-frame-collector")
    _fresh_sentinel(tmp_path / "heartbeat.ok", 1_700_000_100.0)

    result = run_once(
        fetch_target_ref=lambda: "new-ref",
        health_retries=1,
        clock=lambda: 1_700_000_100.0,
        secondary_unit_names=("edge-frame-collector", "edge-live-view"),
        **_base_kwargs(tmp_path, runner=runner),
    )

    assert result == UpdateResult("updated", "new-ref")
    restart_units = [c.args[0][-1] for c in runner.call_args_list if "restart" in c.args[0]]
    # The failing secondary did NOT short-circuit the loop — the other
    # secondary was still attempted afterwards.
    assert restart_units == ["edge-sync-agent", "edge-frame-collector", "edge-live-view"]


def test_noop_does_not_restart_secondary_units(tmp_path):
    _mkcurrent(tmp_path, "abc123")
    runner = MagicMock()

    result = run_once(
        fetch_target_ref=lambda: "abc123",
        secondary_unit_names=("edge-frame-collector", "edge-live-view"),
        **_base_kwargs(tmp_path, runner=runner),
    )

    assert result == UpdateResult("noop", "abc123")
    runner.assert_not_called()


# ── build failure: never swaps ───────────────────────────────────────────────

def test_build_failure_never_swaps_current(tmp_path):
    _mkcurrent(tmp_path, "old-ref")

    def _run(args, **kwargs):
        if "worktree" in args:
            return MagicMock(returncode=1, stdout="", stderr="worktree failed")
        return _ok()

    failing_runner = MagicMock(side_effect=_run)

    result = run_once(
        fetch_target_ref=lambda: "bad-ref",
        **_base_kwargs(tmp_path, runner=failing_runner),
    )

    assert result.action == "noop"
    assert os.readlink(tmp_path / "current") == str(
        tmp_path / "releases" / "old-ref" / SERVICE_SUBDIR
    )


# ── rollback on failed post-restart health ──────────────────────────────────

def test_rollback_when_health_check_fails(tmp_path):
    _mkcurrent(tmp_path, "old-ref")
    # No sentinel file ever created -> heartbeat never looks fresh -> unhealthy.
    runner = _healthy_runner()

    result = run_once(
        fetch_target_ref=lambda: "broken-ref",
        health_retries=2,
        clock=lambda: 1_700_000_100.0,
        **_base_kwargs(tmp_path, runner=runner),
    )

    assert result.action == "rollback"
    assert result.ref == "old-ref"
    assert result.rolled_back is True
    # current points back at the OLD release, not the broken one.
    assert os.readlink(tmp_path / "current") == str(
        tmp_path / "releases" / "old-ref" / SERVICE_SUBDIR
    )
    restart_calls = [c for c in runner.call_args_list if "restart" in c.args[0]]
    assert len(restart_calls) == 2  # once to the broken release, once back


def test_rollback_restarts_secondary_units_too(tmp_path):
    """Symmetry: unit_name gets restarted TWICE here (onto the broken
    release, then back). The secondaries must not be left stuck on
    whatever they were running before this cycle — they get recycled once,
    AFTER `current` is back at the previous (known-good) release, so they
    end up matching unit_name's final state, not the release that failed."""
    _mkcurrent(tmp_path, "old-ref")
    runner = _healthy_runner()  # no sentinel ever created -> unhealthy -> rollback

    result = run_once(
        fetch_target_ref=lambda: "broken-ref",
        health_retries=1,
        clock=lambda: 1_700_000_100.0,
        secondary_unit_names=("edge-frame-collector", "edge-live-view"),
        **_base_kwargs(tmp_path, runner=runner),
    )

    assert result.action == "rollback"
    assert result.rolled_back is True
    restart_units = [c.args[0][-1] for c in runner.call_args_list if "restart" in c.args[0]]
    assert restart_units == [
        "edge-sync-agent",  # 1st: swapped onto broken-ref, restarted, failed health
        "edge-sync-agent",  # 2nd: rolled back onto old-ref, restarted again
        "edge-frame-collector",  # only now, matching the reverted `current`
        "edge-live-view",
    ]


def test_rollback_impossible_on_first_ever_install_failure(tmp_path):
    """No previous release to roll back to (first install) -> stays on the
    new (unhealthy) ref, flagged as unhealthy for the operator, not silently
    swapped to nothing."""
    runner = _healthy_runner()

    result = run_once(
        fetch_target_ref=lambda: "first-ref",
        health_retries=1,
        clock=lambda: 1_700_000_100.0,
        **_base_kwargs(tmp_path, runner=runner),
    )

    assert result.action == "rollback"
    assert result.rolled_back is False
    assert result.healthy is False
    assert result.ref == "first-ref"


def test_rollback_impossible_does_not_restart_secondary_units(tmp_path):
    """No previous release to fall back to -> `current` is left pointing at
    the release that JUST failed unit_name's health check. Cycling the
    secondaries onto that same known-bad code buys nothing and only adds
    risk on top of a state that already needs manual intervention, so they
    are deliberately left untouched (contrast with the rollback-with-a-
    previous-release case, which DOES recycle them, back onto known-good
    code)."""
    runner = _healthy_runner()

    result = run_once(
        fetch_target_ref=lambda: "first-ref",
        health_retries=1,
        clock=lambda: 1_700_000_100.0,
        secondary_unit_names=("edge-frame-collector", "edge-live-view"),
        **_base_kwargs(tmp_path, runner=runner),
    )

    assert result.rolled_back is False
    assert result.healthy is False
    restart_units = [c.args[0][-1] for c in runner.call_args_list if "restart" in c.args[0]]
    assert restart_units == ["edge-sync-agent"]  # only the primary was ever touched


def test_rollback_impossible_from_bootstrap_current_never_swaps_to_a_bogus_path(tmp_path):
    """Regression (found on real hardware, gate 1.6, PR #235): the very
    first OTA cycle after `deploy/install.sh`'s bootstrap has `current`
    pointing straight at a raw checkout, not at releases/<ref>/.... `current`
    still swaps to the newly built (real) release to try it — that part is
    correct and unavoidable. What must NOT happen: before the fix,
    current_ref() fabricated a ref name from the bootstrap path, so on a
    failed health check the "rollback" swapped `current` a SECOND time, to
    releases/<that-fabricated-name>/... — a path that never existed,
    breaking the daemon (systemd 203/EXEC) instead of protecting it. The
    load-bearing property: `current` always resolves to something that
    genuinely exists on disk, never a guessed path.
    """
    current, bootstrap_service_dir = _mkcurrent_bootstrap(tmp_path)
    runner = _healthy_runner()

    result = run_once(
        fetch_target_ref=lambda: "new-ref",
        health_retries=1,
        clock=lambda: 1_700_000_100.0,
        **_base_kwargs(tmp_path, runner=runner),
    )

    assert result.action == "rollback"
    assert result.rolled_back is False
    assert result.healthy is False
    assert result.ref == "new-ref"
    # It tried the new (real) release — moved off the bootstrap path...
    assert os.readlink(current) != str(bootstrap_service_dir)
    assert os.readlink(current) == str(
        tmp_path / "releases" / "new-ref" / SERVICE_SUBDIR
    )
    # ...but never attempted a second swap to a fabricated "previous" path:
    # whatever current points at right now genuinely exists on disk.
    assert os.path.exists(os.readlink(current))


def test_rollback_that_also_fails_health_is_reported_unhealthy(tmp_path):
    """Health never recovers even after rollback (sentinel never fresh) ->
    result.healthy is False so the caller/operator can tell rollback itself
    didn't fully restore service, not just log and move on silently."""
    _mkcurrent(tmp_path, "old-ref")
    runner = _healthy_runner()

    result = run_once(
        fetch_target_ref=lambda: "broken-ref",
        health_retries=1,
        clock=lambda: 1_700_000_100.0,
        **_base_kwargs(tmp_path, runner=runner),
    )

    assert result.action == "rollback"
    assert result.rolled_back is True
    assert result.healthy is False


# ── target fetch propagates (caller decides retry cadence via the timer) ────

def test_target_fetch_error_propagates(tmp_path):
    def _boom():
        raise RuntimeError("network down")

    with pytest.raises(RuntimeError, match="network down"):
        run_once(fetch_target_ref=_boom, **_base_kwargs(tmp_path))
