"""Frame-diffing motion detection — no ONVIF motion events confirmed available
across RVB's Intelbras hardware (task-092 investigation), so the collector
polls RecorderClient.capture_frame() and decides "did anything change" itself.

Downscaled-grayscale mean absolute difference: a classic, dependency-light
motion heuristic. Deliberately Pillow-only (no numpy/opencv) — opencv-python
wheels on ARM/Jetson are a known landmine (the box already has JetPack's own
OpenCV build; a second pip install risks shadowing or conflicting with it,
see docs/edge/REGRAS_PLATAFORMA_JETSON.md's landmine notes), and numpy alone
would still need something to decode JPEG bytes in the first place.

Pure functions/class, no I/O — testable without a real camera or ffmpeg.

PENDÊNCIA: DEFAULT_THRESHOLD is a reasonable starting point for this kind of
diff (not zero, not saturated), never calibrated against real RVB footage —
no camera hardware in this environment. Tune via COLLECTOR_MOTION_THRESHOLD
once the pilot is running against the real cameras.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageStat

_THUMBNAIL_SIZE = (64, 48)


@dataclass(frozen=True)
class MotionResult:
    changed: bool
    score: float  # mean per-pixel difference, 0-255


def frame_diff_score(frame_a: bytes, frame_b: bytes) -> float:
    """Mean per-pixel difference (0-255) between two JPEG frames, downscaled
    grayscale. The core primitive both MotionDetector (idle-cadence "did
    anything change") and the collector's intra-burst dedup (skip
    near-identical frames within one motion burst) build on."""
    a = _to_thumbnail(frame_a)
    b = _to_thumbnail(frame_b)
    diff = ImageChops.difference(a, b)
    return ImageStat.Stat(diff).mean[0]


class MotionDetector:
    """Stateful per-camera motion detector — call detect() with each new
    frame's bytes, in capture order. The FIRST call never reports motion
    (nothing to diff against yet — it just seeds `_previous`); this is
    correct frame-differencing behavior, not a bug.
    """

    DEFAULT_THRESHOLD = 8.0

    def __init__(self, threshold: float = DEFAULT_THRESHOLD) -> None:
        self._threshold = threshold
        self._previous: bytes | None = None

    def detect(self, frame_bytes: bytes) -> MotionResult:
        if self._previous is None:
            self._previous = frame_bytes
            return MotionResult(changed=False, score=0.0)
        score = frame_diff_score(frame_bytes, self._previous)
        self._previous = frame_bytes
        return MotionResult(changed=score >= self._threshold, score=score)


def _to_thumbnail(frame_bytes: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(frame_bytes)).convert("L")
    image.thumbnail(_THUMBNAIL_SIZE)
    return image
