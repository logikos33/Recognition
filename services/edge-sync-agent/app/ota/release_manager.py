"""Release lifecycle for bare-metal OTA: git worktree per ref, venv, atomic
symlink swap, pruning.

"Version" = git ref (no Docker — see docs/edge/REGRAS_PLATAFORMA_JETSON.md
§3.4 and ADR-0057 item 10: sudo/Docker are unusable on the box for autonomous
execution). Each release is a `git worktree` off one source clone (shares the
object store — cheap compared to N full clones) with its own venv. `current`
is a symlink swapped atomically (temp name + os.replace, POSIX-atomic on the
same filesystem) so a reader never observes a half-updated target.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

Runner = Callable[..., Any]

SERVICE_SUBDIR = "services/edge-sync-agent"
_VENV_DIRNAME = ".venv"
_BUILD_TIMEOUT_S = 300


class ReleaseError(Exception):
    """A release build step failed — caller must not swap `current` to it."""


def _run(runner: Runner, args: list[str], cwd: str | None = None) -> Any:
    result = runner(args, cwd=cwd, capture_output=True, text=True, timeout=_BUILD_TIMEOUT_S)
    if result.returncode != 0:
        raise ReleaseError(
            f"{' '.join(args)} falhou (rc={result.returncode}): {(result.stderr or '')[:500]}"
        )
    return result


def service_dir_for(releases_root: str, ref: str) -> str:
    return str(Path(releases_root) / ref / SERVICE_SUBDIR)


def fetch(source_repo: str, *, runner: Runner = subprocess.run) -> None:
    """`git fetch` in the source clone — does not touch its own HEAD."""
    _run(runner, ["git", "-C", source_repo, "fetch", "--all", "--tags"])


def current_ref(current_symlink: str, releases_root: str) -> str | None:
    """Resolves the ref (releases/<ref> dirname) `current` points at, or None
    if there's no *genuine* release to name — `current` doesn't exist yet
    (first-ever install), or it points somewhere that isn't actually under
    `releases_root` (deploy/install.sh's bootstrap points `current` straight
    at the raw checkout so the daemon has something to run before any OTA
    cycle has ever happened — see its comment).

    Returning `None` here (never a guessed/fabricated name) matters beyond
    "what version am I on": `updater.run_once()` treats `None` as "no
    previous release to roll back to" and refuses to touch `current` on a
    failed health check instead of guessing. Before this fixed, walking up
    from a bootstrap symlink produced a name that looked like a real ref
    but named a `releases/<name>/` directory that never existed — a failed
    update's rollback then pointed `current` at that nonexistent path,
    turning a failed update into a broken daemon (confirmed on real hardware
    during gate 1.6, PR #235).
    """
    path = Path(current_symlink)
    if not path.is_symlink():
        return None
    target = Path(os.readlink(path))
    if not target.is_absolute():
        target = (path.parent / target).resolve()
    # target is releases/<ref>/services/edge-sync-agent -> walk up to <ref>.
    depth = len(Path(SERVICE_SUBDIR).parts)
    ref_dir = target
    for _ in range(depth):
        ref_dir = ref_dir.parent
    try:
        if ref_dir.parent.resolve() != Path(releases_root).resolve():
            return None
    except OSError:
        return None
    return ref_dir.name


def build_release(
    source_repo: str,
    releases_root: str,
    ref: str,
    *,
    runner: Runner = subprocess.run,
) -> str:
    """`git worktree add` + venv + pip install for `ref`. Returns the service
    dir path inside the new release — NOT yet wired into `current`. Raises
    ReleaseError on any step failure (caller must not swap to a broken
    release); reuses an already-built worktree/venv if one exists (retry
    after a transient pip failure doesn't redo the worktree add).
    """
    release_dir = str(Path(releases_root) / ref)
    if not Path(release_dir).exists():
        Path(releases_root).mkdir(parents=True, exist_ok=True)
        _run(runner, ["git", "-C", source_repo, "worktree", "add", "--detach", release_dir, ref])

    service_dir = service_dir_for(releases_root, ref)
    venv_dir = str(Path(service_dir) / _VENV_DIRNAME)
    if not Path(venv_dir).exists():
        _run(runner, ["python3", "-m", "venv", venv_dir])

    pip = str(Path(venv_dir) / "bin" / "pip")
    _run(runner, [pip, "install", "-q", "-r", "requirements.txt"], cwd=service_dir)
    return service_dir


def smoke_check(service_dir: str, *, runner: Runner = subprocess.run) -> None:
    """Import-only sanity check — catches missing deps/syntax errors before
    the release is ever wired into `current`. Raises ReleaseError on failure.
    """
    python = str(Path(service_dir) / _VENV_DIRNAME / "bin" / "python")
    _run(runner, [python, "-c", "import app.main"], cwd=service_dir)


def swap_current(current_symlink: str, new_target: str) -> None:
    """Atomically points `current` at `new_target`: write a temp symlink,
    then `os.replace` (POSIX rename — atomic on the same filesystem), so a
    concurrent reader of `current` never sees a half-swapped state."""
    tmp = f"{current_symlink}.tmp"
    if os.path.lexists(tmp):
        os.remove(tmp)
    Path(current_symlink).parent.mkdir(parents=True, exist_ok=True)
    os.symlink(new_target, tmp)
    os.replace(tmp, current_symlink)


def prune_releases(
    releases_root: str, keep_refs: set[str], *, keep_last: int = 3
) -> list[str]:
    """Removes old release dirs beyond `keep_last`, always preserving
    `keep_refs` (current + previous — needed for rollback) regardless of age.
    Returns the refs removed.

    Uses `shutil.rmtree` (not `git worktree remove`) deliberately: a release
    with a broken venv/half-built state shouldn't need a clean git state to
    be prunable. The source repo's worktree registration is left to be swept
    later by an ordinary `git worktree prune` (no strict cleanliness need on
    a bare-metal box, and doing it here would add a failure mode to pruning
    itself).
    """
    root = Path(releases_root)
    if not root.exists():
        return []
    all_dirs = [p for p in root.iterdir() if p.is_dir()]
    protected = {p.name for p in all_dirs} & keep_refs
    candidates = sorted(
        (p for p in all_dirs if p.name not in keep_refs),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    extra_budget = max(0, keep_last - len(protected))
    to_remove = candidates[extra_budget:]

    removed = []
    for p in to_remove:
        shutil.rmtree(p, ignore_errors=True)
        removed.append(p.name)
        logger.info("release_pruned ref=%s", p.name)
    return removed
