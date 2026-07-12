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


# ---------------------------------------------------------------------------
# CountingLineOperation
#
# Position-based tracking uses round(cx, 2) as obj_key. A crossing is only
# detected when the same rounded position appears on opposite sides in
# consecutive frames. Tests use cy=0.498/0.502 which both round to 0.5 but
# are on opposite sides of the horizontal midline at y=0.5.
# ---------------------------------------------------------------------------

_LINE = [[0.0, 0.5], [1.0, 0.5]]  # horizontal midline
_ABOVE = 0.498  # round(0.498, 2) == 0.5; side = cy-0.5 < 0 (above line)
_BELOW = 0.502  # round(0.502, 2) == 0.5; side = cy-0.5 > 0 (below line)


class TestCountingLineOperation:

    def _make(self, direction="both", confirm=1, debounce=0):
        from app.domain.services.operations.canonical.counting_line import CountingLineOperation
        return CountingLineOperation({
            "line_points": _LINE,
            "direction": direction,
            "target_class": "person",
            "confidence_threshold": 0.5,
            "confirm_samples": confirm,
            "direction_debounce_frames": debounce,
        })

    def _det_at(self, cx_norm, cy_norm, conf=0.9):
        w, h = _FRAME_META["width"], _FRAME_META["height"]
        cx, cy = cx_norm * w, cy_norm * h
        return {"class": "person", "confidence": conf, "bbox": [cx - 10, cy - 10, 20, 20]}

    # --- validate_config ---

    def test_validate_valid_config(self):
        op = self._make()
        assert op.validate_config(op.config) == []

    def test_validate_wrong_line_length(self):
        from app.domain.services.operations.canonical.counting_line import CountingLineOperation
        op = CountingLineOperation({"line_points": [[0, 0]], "direction": "both", "target_class": "p"})
        errs = op.validate_config(op.config)
        assert any("line_points" in e for e in errs)

    def test_validate_invalid_direction(self):
        from app.domain.services.operations.canonical.counting_line import CountingLineOperation
        op = CountingLineOperation({"line_points": [[0, 0], [1, 1]], "direction": "sideways", "target_class": "p"})
        errs = op.validate_config(op.config)
        assert any("direction" in e for e in errs)

    def test_validate_empty_target_class(self):
        from app.domain.services.operations.canonical.counting_line import CountingLineOperation
        op = CountingLineOperation({"line_points": [[0, 0], [1, 1]], "direction": "in", "target_class": ""})
        errs = op.validate_config(op.config)
        assert any("target_class" in e for e in errs)

    def test_validate_invalid_confirm_samples(self):
        from app.domain.services.operations.canonical.counting_line import CountingLineOperation
        op = CountingLineOperation({
            "line_points": [[0, 0], [1, 1]], "direction": "in", "target_class": "p", "confirm_samples": 0,
        })
        errs = op.validate_config(op.config)
        assert any("confirm_samples" in e for e in errs)

    def test_validate_negative_debounce(self):
        from app.domain.services.operations.canonical.counting_line import CountingLineOperation
        op = CountingLineOperation({
            "line_points": [[0, 0], [1, 1]], "direction": "in", "target_class": "p",
            "direction_debounce_frames": -1,
        })
        errs = op.validate_config(op.config)
        assert any("debounce" in e for e in errs)

    # --- _side_of_line ---

    def test_side_of_line_above_is_negative(self):
        from app.domain.services.operations.canonical.counting_line import _side_of_line
        assert _side_of_line(0.5, 0.1, _LINE[0], _LINE[1]) < 0

    def test_side_of_line_below_is_positive(self):
        from app.domain.services.operations.canonical.counting_line import _side_of_line
        assert _side_of_line(0.5, 0.9, _LINE[0], _LINE[1]) > 0

    def test_side_of_line_on_line_is_zero(self):
        from app.domain.services.operations.canonical.counting_line import _side_of_line
        assert _side_of_line(0.5, 0.5, _LINE[0], _LINE[1]) == 0.0

    # --- _crossing_debounced ---

    def test_crossing_debounced_no_state_false(self):
        from app.domain.services.operations.canonical.counting_line import _crossing_debounced
        assert _crossing_debounced({}, "obj", "in", 10, 5) is False

    def test_crossing_debounced_zero_frames_false(self):
        from app.domain.services.operations.canonical.counting_line import _crossing_debounced
        dbc = {"obj": {"last_direction": "out", "frame": 8}}
        assert _crossing_debounced(dbc, "obj", "in", 10, 0) is False

    def test_crossing_debounced_opposite_within_window_true(self):
        from app.domain.services.operations.canonical.counting_line import _crossing_debounced
        dbc = {"obj": {"last_direction": "out", "frame": 8}}
        assert _crossing_debounced(dbc, "obj", "in", 10, 5) is True

    def test_crossing_debounced_same_direction_false(self):
        from app.domain.services.operations.canonical.counting_line import _crossing_debounced
        dbc = {"obj": {"last_direction": "in", "frame": 8}}
        assert _crossing_debounced(dbc, "obj", "in", 10, 5) is False

    # --- evaluate (crossing uses cy values that round to same key but on opposite sides) ---

    def test_first_frame_no_crossing(self):
        op = self._make()
        out = op.evaluate([self._det_at(0.5, _ABOVE)], _FRAME_META, {})
        assert out["result"]["count_in"] == 0 and out["result"]["count_out"] == 0

    def test_above_to_below_counts_in(self):
        """cy=0.498→0.502: both keys round to 0.5; side goes neg→pos → count_in."""
        op = self._make(confirm=1)
        s = op.evaluate([self._det_at(0.5, _ABOVE)], _FRAME_META, {})["state_next"]
        out = op.evaluate([self._det_at(0.5, _BELOW)], _FRAME_META, s)
        assert out["result"]["count_in"] == 1

    def test_below_to_above_counts_out(self):
        op = self._make(confirm=1)
        s = op.evaluate([self._det_at(0.5, _BELOW)], _FRAME_META, {})["state_next"]
        out = op.evaluate([self._det_at(0.5, _ABOVE)], _FRAME_META, s)
        assert out["result"]["count_out"] == 1

    def test_confirm_2_needs_two_frames(self):
        op = self._make(confirm=2)
        s = op.evaluate([self._det_at(0.5, _ABOVE)], _FRAME_META, {})["state_next"]
        s2 = op.evaluate([self._det_at(0.5, _BELOW)], _FRAME_META, s)["state_next"]
        assert s2["count_in"] == 0                   # pending, not confirmed yet
        s3 = op.evaluate([self._det_at(0.5, _BELOW)], _FRAME_META, s2)["state_next"]
        assert s3["count_in"] == 1                   # confirmed on second frame

    def test_direction_in_only(self):
        op = self._make(direction="in", confirm=1)
        s = op.evaluate([self._det_at(0.5, _ABOVE)], _FRAME_META, {})["state_next"]
        out = op.evaluate([self._det_at(0.5, _BELOW)], _FRAME_META, s)
        assert out["metric_value"] == 1

    def test_direction_out_only(self):
        op = self._make(direction="out", confirm=1)
        s = op.evaluate([self._det_at(0.5, _BELOW)], _FRAME_META, {})["state_next"]
        out = op.evaluate([self._det_at(0.5, _ABOVE)], _FRAME_META, s)
        assert out["metric_value"] == 1

    def test_low_confidence_ignored(self):
        op = self._make(confirm=1)
        s = op.evaluate([self._det_at(0.5, _ABOVE, conf=0.3)], _FRAME_META, {})["state_next"]
        out = op.evaluate([self._det_at(0.5, _BELOW, conf=0.3)], _FRAME_META, s)
        assert out["result"]["count_in"] == 0

    def test_no_detections_zeros(self):
        op = self._make()
        out = op.evaluate([], _FRAME_META, {})
        assert out["result"]["count_total"] == 0

    def test_condition_satisfied_when_crossings_exist(self):
        op = self._make(confirm=1)
        s = op.evaluate([self._det_at(0.5, _ABOVE)], _FRAME_META, {})["state_next"]
        out = op.evaluate([self._det_at(0.5, _BELOW)], _FRAME_META, s)
        assert out["condition_satisfied"] is True

    def test_debounce_prevents_immediate_reversal(self):
        op = self._make(confirm=1, debounce=10)
        s = op.evaluate([self._det_at(0.5, _ABOVE)], _FRAME_META, {})["state_next"]
        s2 = op.evaluate([self._det_at(0.5, _BELOW)], _FRAME_META, s)["state_next"]  # count_in=1
        out = op.evaluate([self._det_at(0.5, _ABOVE)], _FRAME_META, s2)
        assert out["result"]["count_out"] == 0   # debounced


