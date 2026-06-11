"""
Tests for task-039: per-camera tuning — exclude_zones + day_night_profile.

Eval cases:
  - detecção dentro de exclude_zone é descartada (casos sintéticos)
  - perfil noite aplica threshold maior
  - validate_config rejeita geometria inválida e confidence fora de range
  - defaults preservam comportamento anterior (zero regressão)
"""
from app.domain.services.operations.base import (
    _effective_threshold,
    _is_in_exclude_zone,
    _validate_day_night_profile,
    _validate_exclude_zones,
)
from app.domain.services.operations.canonical.count_static import CountStaticOperation
from app.domain.services.operations.canonical.counting_line import CountingLineOperation
from app.domain.services.operations.canonical.epi_zone import EpiZoneOperation
from app.domain.services.operations.canonical.position import PositionOperation

# ── test helpers ──────────────────────────────────────────────────────────────

# Full-frame polygon (covers everything in [0,1]×[0,1])
_FULL_FRAME = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]

# Small square in the top-right corner: x∈[0.7,0.9], y∈[0.7,0.9]
_CORNER_ZONE = [[0.7, 0.7], [0.9, 0.7], [0.9, 0.9], [0.7, 0.9]]


def _det(cls: str, conf: float, cx_n: float, cy_n: float, fw: int = 640, fh: int = 360) -> dict:
    """Cria detecção com centro normalizado (cx_n, cy_n).

    bbox = [x_left, y_top, box_w, box_h] onde x_left = cx_n*fw e box_w = 0
    → cx = (x_left + 0/2) / fw = cx_n  ✓
    """
    return {
        "class": cls,
        "confidence": conf,
        "bbox": [cx_n * fw, cy_n * fh, 0, 0],
    }


def _meta(period: str = "day", w: int = 640, h: int = 360) -> dict:
    return {"width": w, "height": h, "period": period}


# ── _effective_threshold ──────────────────────────────────────────────────────

class TestEffectiveThreshold:
    def test_no_profile_returns_base_threshold(self):
        assert _effective_threshold({"confidence_threshold": 0.6}, _meta()) == 0.6

    def test_day_profile_applied_for_day_period(self):
        cfg = {
            "confidence_threshold": 0.5,
            "day_night_profile": {"day": {"confidence": 0.4}, "night": {"confidence": 0.8}},
        }
        assert _effective_threshold(cfg, _meta(period="day")) == 0.4

    def test_night_profile_applied_for_night_period(self):
        cfg = {
            "confidence_threshold": 0.5,
            "day_night_profile": {"day": {"confidence": 0.4}, "night": {"confidence": 0.8}},
        }
        assert _effective_threshold(cfg, _meta(period="night")) == 0.8

    def test_missing_period_key_falls_back_to_base(self):
        cfg = {
            "confidence_threshold": 0.5,
            "day_night_profile": {"night": {"confidence": 0.8}},
        }
        assert _effective_threshold(cfg, _meta(period="day")) == 0.5

    def test_missing_period_in_frame_meta_defaults_to_day(self):
        cfg = {
            "confidence_threshold": 0.5,
            "day_night_profile": {"day": {"confidence": 0.3}},
        }
        assert _effective_threshold(cfg, {"width": 640, "height": 360}) == 0.3

    def test_default_threshold_when_no_config(self):
        assert _effective_threshold({}, _meta()) == 0.5


# ── _is_in_exclude_zone ───────────────────────────────────────────────────────

class TestIsInExcludeZone:
    def test_point_inside_zone_returns_true(self):
        assert _is_in_exclude_zone(0.8, 0.8, [_CORNER_ZONE]) is True

    def test_point_outside_zone_returns_false(self):
        assert _is_in_exclude_zone(0.1, 0.1, [_CORNER_ZONE]) is False

    def test_empty_zones_always_false(self):
        assert _is_in_exclude_zone(0.5, 0.5, []) is False

    def test_none_zones_always_false(self):
        assert _is_in_exclude_zone(0.5, 0.5, None) is False  # type: ignore[arg-type]

    def test_zone_with_less_than_3_points_is_ignored(self):
        short = [[0.0, 0.0], [1.0, 0.0]]
        assert _is_in_exclude_zone(0.5, 0.5, [short]) is False

    def test_multiple_zones_any_match_returns_true(self):
        zone_a = [[0.0, 0.0], [0.2, 0.0], [0.2, 0.2], [0.0, 0.2]]
        zone_b = [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]]
        assert _is_in_exclude_zone(0.5, 0.5, [zone_a, zone_b]) is True
        assert _is_in_exclude_zone(0.1, 0.1, [zone_a, zone_b]) is True
        assert _is_in_exclude_zone(0.9, 0.9, [zone_a, zone_b]) is False


# ── _validate_exclude_zones ───────────────────────────────────────────────────

