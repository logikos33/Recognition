"""
Tests: camera_module_service.py — pure logic, no DB/Flask needed (item-24).

Cobre resolve_active_module, get_model_key_for_module, validate_schedule_rules,
e os helpers privados _time_in_range e _valid_time_fmt.
"""
from datetime import datetime


from app.domain.services.camera_module_service import (
    VALID_MODULES,
    get_model_key_for_module,
    resolve_active_module,
    validate_schedule_rules,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _cam(active_module="epi", schedule_rules=None, **model_ids):
    cam = {"active_module": active_module}
    if schedule_rules is not None:
        cam["schedule_rules"] = schedule_rules
    cam.update(model_ids)
    return cam


def _mon(hour=10, minute=0, weekday=0):
    """Monday = weekday 0 → day_of_week 1. June 1, 2026 = Monday (verified)."""
    return datetime(2026, 6, 1 + weekday, hour, minute)


# ---------------------------------------------------------------------------
# resolve_active_module — no schedule rules
# ---------------------------------------------------------------------------

class TestResolveActiveModuleNoRules:

    def test_no_rules_returns_default_module(self):
        cam = _cam(active_module="epi")
        assert resolve_active_module(cam, _mon()) == "epi"

    def test_no_rules_empty_list_returns_default(self):
        cam = _cam(active_module="quality", schedule_rules=[])
        assert resolve_active_module(cam, _mon()) == "quality"

    def test_no_rules_active_module_none_returns_none(self):
        cam = _cam(active_module="none")
        result = resolve_active_module(cam, _mon())
        assert result is None

    def test_no_rules_active_module_missing_defaults_to_epi(self):
        cam = {}
        assert resolve_active_module(cam, _mon()) == "epi"

    def test_schedule_rules_as_string_parses_empty(self):
        cam = _cam(active_module="epi", schedule_rules="[]")
        assert resolve_active_module(cam, _mon()) == "epi"

    def test_schedule_rules_invalid_json_string_falls_back(self):
        cam = _cam(active_module="quality", schedule_rules="{bad json}")
        assert resolve_active_module(cam, _mon()) == "quality"

    def test_no_now_uses_current_time(self):
        cam = _cam(active_module="epi")
        result = resolve_active_module(cam)
        assert result == "epi"


# ---------------------------------------------------------------------------
# resolve_active_module — with schedule rules
# ---------------------------------------------------------------------------

class TestResolveActiveModuleWithRules:

    def _rule(self, days, start, end, module):
        return {"days": days, "start": start, "end": end, "module": module}

    def test_matches_weekday_and_time(self):
        # Monday = day_of_week 1, 10:00 in 08:00–18:00
        rules = [self._rule([1, 2, 3, 4, 5], "08:00", "18:00", "quality")]
        cam = _cam(active_module="epi", schedule_rules=rules)
        result = resolve_active_module(cam, _mon(hour=10))
        assert result == "quality"

    def test_no_match_on_wrong_day(self):
        # Saturday = weekday 5 → day_of_week 6, rule is only Mon–Fri
        rules = [self._rule([1, 2, 3, 4, 5], "08:00", "18:00", "quality")]
        cam = _cam(active_module="epi", schedule_rules=rules)
        saturday = datetime(2026, 6, 6, 10, 0)  # Saturday
        assert resolve_active_module(cam, saturday) == "epi"

    def test_no_match_outside_time_range(self):
        # 20:00 is outside 08:00–18:00
        rules = [self._rule([1, 2, 3, 4, 5], "08:00", "18:00", "quality")]
        cam = _cam(active_module="epi", schedule_rules=rules)
        result = resolve_active_module(cam, _mon(hour=20))
        assert result == "epi"

    def test_module_none_returns_none(self):
        # Weekend → paused
        rules = [self._rule([6, 7], "00:00", "23:59", "none")]
        cam = _cam(active_module="epi", schedule_rules=rules)
        saturday = datetime(2026, 6, 6, 12, 0)
        assert resolve_active_module(cam, saturday) is None

    def test_invalid_module_in_rule_falls_back_to_default(self):
        rules = [self._rule([1], "08:00", "18:00", "invalid_module")]
        cam = _cam(active_module="quality", schedule_rules=rules)
        result = resolve_active_module(cam, _mon(hour=10))
        assert result == "quality"

    def test_first_matching_rule_wins(self):
        rules = [
            self._rule([1, 2, 3, 4, 5], "08:00", "12:00", "quality"),
            self._rule([1, 2, 3, 4, 5], "08:00", "18:00", "epi"),
        ]
        cam = _cam(active_module="epi", schedule_rules=rules)
        assert resolve_active_module(cam, _mon(hour=10)) == "quality"

    def test_midnight_crossing_rule_matches_before_midnight(self):
        rules = [self._rule([1], "22:00", "06:00", "basic")]
        cam = _cam(active_module="epi", schedule_rules=rules)
        result = resolve_active_module(cam, _mon(hour=23))
        assert result == "basic"

    def test_midnight_crossing_rule_matches_after_midnight(self):
        # Rule: Tuesday (day_of_week=2) 22:00–06:00 (midnight-crossing).
        # At 01:00 on Tuesday, "01:00" <= "06:00" → within range.
        # June 2, 2026 = Tuesday (weekday=1 → day_of_week=2).
        rules = [self._rule([2], "22:00", "06:00", "basic")]
        cam = _cam(active_module="epi", schedule_rules=rules)
        tuesday_early = datetime(2026, 6, 2, 1, 0)  # Tuesday 01:00
        assert resolve_active_module(cam, tuesday_early) == "basic"

    def test_non_dict_rule_is_skipped(self):
        rules = ["not a dict", self._rule([1], "08:00", "18:00", "quality")]
        cam = _cam(active_module="epi", schedule_rules=rules)
        assert resolve_active_module(cam, _mon(hour=10)) == "quality"

    def test_schedule_rules_as_json_string(self):
        import json
        rules = [self._rule([1], "08:00", "18:00", "quality")]
        cam = _cam(active_module="epi", schedule_rules=json.dumps(rules))
        assert resolve_active_module(cam, _mon(hour=10)) == "quality"

    def test_all_valid_modules_accepted(self):
        for module in VALID_MODULES:
            rules = [self._rule([1], "00:00", "23:59", module)]
            cam = _cam(active_module="epi", schedule_rules=rules)
            result = resolve_active_module(cam, _mon())
            assert result == module


# ---------------------------------------------------------------------------
# get_model_key_for_module
# ---------------------------------------------------------------------------

class TestGetModelKeyForModule:

    def test_epi_returns_model_epi_id(self):
        cam = {"model_epi_id": "uuid-epi-1"}
        assert get_model_key_for_module(cam, "epi") == "uuid-epi-1"

    def test_quality_returns_model_quality_id(self):
        cam = {"model_quality_id": "uuid-quality-1"}
        assert get_model_key_for_module(cam, "quality") == "uuid-quality-1"

    def test_counting_returns_model_counting_id(self):
        cam = {"model_counting_id": "uuid-counting-1"}
        assert get_model_key_for_module(cam, "counting") == "uuid-counting-1"

    def test_unknown_module_returns_none(self):
        cam = {"model_epi_id": "uuid-epi-1"}
        assert get_model_key_for_module(cam, "unknown") is None

    def test_missing_model_id_returns_none(self):
        cam = {}  # no model_epi_id key
        assert get_model_key_for_module(cam, "epi") is None

    def test_none_model_id_returns_none(self):
        cam = {"model_epi_id": None}
        assert get_model_key_for_module(cam, "epi") is None

    def test_basic_module_not_in_mapping_returns_none(self):
        cam = {"model_epi_id": "uuid"}
        assert get_model_key_for_module(cam, "basic") is None


# ---------------------------------------------------------------------------
# validate_schedule_rules
# ---------------------------------------------------------------------------

class TestValidateScheduleRules:

    def test_empty_list_is_valid(self):
        ok, msg = validate_schedule_rules([])
        assert ok is True
        assert msg == ""

    def test_valid_rule_passes(self):
        rules = [{"days": [1, 2, 3, 4, 5], "start": "08:00", "end": "18:00", "module": "epi"}]
        ok, msg = validate_schedule_rules(rules)
        assert ok is True

    def test_not_a_list_fails(self):
        ok, msg = validate_schedule_rules({"days": [1]})
        assert ok is False
        assert "lista" in msg

    def test_rule_not_dict_fails(self):
        ok, msg = validate_schedule_rules(["not a dict"])
        assert ok is False

    def test_days_missing_fails(self):
        rules = [{"start": "08:00", "end": "18:00", "module": "epi"}]
        ok, msg = validate_schedule_rules(rules)
        assert ok is False
        assert "days" in msg

    def test_days_empty_fails(self):
        rules = [{"days": [], "start": "08:00", "end": "18:00", "module": "epi"}]
        ok, msg = validate_schedule_rules(rules)
        assert ok is False

    def test_days_out_of_range_fails(self):
        rules = [{"days": [0, 8], "start": "08:00", "end": "18:00", "module": "epi"}]
        ok, msg = validate_schedule_rules(rules)
        assert ok is False
        assert "1 (seg)" in msg or "inteiros" in msg

    def test_invalid_start_time_fails(self):
        rules = [{"days": [1], "start": "25:00", "end": "18:00", "module": "epi"}]
        ok, msg = validate_schedule_rules(rules)
        assert ok is False
        assert "start" in msg

    def test_invalid_end_time_fails(self):
        rules = [{"days": [1], "start": "08:00", "end": "60:00", "module": "epi"}]
        ok, msg = validate_schedule_rules(rules)
        assert ok is False
        assert "end" in msg

    def test_invalid_module_fails(self):
        rules = [{"days": [1], "start": "08:00", "end": "18:00", "module": "invalid"}]
        ok, msg = validate_schedule_rules(rules)
        assert ok is False
        assert "inválido" in msg

    def test_module_none_is_valid(self):
        rules = [{"days": [6, 7], "start": "00:00", "end": "23:59", "module": "none"}]
        ok, msg = validate_schedule_rules(rules)
        assert ok is True

    def test_all_valid_modules_pass(self):
        for module in (VALID_MODULES | {"none"}):
            rules = [{"days": [1], "start": "00:00", "end": "23:59", "module": module}]
            ok, msg = validate_schedule_rules(rules)
            assert ok is True, f"Module {module} should be valid: {msg}"

    def test_multiple_rules_all_must_be_valid(self):
        rules = [
            {"days": [1, 2, 3, 4, 5], "start": "08:00", "end": "18:00", "module": "epi"},
            {"days": [6, 7], "start": "00:00", "end": "23:59", "module": "none"},
        ]
        ok, msg = validate_schedule_rules(rules)
        assert ok is True

    def test_error_reports_rule_index(self):
        rules = [
            {"days": [1], "start": "08:00", "end": "18:00", "module": "epi"},  # valid
            {"days": [2], "start": "08:00", "end": "18:00", "module": "bad"},  # invalid
        ]
        ok, msg = validate_schedule_rules(rules)
        assert ok is False
        assert "1" in msg  # second rule (index 1)