# ---------------------------------------------------------------------------
# EpiZoneOperation
# ---------------------------------------------------------------------------

class TestEpiZoneOperation:

    _ZONE = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]

    def _make(self, watch=None):
        from app.domain.services.operations.canonical.epi_zone import EpiZoneOperation
        return EpiZoneOperation({
            "zone_points": self._ZONE,
            "watch_classes": watch or ["no_helmet"],
            "confidence_threshold": 0.5,
        })

    def _det(self, cls, cx_norm, cy_norm, conf=0.9):
        w, h = _FRAME_META["width"], _FRAME_META["height"]
        cx, cy = cx_norm * w, cy_norm * h
        return {"class": cls, "confidence": conf, "bbox": [cx - 5, cy - 5, 10, 10]}

    # --- validate_config ---

    def test_validate_valid_config(self):
        op = self._make()
        assert op.validate_config(op.config) == []

    def test_validate_too_few_zone_points(self):
        from app.domain.services.operations.canonical.epi_zone import EpiZoneOperation
        op = EpiZoneOperation({"zone_points": [[0, 0], [1, 1]], "watch_classes": ["no_helmet"]})
        errs = op.validate_config(op.config)
        assert any("zone_points" in e for e in errs)

    def test_validate_empty_watch_classes(self):
        from app.domain.services.operations.canonical.epi_zone import EpiZoneOperation
        op = EpiZoneOperation({"zone_points": self._ZONE, "watch_classes": []})
        errs = op.validate_config(op.config)
        assert any("watch_classes" in e for e in errs)

    def test_validate_invalid_epi_class(self):
        from app.domain.services.operations.canonical.epi_zone import EpiZoneOperation
        op = EpiZoneOperation({"zone_points": self._ZONE, "watch_classes": ["no_shoes"]})
        errs = op.validate_config(op.config)
        assert any("no_shoes" in e for e in errs)

    # --- evaluate ---

    def test_violation_inside_zone_detected(self):
        op = self._make()
        det = self._det("no_helmet", 0.5, 0.5)   # centroid inside _ZONE
        out = op.evaluate([det], _FRAME_META, {})
        assert out["condition_satisfied"] is True
        assert out["result"]["count"] == 1

    def test_violation_outside_zone_not_counted(self):
        op = self._make()
        det = self._det("no_helmet", 0.05, 0.05)  # outside zone
        out = op.evaluate([det], _FRAME_META, {})
        assert out["condition_satisfied"] is False
        assert out["result"]["count"] == 0

    def test_unwatched_class_ignored(self):
        op = self._make(watch=["no_helmet"])
        det = self._det("no_vest", 0.5, 0.5)
        out = op.evaluate([det], _FRAME_META, {})
        assert out["result"]["count"] == 0

    def test_low_confidence_ignored(self):
        op = self._make()
        det = self._det("no_helmet", 0.5, 0.5, conf=0.3)
        out = op.evaluate([det], _FRAME_META, {})
        assert out["result"]["count"] == 0

    def test_multiple_violations_counted(self):
        op = self._make(watch=["no_helmet", "no_vest"])
        dets = [self._det("no_helmet", 0.5, 0.5), self._det("no_vest", 0.6, 0.6)]
        out = op.evaluate(dets, _FRAME_META, {})
        assert out["result"]["count"] == 2

    def test_no_detections_no_violation(self):
        op = self._make()
        out = op.evaluate([], _FRAME_META, {})
        assert out["condition_satisfied"] is False

    def test_state_passed_through(self):
        op = self._make()
        s = {"custom": "val"}
        out = op.evaluate([], _FRAME_META, s)
        assert out["state_next"] == s


