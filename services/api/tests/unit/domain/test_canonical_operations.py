"""
Tests: CountStatic, OverlapFixed, OverlapDynamic, Position operations (item-19).

Cobre os 4 tipos de operação canônica não testados em test_rvb_operation_types.py.
Todos são testes unitários puros — sem Flask, sem banco.
"""


_ROI_SQUARE = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
_FRAME_META = {"width": 640, "height": 360}

# Detection helper: bbox = [x, y, w, h] in pixels
def _det(cls, cx_norm, cy_norm, conf=0.9, track_id=None):
    w, h = _FRAME_META["width"], _FRAME_META["height"]
    cx, cy = cx_norm * w, cy_norm * h
    d = {"class": cls, "confidence": conf, "bbox": [cx - 10, cy - 10, 20, 20]}
    if track_id is not None:
        d["track_id"] = track_id
    return d


# ---------------------------------------------------------------------------
# CountStaticOperation
# ---------------------------------------------------------------------------

class TestCountStaticOperation:

    def _make(self, config):
        from app.domain.services.operations.canonical.count_static import CountStaticOperation
        return CountStaticOperation(config)

    def test_validate_config_valid(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "count"})
        assert op.validate_config(op.config) == []

    def test_validate_config_missing_target_class(self):
        op = self._make({"roi_points": _ROI_SQUARE, "metric": "count"})
        errors = op.validate_config(op.config)
        assert any("target_class" in e for e in errors)

    def test_validate_config_roi_too_few_points(self):
        op = self._make({"target_class": "person", "roi_points": [[0, 0], [1, 0]], "metric": "count"})
        errors = op.validate_config(op.config)
        assert any("roi_points" in e for e in errors)

    def test_validate_config_invalid_metric(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "invalid"})
        errors = op.validate_config(op.config)
        assert any("metric" in e for e in errors)

    def test_evaluate_counts_objects_in_roi(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "count"})
        dets = [
            _det("person", 0.5, 0.5),  # inside ROI
            _det("person", 0.5, 0.5),  # inside ROI
            _det("person", 0.05, 0.5), # outside ROI
        ]
        result = op.evaluate(dets, _FRAME_META, {})
        assert result["result"]["count"] == 2
        assert result["condition_satisfied"] is True

    def test_evaluate_boolean_above_threshold_met(self):
        op = self._make({
            "target_class": "car",
            "roi_points": _ROI_SQUARE,
            "metric": "boolean_above",
            "count_threshold": 1,
        })
        dets = [_det("car", 0.5, 0.5), _det("car", 0.6, 0.6)]
        result = op.evaluate(dets, _FRAME_META, {})
        assert result["condition_satisfied"] is True

    def test_evaluate_boolean_below_threshold(self):
        op = self._make({
            "target_class": "car",
            "roi_points": _ROI_SQUARE,
            "metric": "boolean_below",
            "count_threshold": 5,
        })
        dets = [_det("car", 0.5, 0.5)]
        result = op.evaluate(dets, _FRAME_META, {})
        assert result["condition_satisfied"] is True

    def test_evaluate_no_detections_returns_zero(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "count"})
        result = op.evaluate([], _FRAME_META, {})
        assert result["result"]["count"] == 0
        assert result["condition_satisfied"] is False

    def test_evaluate_ignores_low_confidence(self):
        op = self._make({
            "target_class": "person",
            "roi_points": _ROI_SQUARE,
            "metric": "count",
            "confidence_threshold": 0.8,
        })
        dets = [_det("person", 0.5, 0.5, conf=0.3)]
        result = op.evaluate(dets, _FRAME_META, {})
        assert result["result"]["count"] == 0

    def test_evaluate_ignores_wrong_class(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "count"})
        dets = [_det("car", 0.5, 0.5)]
        result = op.evaluate(dets, _FRAME_META, {})
        assert result["result"]["count"] == 0


# ---------------------------------------------------------------------------
# OverlapFixedOperation
# ---------------------------------------------------------------------------

