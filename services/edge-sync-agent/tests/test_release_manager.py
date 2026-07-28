"""Tests for release_manager: git worktree/venv build, atomic symlink swap,
pruning. subprocess is always mocked — no real git/venv/network."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.ota.release_manager import (
    SERVICE_SUBDIR,
    ReleaseError,
    build_release,
    current_ref,
    fetch,
    prune_releases,
    service_dir_for,
    smoke_check,
    swap_current,
)


def _ok(stdout=""):
    r = MagicMock()
    r.returncode = 0
    r.stdout = stdout
    r.stderr = ""
    return r


def _fail(stderr="boom"):
    r = MagicMock()
    r.returncode = 1
    r.stdout = ""
    r.stderr = stderr
    return r


# ── fetch ────────────────────────────────────────────────────────────────────

def test_fetch_runs_git_fetch_all_tags():
    runner = MagicMock(return_value=_ok())
    fetch("/src/repo", runner=runner)
    args, kwargs = runner.call_args
    assert args[0] == ["git", "-C", "/src/repo", "fetch", "--all", "--tags"]


def test_fetch_raises_on_failure():
    runner = MagicMock(return_value=_fail("network down"))
    with pytest.raises(ReleaseError, match="network down"):
        fetch("/src/repo", runner=runner)


# ── current_ref ──────────────────────────────────────────────────────────────

def test_current_ref_none_when_symlink_missing(tmp_path):
    assert current_ref(str(tmp_path / "current")) is None


def test_current_ref_resolves_release_name(tmp_path):
    service_dir = tmp_path / "releases" / "abc123" / SERVICE_SUBDIR
    service_dir.mkdir(parents=True)
    current = tmp_path / "current"
    current.symlink_to(service_dir)

    assert current_ref(str(current)) == "abc123"


# ── build_release ────────────────────────────────────────────────────────────

def test_build_release_first_time_does_worktree_venv_and_pip(tmp_path):
    runner = MagicMock(return_value=_ok())
    source_repo = str(tmp_path / "src")
    releases_root = str(tmp_path / "releases")

    result = build_release(source_repo, releases_root, "abc123", runner=runner)

    assert result == service_dir_for(releases_root, "abc123")
    calls = [c.args[0] for c in runner.call_args_list]
    assert calls[0][:4] == ["git", "-C", source_repo, "worktree"]
    assert calls[1][:2] == ["python3", "-m"]
    assert calls[2][-2:] == ["-r", "requirements.txt"]


def test_build_release_reuses_existing_worktree_and_venv(tmp_path):
    releases_root = str(tmp_path / "releases")
    service_dir = Path(service_dir_for(releases_root, "abc123"))
    (service_dir / ".venv" / "bin").mkdir(parents=True)

    runner = MagicMock(return_value=_ok())
    build_release(str(tmp_path / "src"), releases_root, "abc123", runner=runner)

    # Only pip install — no worktree add, no venv creation (both already exist).
    assert runner.call_count == 1
    assert "install" in runner.call_args.args[0]


def test_build_release_raises_on_worktree_failure(tmp_path):
    runner = MagicMock(return_value=_fail("ref not found"))
    with pytest.raises(ReleaseError, match="ref not found"):
        build_release(str(tmp_path / "src"), str(tmp_path / "releases"), "bad-ref", runner=runner)


def test_build_release_raises_on_pip_failure(tmp_path):
    runner = MagicMock(side_effect=[_ok(), _ok(), _fail("no matching distribution")])
    with pytest.raises(ReleaseError, match="no matching distribution"):
        build_release(str(tmp_path / "src"), str(tmp_path / "releases"), "abc123", runner=runner)


# ── smoke_check ──────────────────────────────────────────────────────────────

def test_smoke_check_imports_app_main(tmp_path):
    runner = MagicMock(return_value=_ok())
    service_dir = str(tmp_path / "svc")

    smoke_check(service_dir, runner=runner)

    args, kwargs = runner.call_args
    assert args[0][-1] == "import app.main"
    assert kwargs["cwd"] == service_dir


def test_smoke_check_raises_on_import_error(tmp_path):
    runner = MagicMock(return_value=_fail("ModuleNotFoundError: No module named 'jwt'"))
    with pytest.raises(ReleaseError, match="ModuleNotFoundError"):
        smoke_check(str(tmp_path / "svc"), runner=runner)


# ── swap_current ─────────────────────────────────────────────────────────────

def test_swap_current_points_to_new_target(tmp_path):
    current = tmp_path / "current"
    target_a = tmp_path / "releases" / "a"
    target_b = tmp_path / "releases" / "b"
    target_a.mkdir(parents=True)
    target_b.mkdir(parents=True)

    swap_current(str(current), str(target_a))
    assert os.readlink(current) == str(target_a)

    swap_current(str(current), str(target_b))
    assert os.readlink(current) == str(target_b)


def test_swap_current_leaves_no_leftover_tmp_symlink(tmp_path):
    current = tmp_path / "current"
    target = tmp_path / "releases" / "a"
    target.mkdir(parents=True)

    swap_current(str(current), str(target))

    assert not Path(f"{current}.tmp").exists()


def test_swap_current_creates_parent_dir_if_missing(tmp_path):
    current = tmp_path / "nested" / "dir" / "current"
    target = tmp_path / "releases" / "a"
    target.mkdir(parents=True)

    swap_current(str(current), str(target))

    assert os.readlink(current) == str(target)


# ── prune_releases ────────────────────────────────────────────────────────────

def _make_release(root: Path, name: str, age_days: int) -> Path:
    d = root / name
    d.mkdir(parents=True)
    ts = 1_700_000_000 - age_days * 86400
    os.utime(d, (ts, ts))
    return d


def test_prune_keeps_most_recent_up_to_keep_last(tmp_path):
    root = tmp_path / "releases"
    _make_release(root, "oldest", age_days=10)
    _make_release(root, "older", age_days=5)
    _make_release(root, "newest", age_days=0)

    removed = prune_releases(str(root), keep_refs=set(), keep_last=2)

    assert removed == ["oldest"]
    assert {p.name for p in root.iterdir()} == {"older", "newest"}


def test_prune_never_removes_protected_refs_even_if_old(tmp_path):
    root = tmp_path / "releases"
    _make_release(root, "ancient-but-current", age_days=100)
    _make_release(root, "newer-unrelated", age_days=1)

    removed = prune_releases(
        str(root), keep_refs={"ancient-but-current"}, keep_last=1
    )

    assert "ancient-but-current" not in removed
    assert (root / "ancient-but-current").exists()


def test_prune_returns_empty_list_when_root_missing(tmp_path):
    assert prune_releases(str(tmp_path / "nope"), keep_refs=set()) == []


def test_prune_protected_refs_dont_count_against_keep_last_budget(tmp_path):
    """current + previous (2 protected) + keep_last=3 -> 1 extra unprotected kept."""
    root = tmp_path / "releases"
    _make_release(root, "current", age_days=0)
    _make_release(root, "previous", age_days=1)
    _make_release(root, "extra-newest", age_days=2)
    _make_release(root, "extra-oldest", age_days=3)

    removed = prune_releases(str(root), keep_refs={"current", "previous"}, keep_last=3)

    assert removed == ["extra-oldest"]
    assert {p.name for p in root.iterdir()} == {"current", "previous", "extra-newest"}
