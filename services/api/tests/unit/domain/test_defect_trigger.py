"""
Tests: DefectTriggerOperation — validate_config + evaluate logic.

Pure-logic: no stubs, no network calls.
"""
from app.domain.services.operations.canonical.defect_trigger import DefectTriggerOperation

# Rectangle covering centre of frame [0.2–0.8, 0.2–0.8]
_ROI = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
_META = {"width": 640, "height": 360}


def _op(config: dict) -> DefectTriggerOperation:
    return DefectTriggerOperation(config)


def _base_config(**overrides) -> dict:
    cfg = {
        "roi_points": _ROI,
        "trigger_class": "product_box",
        "defect_classes": ["scratch", "dent"],
        "confidence_threshold": 0.5,
    }
    cfg.update(overrides)
    return cfg


def _det(cls: str, conf: float = 0.9, cx: float = 0.5, cy: float = 0.5) -> dict:
    """Build a detection whose centre (cx, cy) is in normalised coords.

    DefectTriggerOperation computes: cx = (bbox[0] + bbox[2]/2) / frame_w
    With w=h=0 this simplifies to bbox[0]/frame_w = cx_norm.
    """
    px_cx = cx * _META["width"]
    px_cy = cy * _META["height"]
    return {"class": cls, "confidence": conf, "bbox": [px_cx, px_cy, 0, 0]}


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------

class TestValidateConfig:

    def test_valid_config_returns_no_errors(self):
        cfg = _base_config()
        assert _op(cfg).validate_config(cfg) == []

    def test_roi_too_few_points_is_error(self):
        cfg = _base_config(roi_points=[[0, 0], [1, 0]])  # only 2 points
        errors = _op(_base_config()).validate_config(cfg)
        assert any("roi_points" in e for e in errors)

    def test_empty_roi_is_error(self):
        cfg = _base_config(roi_points=[])
        errors = _op(_base_config()).validate_config(cfg)
        assert any("roi_points" in e for e in errors)

    def test_missing_trigger_class_is_error(self):
        cfg = _base_config(trigger_class="")
        errors = _op(cfg).validate_config(cfg)
        assert any("trigger_class" in e for e in errors)

    def test_missing_defect_classes_is_error(self):
        cfg = _base_config(defect_classes=[])
        errors = _op(cfg).validate_config(cfg)
        assert any("defect_classes" in e for e in errors)

    def test_all_three_missing_returns_three_errors(self):
        cfg = {"roi_points": [], "trigger_class": "", "defect_classes": []}
        errors = _op(_base_config()).validate_config(cfg)
        assert len(errors) == 3

    def test_three_point_roi_is_valid(self):
        cfg = _base_config(roi_points=[[0, 0], [1, 0], [0.5, 1]])
        assert _op(cfg).validate_config(cfg) == []


# ---------------------------------------------------------------------------
# evaluate — basic gate conditions
# ---------------------------------------------------------------------------

class TestEvaluateBasic:

    def test_no_detections_returns_no_condition(self):
        result = _op(_base_config()).evaluate([], _META, {})
        assert result["condition_satisfied"] is False
        assert result["result"]["trigger_in_roi"] is False
        assert result["result"]["defect_count"] == 0
        assert result["metric_value"] == 0

    def test_trigger_only_not_satisfied(self):
        result = _op(_base_config()).evaluate([_det("product_box")], _META, {})
        assert result["condition_satisfied"] is False
        assert result["result"]["trigger_in_roi"] is True
        assert result["result"]["defect_count"] == 0

    def test_defect_only_not_satisfied(self):
        result = _op(_base_config()).evaluate([_det("scratch")], _META, {})
        assert result["condition_satisfied"] is False
        assert result["result"]["trigger_in_roi"] is False
        assert result["result"]["defect_count"] == 1

    def test_trigger_and_defect_both_in_roi_satisfied(self):
        dets = [_det("product_box"), _det("scratch")]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["condition_satisfied"] is True
        assert result["result"]["trigger_in_roi"] is True
        assert result["result"]["defect_count"] == 1
        assert result["metric_value"] == 1

    def test_multiple_defects_metric_value_is_count(self):
        dets = [_det("product_box"), _det("scratch"), _det("dent")]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["metric_value"] == 2
        assert result["result"]["defect_count"] == 2

    def test_state_is_passed_through_unchanged(self):
        state = {"frame_count": 42}
        result = _op(_base_config()).evaluate([], _META, state)
        assert result["state_next"] == state