class TestOverlapFixedOperation:

    def _make(self, config):
        from app.domain.services.operations.canonical.overlap_fixed import OverlapFixedOperation
        return OverlapFixedOperation(config)

    def test_validate_config_valid(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "time_seconds"})
        assert op.validate_config(op.config) == []

    def test_validate_config_missing_target_class(self):
        op = self._make({"roi_points": _ROI_SQUARE, "metric": "time_seconds"})
        errors = op.validate_config(op.config)
        assert any("target_class" in e for e in errors)

    def test_validate_config_invalid_metric(self):
        op = self._make({"target_class": "x", "roi_points": _ROI_SQUARE, "metric": "bad"})
        errors = op.validate_config(op.config)
        assert any("metric" in e for e in errors)

    def test_evaluate_entry_adds_to_state(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "time_seconds"})
        t0 = 1000.0
        dets = [_det("person", 0.5, 0.5, track_id="t1")]
        meta = {**_FRAME_META, "timestamp_epoch": t0}
        result = op.evaluate(dets, meta, {})
        assert result["state_next"]["entries"] == 1
        assert "t1" in result["state_next"]["entry_times"]

    def test_evaluate_exit_accumulates_time(self):
        op = self._make({
            "target_class": "person",
            "roi_points": _ROI_SQUARE,
            "metric": "time_seconds",
            "threshold_seconds": 5.0,
        })
        t0, t1 = 1000.0, 1007.0
        state = {"entry_times": {"t1": t0}, "total_time": 0.0, "entries": 1, "exits": 0}
        meta = {**_FRAME_META, "timestamp_epoch": t1}
        result = op.evaluate([], meta, state)  # no detections → t1 exits
        assert result["state_next"]["exits"] == 1
        assert result["state_next"]["total_time"] >= 7.0
        assert result["condition_satisfied"] is True  # 7s >= 5s threshold

    def test_evaluate_entry_exit_count_metric(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "entry_exit_count"})
        state = {"entry_times": {}, "total_time": 0.0, "entries": 3, "exits": 2}
        meta = {**_FRAME_META, "timestamp_epoch": 1000.0}
        result = op.evaluate([], meta, state)
        assert isinstance(result["metric_value"], dict)
        assert "entries" in result["metric_value"]


# ---------------------------------------------------------------------------
# OverlapDynamicOperation
# ---------------------------------------------------------------------------

class TestOverlapDynamicOperation:

    def _make(self, config):
        from app.domain.services.operations.canonical.overlap_dynamic import OverlapDynamicOperation
        return OverlapDynamicOperation(config)

    def test_validate_config_valid(self):
        op = self._make({"class_a": "person", "class_b": "machine", "metric": "iou_percent"})
        assert op.validate_config(op.config) == []

    def test_validate_config_missing_class_a(self):
        op = self._make({"class_b": "machine", "metric": "iou_percent"})
        errors = op.validate_config(op.config)
        assert any("class_a" in e for e in errors)

    def test_validate_config_invalid_metric(self):
        op = self._make({"class_a": "person", "class_b": "machine", "metric": "bad"})
        errors = op.validate_config(op.config)
        assert any("metric" in e for e in errors)

    def test_evaluate_no_overlap_returns_false(self):
        op = self._make({"class_a": "person", "class_b": "machine", "metric": "iou_percent"})
        dets = [
            _det("person", 0.1, 0.1),
            _det("machine", 0.9, 0.9),
        ]
        result = op.evaluate(dets, _FRAME_META, {})
        assert result["condition_satisfied"] is False

    def test_evaluate_overlapping_objects_returns_true(self):
        op = self._make({
            "class_a": "person",
            "class_b": "machine",
            "metric": "iou_percent",
            "iou_threshold": 0.01,
        })
        # Same position → high IoU
        dets = [
            _det("person", 0.5, 0.5),
            _det("machine", 0.5, 0.5),
        ]
        result = op.evaluate(dets, _FRAME_META, {})
        assert result["condition_satisfied"] is True

    def test_evaluate_no_detections_returns_no_overlap(self):
        op = self._make({"class_a": "person", "class_b": "machine", "metric": "iou_percent"})
        result = op.evaluate([], _FRAME_META, {})
        assert result["condition_satisfied"] is False


# ---------------------------------------------------------------------------
# PositionOperation
# ---------------------------------------------------------------------------

class TestPositionOperation:

    def _make(self, config):
        from app.domain.services.operations.canonical.position import PositionOperation
        return PositionOperation(config)

    def test_validate_config_valid(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "state"})
        assert op.validate_config(op.config) == []

    def test_validate_config_missing_target_class(self):
        op = self._make({"roi_points": _ROI_SQUARE, "metric": "state"})
        errors = op.validate_config(op.config)
        assert any("target_class" in e for e in errors)

    def test_validate_config_roi_too_few_points(self):
        op = self._make({"target_class": "x", "roi_points": [[0, 0], [1, 0]], "metric": "state"})
        errors = op.validate_config(op.config)
        assert any("roi_points" in e for e in errors)

    def test_evaluate_object_inside_roi(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "state"})
        dets = [_det("person", 0.5, 0.5)]
        result = op.evaluate(dets, _FRAME_META, {})
        assert result["condition_satisfied"] is True

    def test_evaluate_object_outside_roi(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "state"})
        dets = [_det("person", 0.02, 0.02)]  # outside [0.1,0.9] square
        result = op.evaluate(dets, _FRAME_META, {})
        assert result["condition_satisfied"] is False

    def test_evaluate_coordinates_metric(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "coordinates"})
        dets = [_det("person", 0.5, 0.5)]
        result = op.evaluate(dets, _FRAME_META, {})
        assert "objects" in result["result"] or result.get("metric_value") is not None

    def test_evaluate_no_detections(self):
        op = self._make({"target_class": "person", "roi_points": _ROI_SQUARE, "metric": "state"})
        result = op.evaluate([], _FRAME_META, {})
        assert result["condition_satisfied"] is False
