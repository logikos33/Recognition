"""
Tests: OperationTypeRegistry — uncovered lines 37, 48-50, 56, 65.

_types is a class-level dict; each test class saves/restores it to prevent
cross-test contamination.
"""
from app.domain.services.operations.base import BaseOperation
from app.domain.services.operations.registry import OperationTypeRegistry


# ---------------------------------------------------------------------------
# Concrete stub operations for testing
# ---------------------------------------------------------------------------

class _OpAlpha(BaseOperation):
    type_id = "alpha"
    type_label = "Alpha"
    available_modules = ["ppe", "quality"]
    config_schema = {}
    metric_options = []
    description = "Alpha op"

    def validate_config(self, config):
        return []

    def evaluate(self, detections, frame_meta, state):
        return {}


class _OpBeta(BaseOperation):
    type_id = "beta"
    type_label = "Beta"
    available_modules = ["*"]
    config_schema = {"type": "object"}
    metric_options = ["count"]
    description = "Beta op (universal)"

    def validate_config(self, config):
        return []

    def evaluate(self, detections, frame_meta, state):
        return {}


class _OpGamma(BaseOperation):
    type_id = "gamma"
    type_label = "Gamma"
    available_modules = ["fueling"]
    config_schema = {}
    metric_options = []
    description = "Gamma op"

    def validate_config(self, config):
        return []

    def evaluate(self, detections, frame_meta, state):
        return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snapshot():
    return dict(OperationTypeRegistry._types)


def _restore(snapshot):
    OperationTypeRegistry._types.clear()
    OperationTypeRegistry._types.update(snapshot)


# ---------------------------------------------------------------------------
# TestRegister
# ---------------------------------------------------------------------------

class TestRegister:
    def setup_method(self):
        self._snap = _snapshot()

    def teardown_method(self):
        _restore(self._snap)

    def test_register_adds_to_types(self):
        OperationTypeRegistry.register(_OpAlpha)
        assert "alpha" in OperationTypeRegistry._types

    def test_register_maps_type_id_to_class(self):
        OperationTypeRegistry.register(_OpAlpha)
        assert OperationTypeRegistry._types["alpha"] is _OpAlpha

    def test_register_multiple(self):
        OperationTypeRegistry.register(_OpAlpha)
        OperationTypeRegistry.register(_OpBeta)
        assert "alpha" in OperationTypeRegistry._types
        assert "beta" in OperationTypeRegistry._types


# ---------------------------------------------------------------------------
# TestGet — line 37
# ---------------------------------------------------------------------------

class TestGet:
    def setup_method(self):
        self._snap = _snapshot()
        OperationTypeRegistry._types.clear()
        OperationTypeRegistry.register(_OpAlpha)
        OperationTypeRegistry.register(_OpBeta)

    def teardown_method(self):
        _restore(self._snap)

    def test_get_known_type_returns_class(self):
        assert OperationTypeRegistry.get("alpha") is _OpAlpha

    def test_get_unknown_type_returns_none(self):
        assert OperationTypeRegistry.get("does-not-exist") is None

    def test_get_another_registered_type(self):
        assert OperationTypeRegistry.get("beta") is _OpBeta


# ---------------------------------------------------------------------------
# TestGetForModule — lines 48-50
# ---------------------------------------------------------------------------

