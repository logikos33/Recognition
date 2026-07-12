"""Tests: PermissionService.resolve_effective (WS7, unit — repos mockados).

Cobertura exigida pelo plano:
  - role base
  - custom_role soma permissões
  - override allow concede a viewer
  - override deny remove de operator
  - superadmin imune a deny
  - chave inválida rejeitada/ignorada
"""
from unittest.mock import MagicMock

from app.core.permissions import all_permission_keys, permissions_for_role
from app.domain.services.permission_service import PermissionService

USER_ID = "11111111-1111-1111-1111-111111111111"
TENANT_ID = "22222222-2222-2222-2222-222222222222"
ROLE_ID = "33333333-3333-3333-3333-333333333333"


def _service(overrides=None, custom_role=None) -> PermissionService:
    override_repo = MagicMock()
    override_repo.list_by_user.return_value = overrides or []
    custom_role_repo = MagicMock()
    custom_role_repo.get_by_id.return_value = custom_role
    return PermissionService(override_repo, custom_role_repo)


def _user(role: str, custom_role_id: str | None = None) -> dict:
    return {
        "id": USER_ID,
        "role": role,
        "tenant_id": TENANT_ID,
        "custom_role_id": custom_role_id,
    }


class TestRoleBase:
    def test_viewer_gets_only_role_defaults(self):
        effective = _service().resolve_effective(_user("viewer"))
        assert effective == permissions_for_role("viewer")

    def test_admin_gets_role_defaults(self):
        effective = _service().resolve_effective(_user("admin"))
        assert "retention:write" in effective
        assert "admin:panel" not in effective


class TestCustomRole:
    def test_custom_role_adds_permissions(self):
        svc = _service(custom_role={
            "id": ROLE_ID, "tenant_id": TENANT_ID, "name": "Treinador",
            "permissions": {"training:read": True, "training:write": False},
        })
        effective = svc.resolve_effective(_user("viewer", custom_role_id=ROLE_ID))
        assert "training:read" in effective
        assert "training:write" not in effective  # false não concede

    def test_custom_role_permissions_as_json_string(self):
        svc = _service(custom_role={
            "id": ROLE_ID, "tenant_id": TENANT_ID, "name": "X",
            "permissions": '{"alerts:export": true}',
        })
        effective = svc.resolve_effective(_user("viewer", custom_role_id=ROLE_ID))
        assert "alerts:export" in effective

    def test_custom_role_invalid_keys_ignored(self):
        svc = _service(custom_role={
            "id": ROLE_ID, "tenant_id": TENANT_ID, "name": "X",
            "permissions": {"hacky:permission": True, "training:read": True},
        })
        effective = svc.resolve_effective(_user("viewer", custom_role_id=ROLE_ID))
        assert "hacky:permission" not in effective
        assert "training:read" in effective


class TestOverrides:
    def test_allow_override_grants_to_viewer(self):
        svc = _service(overrides=[
            {"permission_key": "retention:write", "allow": True},
        ])
        effective = svc.resolve_effective(_user("viewer"))
        assert "retention:write" in effective

    def test_deny_override_removes_from_operator(self):
        assert "cameras:control" in permissions_for_role("operator")
        svc = _service(overrides=[
            {"permission_key": "cameras:control", "allow": False},
        ])
        effective = svc.resolve_effective(_user("operator"))
        assert "cameras:control" not in effective

    def test_deny_wins_over_custom_role_grant(self):
        svc = _service(
            overrides=[{"permission_key": "training:read", "allow": False}],
            custom_role={
                "id": ROLE_ID, "tenant_id": TENANT_ID, "name": "X",
                "permissions": {"training:read": True},
            },
        )
        effective = svc.resolve_effective(_user("viewer", custom_role_id=ROLE_ID))
        assert "training:read" not in effective

    def test_legacy_alias_in_override_normalized(self):
        svc = _service(overrides=[
            {"permission_key": "view_audit_log", "allow": True},
        ])
        effective = svc.resolve_effective(_user("viewer"))
        assert "audit:read" in effective

    def test_invalid_override_key_ignored(self):
        svc = _service(overrides=[
            {"permission_key": "totally:bogus", "allow": True},
        ])
        effective = svc.resolve_effective(_user("viewer"))
        assert "totally:bogus" not in effective
        assert effective == permissions_for_role("viewer")


class TestSuperadmin:
    def test_superadmin_gets_everything(self):
        effective = _service().resolve_effective(_user("superadmin"))
        assert effective == all_permission_keys()

    def test_superadmin_immune_to_deny(self):
        svc = _service(overrides=[
            {"permission_key": "admin:panel", "allow": False},
        ])
        effective = svc.resolve_effective(_user("superadmin"))
        assert "admin:panel" in effective  # anti-lockout


class TestRepoFailureGraceful:
    def test_override_repo_error_falls_back_to_role(self):
        override_repo = MagicMock()
        override_repo.list_by_user.side_effect = RuntimeError("db down")
        svc = PermissionService(override_repo, MagicMock())
        effective = svc.resolve_effective(_user("viewer"))
        assert effective == permissions_for_role("viewer")


class TestDescribe:
    def test_describe_shape(self):
        svc = _service(overrides=[
            {
                "permission_key": "retention:write", "allow": True,
                "reason": "cobertura de férias", "granted_by": USER_ID,
                "updated_at": None,
            },
        ])
        detail = svc.describe(_user("viewer"))
        assert detail["role"] == "viewer"
        assert detail["custom_role"] is None
        assert detail["overrides"][0]["permission_key"] == "retention:write"
        assert detail["overrides"][0]["allow"] is True
        assert "retention:write" in detail["effective"]
        assert detail["role_permissions"] == permissions_for_role("viewer")
