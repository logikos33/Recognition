"""Tests: registry canônico de permissões (WS7).

Cobertura:
  - Contract: ROLE_PERMISSIONS derivada == literal legado (shape byte-compatível)
  - Registry: ≥30 chaves, todas com label/description pt-BR não-vazios
  - normalize_key: canônica, alias legado, desconhecida
  - Paridade estática: default_roles dos gates convertidos == role-set original
"""
from app.constants import ROLE_PERMISSIONS
from app.core.permissions import (
    LEGACY_ALIASES,
    PERMISSION_REGISTRY,
    all_permission_keys,
    default_roles_for,
    legacy_role_permissions,
    normalize_key,
    permissions_for_role,
    registry_as_list,
)

# Literal EXATO da constante pré-WS7 (constants.py:100-119) — contract test.
_LEGACY_LITERAL = {
    "view_cameras":          ["superadmin", "admin", "operator", "analyst", "trainer", "viewer"],
    "control_cameras":       ["superadmin", "admin", "operator"],
    "view_alerts":           ["superadmin", "admin", "operator", "analyst", "viewer"],
    "feedback_alerts":       ["superadmin", "admin", "operator", "analyst"],
    "annotate_frames":       ["superadmin", "admin", "operator", "trainer"],
    "create_training_job":   ["superadmin", "admin", "trainer"],
    "approve_model":         ["superadmin", "admin"],
    "view_reports":          ["superadmin", "admin", "operator", "analyst", "viewer"],
    "manage_users":          ["superadmin", "admin"],
    "configure_cameras":     ["superadmin", "admin"],
    "manage_tenant":         ["superadmin"],
    "view_admin_panel":      ["superadmin"],
    "approve_training":      ["superadmin"],
    "manage_workers":        ["superadmin"],
    "manage_plans":          ["superadmin"],
    "manage_announcements":  ["superadmin"],
    "view_audit_log":        ["superadmin"],
    "manage_tickets":        ["superadmin", "admin"],
}


class TestLegacyMatrixContract:
    """GET /permissions/matrix depende de ROLE_PERMISSIONS — shape inalterada."""

    def test_derived_equals_legacy_literal(self):
        assert legacy_role_permissions() == _LEGACY_LITERAL

    def test_constants_export_equals_legacy_literal(self):
        assert ROLE_PERMISSIONS == _LEGACY_LITERAL

    def test_key_order_preserved(self):
        assert list(ROLE_PERMISSIONS.keys()) == list(_LEGACY_LITERAL.keys())


class TestRegistryContent:
    def test_at_least_30_permissions(self):
        assert len(PERMISSION_REGISTRY) >= 30

    def test_all_entries_have_label_and_description_ptbr(self):
        for key, meta in PERMISSION_REGISTRY.items():
            assert meta["label"].strip(), f"{key} sem label"
            assert meta["description"].strip(), f"{key} sem description"
            assert meta["group"].strip(), f"{key} sem group"
            assert meta["default_roles"], f"{key} sem default_roles"

    def test_all_keys_are_domain_action_format(self):
        for key in PERMISSION_REGISTRY:
            assert ":" in key, f"chave fora do formato dominio:acao: {key}"

    def test_superadmin_has_every_permission_by_default(self):
        for key, meta in PERMISSION_REGISTRY.items():
            assert "superadmin" in meta["default_roles"], key

    def test_registry_as_list_serializable(self):
        items = registry_as_list()
        assert len(items) == len(PERMISSION_REGISTRY)
        sample = items[0]
        assert set(sample.keys()) == {
            "key", "label", "description", "group", "module",
            "default_roles", "enforced",
        }


class TestNormalizeKey:
    def test_canonical_passthrough(self):
        assert normalize_key("cameras:read") == "cameras:read"

    def test_legacy_alias_resolves(self):
        assert normalize_key("view_cameras") == "cameras:read"
        assert normalize_key("manage_tickets") == "tickets:manage"

    def test_unknown_returns_none(self):
        assert normalize_key("nonexistent:perm") is None
        assert normalize_key("") is None

    def test_every_alias_targets_registry_key(self):
        for alias, canonical in LEGACY_ALIASES.items():
            assert canonical in PERMISSION_REGISTRY, f"{alias} → {canonical} inválido"


class TestGateParityStatic:
    """default_roles dos gates convertidos == role-set do check inline original."""

    def test_retention_write_matches_inline_gate(self):
        # retention/routes.py:73 e cameras/*retention_handler: (admin, superadmin)
        assert set(default_roles_for("retention:write")) == {"admin", "superadmin"}

    def test_notifications_manage_matches_inline_gate(self):
        assert set(default_roles_for("notifications:manage")) == {"admin", "superadmin"}

    def test_devices_manage_matches_inline_gate(self):
        assert set(default_roles_for("devices:manage")) == {"admin", "superadmin"}

    def test_edge_manage_matches_inline_gate(self):
        assert set(default_roles_for("edge:manage")) == {"admin", "superadmin"}

    def test_gateways_manage_matches_inline_gate(self):
        assert set(default_roles_for("gateways:manage")) == {"admin", "superadmin"}

    def test_cameras_test_matches_probe_gate(self):
        # cameras/probe_handler.py:187: (admin, operator, superadmin)
        assert set(default_roles_for("cameras:test")) == {
            "admin", "operator", "superadmin",
        }

    def test_modules_write_matches_toggle_class_gate(self):
        # modules/routes.py:toggle_module_class — task-073/achado #6
        assert set(default_roles_for("modules:write")) == {"admin", "superadmin"}


class TestRoleResolution:
    def test_permissions_for_viewer(self):
        perms = permissions_for_role("viewer")
        assert "cameras:read" in perms
        assert "retention:write" not in perms
        assert "admin:panel" not in perms

    def test_permissions_for_unknown_role_empty(self):
        assert permissions_for_role("nonexistent") == []

    def test_all_permission_keys_sorted(self):
        keys = all_permission_keys()
        assert keys == sorted(keys)
        assert len(keys) == len(PERMISSION_REGISTRY)