class TestGetForModule:
    def setup_method(self):
        self._snap = _snapshot()
        OperationTypeRegistry._types.clear()
        OperationTypeRegistry.register(_OpAlpha)   # available_modules = ["ppe", "quality"]
        OperationTypeRegistry.register(_OpBeta)    # available_modules = ["*"]
        OperationTypeRegistry.register(_OpGamma)   # available_modules = ["fueling"]

    def teardown_method(self):
        _restore(self._snap)

    def test_returns_types_matching_module(self):
        result = OperationTypeRegistry.get_for_module("ppe")
        type_ids = [op.type_id for op in result]
        assert "alpha" in type_ids

    def test_universal_star_included_for_any_module(self):
        result = OperationTypeRegistry.get_for_module("ppe")
        type_ids = [op.type_id for op in result]
        assert "beta" in type_ids

    def test_unrelated_module_excluded(self):
        result = OperationTypeRegistry.get_for_module("ppe")
        type_ids = [op.type_id for op in result]
        assert "gamma" not in type_ids

    def test_fueling_module_gets_gamma_and_beta(self):
        result = OperationTypeRegistry.get_for_module("fueling")
        type_ids = [op.type_id for op in result]
        assert "gamma" in type_ids
        assert "beta" in type_ids

    def test_unknown_module_returns_only_universal(self):
        result = OperationTypeRegistry.get_for_module("unknown-module")
        type_ids = [op.type_id for op in result]
        assert type_ids == ["beta"]

    def test_returns_list(self):
        assert isinstance(OperationTypeRegistry.get_for_module("ppe"), list)


# ---------------------------------------------------------------------------
# TestListAll — line 56
# ---------------------------------------------------------------------------

class TestListAll:
    def setup_method(self):
        self._snap = _snapshot()
        OperationTypeRegistry._types.clear()

    def teardown_method(self):
        _restore(self._snap)

    def test_empty_registry_returns_empty_list(self):
        assert OperationTypeRegistry.list_all() == []

    def test_returns_all_registered_classes(self):
        OperationTypeRegistry.register(_OpAlpha)
        OperationTypeRegistry.register(_OpBeta)
        result = OperationTypeRegistry.list_all()
        assert _OpAlpha in result
        assert _OpBeta in result

    def test_returns_list_type(self):
        OperationTypeRegistry.register(_OpAlpha)
        assert isinstance(OperationTypeRegistry.list_all(), list)

    def test_count_matches_registered(self):
        OperationTypeRegistry.register(_OpAlpha)
        OperationTypeRegistry.register(_OpBeta)
        OperationTypeRegistry.register(_OpGamma)
        assert len(OperationTypeRegistry.list_all()) == 3


# ---------------------------------------------------------------------------
# TestToCatalog — line 65
# ---------------------------------------------------------------------------

class TestToCatalog:
    def setup_method(self):
        self._snap = _snapshot()
        OperationTypeRegistry._types.clear()
        OperationTypeRegistry.register(_OpAlpha)
        OperationTypeRegistry.register(_OpBeta)
        OperationTypeRegistry.register(_OpGamma)

    def teardown_method(self):
        _restore(self._snap)

    def test_returns_list_of_dicts(self):
        result = OperationTypeRegistry.to_catalog("ppe")
        assert isinstance(result, list)
        assert all(isinstance(entry, dict) for entry in result)

    def test_catalog_entry_has_expected_keys(self):
        result = OperationTypeRegistry.to_catalog("ppe")
        assert len(result) > 0
        entry = result[0]
        assert "type_id" in entry
        assert "type_label" in entry
        assert "description" in entry
        assert "available_modules" in entry

    def test_catalog_excludes_unrelated_module(self):
        result = OperationTypeRegistry.to_catalog("ppe")
        type_ids = [e["type_id"] for e in result]
        assert "gamma" not in type_ids

    def test_catalog_includes_universal_op(self):
        result = OperationTypeRegistry.to_catalog("ppe")
        type_ids = [e["type_id"] for e in result]
        assert "beta" in type_ids

    def test_catalog_entry_values_match_class_attrs(self):
        result = OperationTypeRegistry.to_catalog("quality")
        alpha_entry = next(e for e in result if e["type_id"] == "alpha")
        assert alpha_entry["type_label"] == "Alpha"
        assert alpha_entry["description"] == "Alpha op"

    def test_empty_module_returns_only_universal(self):
        result = OperationTypeRegistry.to_catalog("no-such-module")
        type_ids = [e["type_id"] for e in result]
        assert type_ids == ["beta"]
