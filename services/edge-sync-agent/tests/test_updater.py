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


def _mkcurrent(tmp_path, ref):
    """Points `current` at an existing release for `ref` (as if already deployed)."""
    service_dir = tmp_path / "releases" / ref / SERVICE_SUBDIR
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
