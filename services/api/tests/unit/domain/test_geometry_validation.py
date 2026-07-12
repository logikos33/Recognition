"""Tests: geometry_validation.py — validação de config de deploy (WS-C2)."""
from __future__ import annotations

from app.domain.services.geometry_validation import validate_deployment_config


def _valid_config(**overrides):
    config = {
        "roi": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]],
        "classes": ["helmet", "no_helmet"],
        "thresholds": {"helmet": 0.6, "no_helmet": 0.5},
    }
    config.update(overrides)
    return config


class TestValidateDeploymentConfig:
    def test_valid_roi_config_has_no_errors(self):
        assert validate_deployment_config(_valid_config()) == []

    def test_valid_line_config_has_no_errors(self):
        config = _valid_config(line=[[0.0, 0.5], [1.0, 0.5]])
        del config["roi"]
        assert validate_deployment_config(config) == []

    def test_non_dict_config_rejected(self):
        assert validate_deployment_config("not-a-dict") == ["config deve ser um objeto"]

    def test_roi_and_line_together_rejected(self):
        config = _valid_config(line=[[0.0, 0.5], [1.0, 0.5]])
        errors = validate_deployment_config(config)
        assert any("mutuamente exclusivos" in e for e in errors)

    def test_roi_with_fewer_than_3_points_rejected(self):
        config = _valid_config(roi=[[0.1, 0.1], [0.9, 0.9]])
        errors = validate_deployment_config(config)
        assert any("roi" in e for e in errors)

    def test_line_with_wrong_point_count_rejected(self):
        config = _valid_config(line=[[0.0, 0.5]])
        del config["roi"]
        errors = validate_deployment_config(config)
        assert any("line" in e for e in errors)

    def test_point_outside_0_1_range_rejected(self):
        config = _valid_config(roi=[[0.1, 0.1], [1.5, 0.1], [0.9, 0.9]])
        errors = validate_deployment_config(config)
        assert any("roi" in e for e in errors)

    def test_empty_classes_rejected(self):
        config = _valid_config(classes=[])
        errors = validate_deployment_config(config)
        assert any("classes" in e for e in errors)

    def test_missing_classes_rejected(self):
        config = _valid_config()
        del config["classes"]
        errors = validate_deployment_config(config)
        assert any("classes" in e for e in errors)

    def test_threshold_class_not_in_classes_rejected(self):
        config = _valid_config(thresholds={"vest": 0.5})
        errors = validate_deployment_config(config)
        assert any("fora de 'classes'" in e for e in errors)

    def test_threshold_out_of_range_rejected(self):
        config = _valid_config(thresholds={"helmet": 1.5})
        errors = validate_deployment_config(config)
        assert any("threshold" in e for e in errors)

    def test_threshold_non_numeric_rejected(self):
        config = _valid_config(thresholds={"helmet": "high"})
        errors = validate_deployment_config(config)
        assert any("threshold" in e for e in errors)

    def test_missing_thresholds_defaults_to_empty_and_is_valid(self):
        config = _valid_config()
        del config["thresholds"]
        assert validate_deployment_config(config) == []

    def test_bool_is_not_a_valid_point_coordinate(self):
        config = _valid_config(roi=[[0.1, True], [0.9, 0.1], [0.9, 0.9]])
        errors = validate_deployment_config(config)
        assert any("roi" in e for e in errors)