# ---------------------------------------------------------------------------
# evaluate — confidence threshold
# ---------------------------------------------------------------------------

class TestEvaluateConfidence:

    def test_low_confidence_trigger_not_activated(self):
        dets = [_det("product_box", conf=0.3), _det("scratch", conf=0.9)]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["result"]["trigger_in_roi"] is False
        assert result["condition_satisfied"] is False

    def test_low_confidence_defect_ignored(self):
        dets = [_det("product_box", conf=0.9), _det("scratch", conf=0.3)]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["result"]["defect_count"] == 0
        assert result["condition_satisfied"] is False

    def test_exact_threshold_passes(self):
        # confidence == threshold should pass (>= check)
        dets = [_det("product_box", conf=0.5), _det("scratch", conf=0.5)]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["condition_satisfied"] is True

    def test_custom_high_threshold_filters_marginal(self):
        cfg = _base_config(confidence_threshold=0.9)
        dets = [_det("product_box", conf=0.75), _det("scratch", conf=0.75)]
        result = _op(cfg).evaluate(dets, _META, {})
        assert result["condition_satisfied"] is False

    def test_custom_low_threshold_passes_lower_confidence(self):
        cfg = _base_config(confidence_threshold=0.3)
        dets = [_det("product_box", conf=0.35), _det("scratch", conf=0.35)]
        result = _op(cfg).evaluate(dets, _META, {})
        assert result["condition_satisfied"] is True


# ---------------------------------------------------------------------------
# evaluate — ROI boundary
# ---------------------------------------------------------------------------

class TestEvaluateROI:

    def test_detection_outside_roi_ignored(self):
        # (0.05, 0.5) is left of [0.2, 0.8] x-bounds
        dets = [_det("product_box", cx=0.05), _det("scratch", cx=0.05)]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["result"]["trigger_in_roi"] is False
        assert result["result"]["defect_count"] == 0

    def test_detection_inside_roi_counted(self):
        dets = [_det("product_box", cx=0.5, cy=0.5), _det("dent", cx=0.5, cy=0.5)]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["condition_satisfied"] is True

    def test_defect_inside_but_trigger_outside_not_satisfied(self):
        dets = [
            _det("product_box", cx=0.05, cy=0.5),  # outside ROI
            _det("scratch", cx=0.5, cy=0.5),         # inside ROI
        ]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["result"]["trigger_in_roi"] is False
        assert result["result"]["defect_count"] == 1
        assert result["condition_satisfied"] is False

    def test_metric_value_zero_when_trigger_absent(self):
        # Defect present but no trigger → metric_value must be 0
        dets = [_det("scratch")]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["metric_value"] == 0


# ---------------------------------------------------------------------------
# evaluate — case sensitivity
# ---------------------------------------------------------------------------

class TestEvaluateCaseInsensitive:

    def test_trigger_class_uppercase_matched(self):
        dets = [_det("PRODUCT_BOX"), _det("scratch")]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["result"]["trigger_in_roi"] is True

    def test_defect_class_uppercase_matched(self):
        dets = [_det("product_box"), _det("SCRATCH")]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["condition_satisfied"] is True

    def test_mixed_case_both_matched(self):
        dets = [_det("Product_Box"), _det("Dent")]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["condition_satisfied"] is True


# ---------------------------------------------------------------------------
# evaluate — multiple defect classes
# ---------------------------------------------------------------------------

class TestEvaluateMultipleDefectClasses:

    def test_second_defect_class_detected(self):
        dets = [_det("product_box"), _det("dent")]
        result = _op(_base_config()).evaluate(dets, _META, {})
        defect_classes = {d["class"] for d in result["result"]["defects"]}
        assert "dent" in defect_classes

    def test_unregistered_class_not_counted_as_defect(self):
        dets = [_det("product_box"), _det("unknown_defect")]
        result = _op(_base_config()).evaluate(dets, _META, {})
        assert result["result"]["defect_count"] == 0

    def test_result_defects_list_has_correct_fields(self):
        dets = [_det("product_box"), _det("scratch", cx=0.4, cy=0.4)]
        result = _op(_base_config()).evaluate(dets, _META, {})
        defect = result["result"]["defects"][0]
        assert "class" in defect
        assert "cx" in defect
        assert "cy" in defect
        assert "confidence" in defect
