"""Tests for MotionDetector/frame_diff_score: pure Pillow diffing, no I/O."""

import io

from PIL import Image

from app.collector.motion_detector import MotionDetector, MotionResult, frame_diff_score


def _solid_jpeg(color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color=color).save(buf, format="JPEG")
    return buf.getvalue()


_BLACK = _solid_jpeg((0, 0, 0))
_WHITE = _solid_jpeg((255, 255, 255))
_BLACK_AGAIN = _solid_jpeg((0, 0, 0))


def test_frame_diff_score_is_near_zero_for_identical_content():
    assert frame_diff_score(_BLACK, _BLACK_AGAIN) < 1.0


def test_frame_diff_score_is_high_for_very_different_content():
    assert frame_diff_score(_BLACK, _WHITE) > 200.0


def test_first_detect_call_never_reports_motion():
    detector = MotionDetector()
    result = detector.detect(_WHITE)
    assert result == MotionResult(changed=False, score=0.0)


def test_detect_reports_motion_when_score_crosses_threshold():
    detector = MotionDetector(threshold=8.0)
    detector.detect(_BLACK)  # seed
    result = detector.detect(_WHITE)
    assert result.changed is True
    assert result.score > 8.0


def test_detect_reports_no_motion_when_frame_is_unchanged():
    detector = MotionDetector(threshold=8.0)
    detector.detect(_BLACK)  # seed
    result = detector.detect(_BLACK_AGAIN)
    assert result.changed is False


def test_detect_updates_previous_frame_each_call():
    detector = MotionDetector(threshold=8.0)
    detector.detect(_BLACK)
    detector.detect(_WHITE)
    # third call compares against WHITE (the 2nd call), not BLACK again —
    # unchanged now since consecutive frames are both WHITE.
    result = detector.detect(_WHITE)
    assert result.changed is False


def test_custom_threshold_is_respected():
    # 1000.0 is unreachable (max possible score is 255) — nothing ever triggers.
    detector = MotionDetector(threshold=1000.0)
    detector.detect(_BLACK)
    result = detector.detect(_WHITE)
    assert result.changed is False