# ---------------------------------------------------------------------------
# _compute_iou / _compute_distance (overlap_dynamic helpers)
# ---------------------------------------------------------------------------

class TestOverlapDynamicHelpers:

    def test_compute_iou_perfect_overlap(self):
        from app.domain.services.operations.canonical.overlap_dynamic import _compute_iou
        box = [0, 0, 100, 100]
        assert abs(_compute_iou(box, box, 100, 100) - 1.0) < 1e-9

    def test_compute_iou_no_overlap(self):
        from app.domain.services.operations.canonical.overlap_dynamic import _compute_iou
        assert _compute_iou([0, 0, 30, 30], [70, 70, 30, 30], 100, 100) == 0.0

    def test_compute_distance_same_box_zero(self):
        from app.domain.services.operations.canonical.overlap_dynamic import _compute_distance
        box = [25, 25, 50, 50]
        assert _compute_distance(box, box, 100, 100) == 0.0

    def test_compute_distance_far_apart(self):
        from app.domain.services.operations.canonical.overlap_dynamic import _compute_distance
        box_a = [0, 0, 0, 0]
        box_b = [100, 100, 0, 0]
        dist = _compute_distance(box_a, box_b, 100, 100)
        assert dist > 0


# ---------------------------------------------------------------------------
# _point_in_polygon (base helper)
# ---------------------------------------------------------------------------

class TestPointInPolygon:

    def test_centre_inside_square(self):
        from app.domain.services.operations.base import _point_in_polygon
        roi = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
        assert _point_in_polygon(0.5, 0.5, roi) is True

    def test_corner_outside_square(self):
        from app.domain.services.operations.base import _point_in_polygon
        roi = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
        assert _point_in_polygon(0.0, 0.0, roi) is False

    def test_empty_polygon_false(self):
        from app.domain.services.operations.base import _point_in_polygon
        assert _point_in_polygon(0.5, 0.5, []) is False
