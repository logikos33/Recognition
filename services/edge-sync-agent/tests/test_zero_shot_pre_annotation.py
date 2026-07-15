"""Tests for the onboarding zero-shot pre-annotation orchestration (task-098):
flag gating (OFF by default — normal path intact), format conversion to the
exact pre_annotations dict shape, and batch error handling."""

import json

import pytest

from app.zero_shot_detector import (
    StubZeroShotDetector,
    ZeroShotDetection,
    ZeroShotDetectorError,
)
from app.zero_shot_pre_annotation import (
    FeatureFlagDisabledError,
    FrameInput,
    _load_frames_from_dir,
    _parse_args,
    is_zero_shot_enabled,
    run_onboarding_pre_annotation,
    to_pre_annotation_dict,
    to_pre_annotation_dicts,
)

_HELMET = ZeroShotDetection(
    text_label="capacete", confidence=0.87, cx=0.5, cy=0.4, w=0.2, h=0.3
)
_VEST = ZeroShotDetection(
    text_label="colete", confidence=0.65, cx=0.3, cy=0.6, w=0.15, h=0.25
)


class TestIsZeroShotEnabled:
    def test_disabled_when_no_flags(self):
        assert is_zero_shot_enabled({}) is False

    def test_disabled_when_enabled_flag_false(self):
        flags = {"pre_annotation_enabled": False, "pre_annotation_backend": "zero_shot"}
        assert is_zero_shot_enabled(flags) is False

    def test_disabled_when_backend_is_dino_sam(self):
        flags = {"pre_annotation_enabled": True, "pre_annotation_backend": "dino_sam"}
        assert is_zero_shot_enabled(flags) is False

    def test_disabled_when_backend_missing(self):
        flags = {"pre_annotation_enabled": True}
        assert is_zero_shot_enabled(flags) is False

    def test_enabled_when_both_set(self):
        flags = {"pre_annotation_enabled": True, "pre_annotation_backend": "zero_shot"}
        assert is_zero_shot_enabled(flags) is True

    def test_no_env_fallback_unlike_cloud_factory(self, monkeypatch):
        """Unlike services/api's factory.py (which falls back to
        PRE_ANNOTATION_ENABLED env var), the edge module has no implicit
        default — only explicit feature_flags input matters."""
        monkeypatch.setenv("PRE_ANNOTATION_ENABLED", "true")
        assert is_zero_shot_enabled({}) is False


class TestToPreAnnotationDict:
    def test_shape_matches_annotation_service_contract(self):
        result = to_pre_annotation_dict(_HELMET)

        assert result == {
            "bbox": {"cx": 0.5, "cy": 0.4, "w": 0.2, "h": 0.3},
            "class": "capacete",
            "confidence": 0.87,
        }

    def test_multiple_detections_preserve_order(self):
        result = to_pre_annotation_dicts([_HELMET, _VEST])
        assert [r["class"] for r in result] == ["capacete", "colete"]


_ENABLED_FLAGS = {"pre_annotation_enabled": True, "pre_annotation_backend": "zero_shot"}