class TestValidateExcludeZones:
    def test_valid_triangle_no_errors(self):
        zones = [[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]]]
        assert _validate_exclude_zones(zones) == []

    def test_empty_list_no_errors(self):
        assert _validate_exclude_zones([]) == []

    def test_zone_with_2_points_error(self):
        errors = _validate_exclude_zones([[[0.1, 0.1], [0.5, 0.1]]])
        assert any("ao menos 3 pontos" in e for e in errors)

    def test_coord_above_1_error(self):
        errors = _validate_exclude_zones([[[1.5, 0.1], [0.5, 0.1], [0.5, 0.5]]])
        assert any("fora de [0,1]" in e for e in errors)

    def test_coord_below_0_error(self):
        errors = _validate_exclude_zones([[[-0.1, 0.1], [0.5, 0.1], [0.5, 0.5]]])
        assert any("fora de [0,1]" in e for e in errors)

    def test_malformed_point_error(self):
        errors = _validate_exclude_zones([[[0.1], [0.5, 0.1], [0.5, 0.5]]])
        assert len(errors) > 0

    def test_multiple_zones_validates_all(self):
        zones = [
            [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]],  # valid
            [[0.1, 0.1], [0.5, 0.1]],               # invalid (2 pts)
        ]
        errors = _validate_exclude_zones(zones)
        assert any("exclude_zones[1]" in e for e in errors)


# ── _validate_day_night_profile ───────────────────────────────────────────────

class TestValidateDayNightProfile:
    def test_valid_profile_no_errors(self):
        assert _validate_day_night_profile(
            {"day": {"confidence": 0.5}, "night": {"confidence": 0.7}}
        ) == []

    def test_empty_profile_no_errors(self):
        assert _validate_day_night_profile({}) == []

    def test_none_profile_no_errors(self):
        assert _validate_day_night_profile(None) == []  # type: ignore[arg-type]

    def test_night_confidence_below_minimum_error(self):
        errors = _validate_day_night_profile({"night": {"confidence": 0.05}})
        assert any("night.confidence" in e for e in errors)

    def test_day_confidence_above_maximum_error(self):
        errors = _validate_day_night_profile({"day": {"confidence": 1.5}})
        assert any("day.confidence" in e for e in errors)

    def test_boundary_values_valid(self):
        assert _validate_day_night_profile(
            {"day": {"confidence": 0.1}, "night": {"confidence": 1.0}}
        ) == []


# ── EpiZoneOperation ──────────────────────────────────────────────────────────

class TestEpiZoneExcludeZones:
    def _make_op(self, exclude_zones=None):
        cfg = {
            "zone_points": _FULL_FRAME,
            "watch_classes": ["no_helmet"],
            "confidence_threshold": 0.5,
        }
        if exclude_zones is not None:
            cfg["exclude_zones"] = exclude_zones
        return EpiZoneOperation(cfg)

    def test_detection_outside_exclude_zone_is_detected(self):
        op = self._make_op(exclude_zones=[_CORNER_ZONE])
        result = op.evaluate([_det("no_helmet", 0.9, 0.3, 0.3)], _meta(), {})
        assert result["result"]["count"] == 1
        assert result["condition_satisfied"] is True

    def test_detection_inside_exclude_zone_is_discarded(self):
        op = self._make_op(exclude_zones=[_CORNER_ZONE])
        # (0.8, 0.8) is inside _CORNER_ZONE
        result = op.evaluate([_det("no_helmet", 0.9, 0.8, 0.8)], _meta(), {})
        assert result["result"]["count"] == 0
        assert result["condition_satisfied"] is False

    def test_no_exclude_zones_preserves_original_behavior(self):
        op = self._make_op()
        result = op.evaluate([_det("no_helmet", 0.9, 0.8, 0.8)], _meta(), {})
        assert result["result"]["count"] == 1


class TestEpiZoneDayNightProfile:
    def _make_op(self, profile):
        return EpiZoneOperation({
            "zone_points": _FULL_FRAME,
            "watch_classes": ["no_helmet"],
            "confidence_threshold": 0.5,
            "day_night_profile": profile,
        })

    def test_passes_day_threshold_fails_night(self):
        op = self._make_op({"day": {"confidence": 0.4}, "night": {"confidence": 0.8}})
        det = _det("no_helmet", 0.6, 0.5, 0.5)  # conf 0.6: ≥ day(0.4), < night(0.8)
        assert op.evaluate([det], _meta(period="day"), {})["result"]["count"] == 1
        assert op.evaluate([det], _meta(period="night"), {})["result"]["count"] == 0

    def test_detection_below_day_threshold_blocked(self):
        op = self._make_op({"day": {"confidence": 0.8}})
        result = op.evaluate([_det("no_helmet", 0.6, 0.5, 0.5)], _meta(period="day"), {})
        assert result["result"]["count"] == 0


