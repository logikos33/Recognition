"""Tests for the ZeroShotDetector abstraction: interface, fail-loud default,
deterministic stub, and the OwlVitZeroShotDetector import-guard (task-098)."""

import pytest

from app.zero_shot_detector import (
    NotConfiguredZeroShotDetector,
    OwlVitZeroShotDetector,
    StubZeroShotDetector,
    ZeroShotDetection,
    ZeroShotDetector,
    ZeroShotDetectorError,
)


def test_not_configured_detector_satisfies_protocol():
    assert isinstance(NotConfiguredZeroShotDetector(), ZeroShotDetector)


def test_stub_detector_satisfies_protocol():
    assert isinstance(StubZeroShotDetector(), ZeroShotDetector)


def test_not_configured_detect_raises():
    detector = NotConfiguredZeroShotDetector()
    with pytest.raises(ZeroShotDetectorError):
        detector.detect(b"fake-jpeg-bytes", ["capacete"])


class TestZeroShotDetection:
    def test_valid_detection_constructs(self):
        d = ZeroShotDetection(
            text_label="capacete", confidence=0.9, cx=0.5, cy=0.5, w=0.2, h=0.3
        )
        assert d.text_label == "capacete"

    @pytest.mark.parametrize("confidence", [-0.1, 1.1])
    def test_confidence_out_of_range_raises(self, confidence):
        with pytest.raises(ValueError):
            ZeroShotDetection(
                text_label="capacete", confidence=confidence, cx=0.5, cy=0.5, w=0.2, h=0.3
            )

    @pytest.mark.parametrize("field_name", ["cx", "cy", "w", "h"])
    def test_bbox_field_out_of_range_raises(self, field_name):
        kwargs = {"cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.3}
        kwargs[field_name] = 1.5
        with pytest.raises(ValueError):
            ZeroShotDetection(text_label="capacete", confidence=0.9, **kwargs)


class TestStubZeroShotDetector:
    def test_detect_filters_by_requested_labels(self):
        detections = [
            ZeroShotDetection(
                text_label="capacete", confidence=0.9, cx=0.5, cy=0.5, w=0.2, h=0.3
            ),
            ZeroShotDetection(
                text_label="colete", confidence=0.8, cx=0.3, cy=0.3, w=0.1, h=0.1
            ),
        ]
        detector = StubZeroShotDetector(detections=detections)

        result = detector.detect(b"fake-jpeg-bytes", ["capacete"])

        assert [d.text_label for d in result] == ["capacete"]

    def test_detect_is_case_and_whitespace_insensitive(self):
        detections = [
            ZeroShotDetection(
                text_label="Capacete", confidence=0.9, cx=0.5, cy=0.5, w=0.2, h=0.3
            ),
        ]
        detector = StubZeroShotDetector(detections=detections)

        result = detector.detect(b"fake-jpeg-bytes", ["  capacete  "])

        assert len(result) == 1

    def test_detect_raises_on_empty_labels(self):
        detector = StubZeroShotDetector()
        with pytest.raises(ZeroShotDetectorError):
            detector.detect(b"fake-jpeg-bytes", [])

    def test_detect_raises_on_empty_image(self):
        detector = StubZeroShotDetector()
        with pytest.raises(ZeroShotDetectorError):
            detector.detect(b"", ["capacete"])

    def test_detect_returns_empty_list_when_no_label_matches(self):
        detector = StubZeroShotDetector(
            detections=[
                ZeroShotDetection(
                    text_label="capacete", confidence=0.9, cx=0.5, cy=0.5, w=0.2, h=0.3
                )
            ]
        )

        result = detector.detect(b"fake-jpeg-bytes", ["luva"])

        assert result == []


class TestOwlVitZeroShotDetector:
    def test_missing_nanoowl_dependency_raises_clear_error(self):
        """No GPU/Jetson/TensorRT/nanoowl available in this environment
        (task-098 — same limitation as every other edge module in this
        queue). Instantiation must fail loud with a clear pointer, not a
        raw ModuleNotFoundError."""
        with pytest.raises(ZeroShotDetectorError, match="nanoowl"):
            OwlVitZeroShotDetector(engine_path="/nonexistent/engine.trt")