class TestRunOnboardingPreAnnotation:
    def test_raises_when_flag_disabled(self):
        detector = StubZeroShotDetector(detections=[_HELMET])
        frames = [FrameInput(frame_id="frame-1", image_bytes=b"jpeg-bytes")]

        with pytest.raises(FeatureFlagDisabledError):
            run_onboarding_pre_annotation(
                detector=detector,
                frames=frames,
                text_labels=["capacete"],
                feature_flags={},
            )

    def test_normal_onboarding_path_intact_when_disabled(self):
        """No frame is ever touched when the flag is off — the detector
        must not even be called (sem fallback silencioso)."""
        class _ExplodingDetector:
            def detect(self, image_bytes, text_labels):
                raise AssertionError("detector should never be called when flag is off")

        with pytest.raises(FeatureFlagDisabledError):
            run_onboarding_pre_annotation(
                detector=_ExplodingDetector(),
                frames=[FrameInput(frame_id="frame-1", image_bytes=b"x")],
                text_labels=["capacete"],
                feature_flags={"pre_annotation_enabled": False},
            )

    def test_raises_on_empty_text_labels(self):
        detector = StubZeroShotDetector(detections=[_HELMET])
        with pytest.raises(ValueError, match="text_labels"):
            run_onboarding_pre_annotation(
                detector=detector,
                frames=[FrameInput(frame_id="frame-1", image_bytes=b"x")],
                text_labels=[],
                feature_flags=_ENABLED_FLAGS,
            )

    def test_produces_pre_annotations_for_each_frame(self):
        detector = StubZeroShotDetector(detections=[_HELMET, _VEST])
        frames = [
            FrameInput(frame_id="frame-1", image_bytes=b"jpeg-1"),
            FrameInput(frame_id="frame-2", image_bytes=b"jpeg-2"),
        ]

        report = run_onboarding_pre_annotation(
            detector=detector,
            frames=frames,
            text_labels=["capacete", "colete"],
            feature_flags=_ENABLED_FLAGS,
        )

        assert [r.frame_id for r in report.results] == ["frame-1", "frame-2"]
        assert report.total_annotations == 4
        assert report.results[0].pre_annotations[0]["class"] == "capacete"
        assert report.failed_frame_ids == []

    def test_frame_error_aborts_batch_by_default(self):
        class _FailingDetector:
            def detect(self, image_bytes, text_labels):
                raise ZeroShotDetectorError("boom")

        with pytest.raises(ZeroShotDetectorError):
            run_onboarding_pre_annotation(
                detector=_FailingDetector(),
                frames=[FrameInput(frame_id="frame-1", image_bytes=b"x")],
                text_labels=["capacete"],
                feature_flags=_ENABLED_FLAGS,
            )

    def test_continue_on_frame_error_skips_and_records(self):
        class _FlakyDetector:
            def __init__(self):
                self.calls = 0

            def detect(self, image_bytes, text_labels):
                self.calls += 1
                if self.calls == 1:
                    raise ZeroShotDetectorError("corrupt image")
                return [_HELMET]

        frames = [
            FrameInput(frame_id="bad-frame", image_bytes=b"corrupt"),
            FrameInput(frame_id="good-frame", image_bytes=b"jpeg"),
        ]

        report = run_onboarding_pre_annotation(
            detector=_FlakyDetector(),
            frames=frames,
            text_labels=["capacete"],
            feature_flags=_ENABLED_FLAGS,
            continue_on_frame_error=True,
        )

        assert report.failed_frame_ids == ["bad-frame"]
        assert [r.frame_id for r in report.results] == ["good-frame"]


class TestLoadFramesFromDir:
    def test_loads_jpg_and_png_using_stem_as_frame_id(self, tmp_path):
        (tmp_path / "frame-abc.jpg").write_bytes(b"jpeg-bytes")
        (tmp_path / "frame-def.png").write_bytes(b"png-bytes")
        (tmp_path / "notes.txt").write_text("ignore me")

        frames = _load_frames_from_dir(tmp_path)

        assert {f.frame_id for f in frames} == {"frame-abc", "frame-def"}

    def test_empty_dir_returns_empty_list(self, tmp_path):
        assert _load_frames_from_dir(tmp_path) == []


class TestParseArgs:
    def test_parses_required_arguments(self, tmp_path):
        args = _parse_args([
            "--frames-dir", str(tmp_path),
            "--text-labels", "capacete,colete",
            "--feature-flags", json.dumps(_ENABLED_FLAGS),
            "--engine-path", "/opt/nanoowl/engine.trt",
            "--output", str(tmp_path / "out.json"),
        ])

        assert args.text_labels == "capacete,colete"
        assert args.continue_on_frame_error is False

    def test_continue_on_frame_error_flag(self, tmp_path):
        args = _parse_args([
            "--frames-dir", str(tmp_path),
            "--text-labels", "capacete",
            "--feature-flags", "{}",
            "--engine-path", "/opt/nanoowl/engine.trt",
            "--output", str(tmp_path / "out.json"),
            "--continue-on-frame-error",
        ])

        assert args.continue_on_frame_error is True