class TestEpiZoneValidateConfig:
    def test_invalid_exclude_zone_geometry_rejected(self):
        cfg = {
            "zone_points": _FULL_FRAME,
            "watch_classes": ["no_helmet"],
            "exclude_zones": [[[0.1, 0.1]]],  # 1 ponto → inválido
        }
        errors = EpiZoneOperation(cfg).validate_config(cfg)
        assert any("exclude_zones" in e for e in errors)

    def test_invalid_day_night_confidence_rejected(self):
        cfg = {
            "zone_points": _FULL_FRAME,
            "watch_classes": ["no_helmet"],
            "day_night_profile": {"night": {"confidence": 2.0}},
        }
        errors = EpiZoneOperation(cfg).validate_config(cfg)
        assert any("night.confidence" in e for e in errors)

    def test_valid_config_with_both_fields_no_errors(self):
        cfg = {
            "zone_points": _FULL_FRAME,
            "watch_classes": ["no_helmet"],
            "confidence_threshold": 0.5,
            "exclude_zones": [_CORNER_ZONE],
            "day_night_profile": {"day": {"confidence": 0.4}, "night": {"confidence": 0.7}},
        }
        errors = EpiZoneOperation(cfg).validate_config(cfg)
        assert errors == []


# ── CountStaticOperation ──────────────────────────────────────────────────────

class TestCountStaticExcludeZones:
    def _make_op(self, exclude_zones=None):
        cfg = {
            "target_class": "person",
            "roi_points": _FULL_FRAME,
            "metric": "count",
            "confidence_threshold": 0.5,
        }
        if exclude_zones is not None:
            cfg["exclude_zones"] = exclude_zones
        return CountStaticOperation(cfg)

    def test_detection_in_exclude_zone_not_counted(self):
        op = self._make_op(exclude_zones=[_CORNER_ZONE])
        result = op.evaluate([_det("person", 0.9, 0.8, 0.8)], _meta(), {})
        assert result["result"]["count"] == 0

    def test_detection_outside_exclude_zone_counted(self):
        op = self._make_op(exclude_zones=[_CORNER_ZONE])
        result = op.evaluate([_det("person", 0.9, 0.3, 0.3)], _meta(), {})
        assert result["result"]["count"] == 1

    def test_night_profile_raises_threshold(self):
        op = CountStaticOperation({
            "target_class": "person",
            "roi_points": _FULL_FRAME,
            "metric": "count",
            "confidence_threshold": 0.5,
            "day_night_profile": {"night": {"confidence": 0.9}},
        })
        det = _det("person", 0.7, 0.5, 0.5)
        assert op.evaluate([det], _meta(period="day"), {})["result"]["count"] == 1
        assert op.evaluate([det], _meta(period="night"), {})["result"]["count"] == 0


# ── CountingLineOperation ─────────────────────────────────────────────────────

class TestCountingLineExcludeZones:
    def _make_op(self, exclude_zones=None):
        cfg = {
            "line_points": [[0.0, 0.5], [1.0, 0.5]],
            "direction": "both",
            "target_class": "person",
            "confidence_threshold": 0.5,
        }
        if exclude_zones is not None:
            cfg["exclude_zones"] = exclude_zones
        return CountingLineOperation(cfg)

    def test_detection_in_exclude_zone_not_tracked(self):
        """Detecção na zona de exclusão não entra no rastreamento de cruzamento."""
        op = self._make_op(exclude_zones=[_CORNER_ZONE])
        result = op.evaluate([_det("person", 0.9, 0.8, 0.8)], _meta(), {})
        assert result["state_next"]["prev_sides"] == {}

    def test_detection_outside_exclude_zone_is_tracked(self):
        op = self._make_op(exclude_zones=[_CORNER_ZONE])
        result = op.evaluate([_det("person", 0.9, 0.3, 0.3)], _meta(), {})
        assert len(result["state_next"]["prev_sides"]) == 1


# ── PositionOperation ─────────────────────────────────────────────────────────

class TestPositionExcludeZones:
    def _make_op(self, exclude_zones=None):
        cfg = {
            "target_class": "person",
            "roi_points": _FULL_FRAME,
            "metric": "state",
            "confidence_threshold": 0.5,
        }
        if exclude_zones is not None:
            cfg["exclude_zones"] = exclude_zones
        return PositionOperation(cfg)

    def test_detection_in_exclude_zone_not_in_roi(self):
        op = self._make_op(exclude_zones=[_CORNER_ZONE])
        result = op.evaluate([_det("person", 0.9, 0.8, 0.8)], _meta(), {})
        assert result["result"]["count"] == 0
        assert result["condition_satisfied"] is False

    def test_detection_outside_exclude_zone_in_roi(self):
        op = self._make_op(exclude_zones=[_CORNER_ZONE])
        result = op.evaluate([_det("person", 0.9, 0.3, 0.3)], _meta(), {})
        assert result["result"]["count"] == 1
        assert result["condition_satisfied"] is True
