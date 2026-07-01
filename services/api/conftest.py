"""Root conftest — adds shared/python to sys.path so recognition_shared is importable."""
import sys
from pathlib import Path

_shared = Path(__file__).resolve().parents[2] / "shared" / "python"
if _shared.exists() and str(_shared) not in sys.path:
    sys.path.insert(0, str(_shared))
