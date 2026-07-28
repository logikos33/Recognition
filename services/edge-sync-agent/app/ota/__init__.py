"""Bare-metal OTA (ADR-0057 item 10): git ref + venv-per-release + symlink swap.

No Docker — see docs/edge/REGRAS_PLATAFORMA_JETSON.md §3.4. Runs as its own
systemd --user timer/oneshot unit, separate from the edge-sync-agent daemon it
updates (see `updater.py`'s module docstring for why that separation is
required, not incidental).
"""

from .client import TargetFetchError, fetch_target_ref
from .release_manager import ReleaseError
from .updater import UpdateResult, run_once

__all__ = [
    "ReleaseError",
    "TargetFetchError",
    "UpdateResult",
    "fetch_target_ref",
    "run_once",
]
