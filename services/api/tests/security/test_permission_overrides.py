"""Security tests: permissões granulares por usuário (WS7).

Cobertura:
  - viewer sem override → 403 em endpoint gated (retention PUT)
  - viewer com claim perms concedendo → passa o gate (≠403)
  - token antigo (sem claim perms) → fallback por role, sem lockout
  - GET /api/v1/permissions/mine acessível a qualquer role
  - GET /api/v1/admin/permissions/registry: superadmin-only, ≥30 chaves com
    label/descrição pt-BR
  - GET /api/v1/admin/permissions/matrix: shape byte-compatível (contract)
  - Isolamento: override de usuário do tenant A não vaza para usuário do B
"""
from unittest.mock import MagicMock
from uuid import uuid4

from flask_jwt_extended import create_access_token

from app.core.permissions import permissions_for_role
from app.domain.services.permission_service import PermissionService

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"


def _auth_header(app, role: str, perms: list[str] | None = None,
                 tenant_id: str = TENANT_A) -> dict[str, str]:
    claims = {
        "tenant_id": tenant_id,
        "tenant_schema": "tenant_test",
        "role": role,
    }
    if perms is not None:
        claims["perms"] = perms
    with app.app_context():
        token = create_access_token(identity=str(uuid4()), additional_claims=claims)
    return {"Authorization": f"Bearer {token}"}


# ── Gate granular: retention PUT (convertido p/ retention:write) ─────────────


class TestGranularGateRetention:
    def test_viewer_without_override_403(self, client, app):
        resp = client.put(
            "/api/v1/tenant/retention",
            json={"default_retention_days": 7},
            headers=_auth_header(app, "viewer", perms=permissions_for_role("viewer")),
        )
        assert resp.status_code == 403

    def test_viewer_with_grant_passes_gate(self, client, app):
        perms = permissions_for_role("viewer") + ["retention:write"]
        resp = client.put(
            "/api/v1/tenant/retention",
            json={"default_retention_days": 7},
            headers=_auth_header(app, "viewer", perms=perms),
        )
        # Sem DB no ambiente de teste o endpoint pode falhar depois do gate,
        # mas NUNCA com 403 — o gate concedeu.
        assert resp.status_code != 403

    def test_admin_with_deny_claim_403(self, client, app):
        # Deny override refletido na claim: admin perde retention:write
        perms = [p for p in permissions_for_role("admin") if p != "retention:write"]
        resp = client.put(
            "/api/v1/tenant/retention",
            json={"default_retention_days": 7},
            headers=_auth_header(app, "admin", perms=perms),
        )
        assert resp.status_code == 403

    def test_legacy_token_admin_passes_gate(self, client, app):
        # Token antigo sem claim perms → fallback por role (zero lockout)
        resp = client.put(
            "/api/v1/tenant/retention",
            json={"default_retention_days": 7},
            headers=_auth_header(app, "admin", perms=None),
        )
        assert resp.status_code != 403

    def test_legacy_token_viewer_still_403(self, client, app):
        resp = client.put(
            "/api/v1/tenant/retention",
            json={"default_retention_days": 7},
            headers=_auth_header(app, "viewer", perms=None),
        )
        assert resp.status_code == 403


# ── /permissions/mine — qualquer role ────────────────────────────────────────


class TestMinePermissions:
    def test_viewer_200_with_role_fallback(self, client, app):
        resp = client.get(
            "/api/v1/permissions/mine",
            headers=_auth_header(app, "viewer"),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["role"] == "viewer"
        assert data["permissions"] == permissions_for_role("viewer")

    def test_analyst_200(self, client, app):
        resp = client.get(
            "/api/v1/permissions/mine",
            headers=_auth_header(app, "analyst"),
        )
        assert resp.status_code == 200

    def test_operator_200(self, client, app):
        resp = client.get(
            "/api/v1/permissions/mine",
            headers=_auth_header(app, "operator"),
        )
        assert resp.status_code == 200

    def test_no_token_401(self, client):
        resp = client.get("/api/v1/permissions/mine")
        assert resp.status_code == 401


# ── Registry endpoint — superadmin only ──────────────────────────────────────


class TestRegistryEndpoint:
    def test_superadmin_gets_registry(self, client, app):
        resp = client.get(
            "/api/v1/admin/permissions/registry",
            headers=_auth_header(app, "superadmin"),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        perms = data["permissions"]
        assert len(perms) >= 30
        for item in perms:
            assert item["key"]
            assert item["label"].strip()
            assert item["description"].strip()
            assert item["group"].strip()
            assert isinstance(item["default_roles"], list) and item["default_roles"]

    def test_admin_403(self, client, app):
        resp = client.get(
            "/api/v1/admin/permissions/registry",
            headers=_auth_header(app, "admin"),
        )
        assert resp.status_code == 403

    def test_analyst_403(self, client, app):
        resp = client.get(
            "/api/v1/admin/permissions/registry",
            headers=_auth_header(app, "analyst"),
        )
        assert resp.status_code == 403


# ── Matrix — contract test (shape inalterada pós-derivação) ──────────────────


class TestMatrixContract:
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

    def test_matrix_shape_unchanged(self, client, app):
        resp = client.get(
            "/api/v1/admin/permissions/matrix",
            headers=_auth_header(app, "superadmin"),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["matrix"] == self._LEGACY_LITERAL

    def test_matrix_still_superadmin_only(self, client, app):
        resp = client.get(
            "/api/v1/admin/permissions/matrix",
            headers=_auth_header(app, "admin"),
        )
        assert resp.status_code == 403


# ── Endpoints de override — gate superadmin ──────────────────────────────────


class TestUserPermissionEndpointsGate:
    def test_get_user_permissions_admin_403(self, client, app):
        resp = client.get(
            f"/api/v1/admin/users/{uuid4()}/permissions",
            headers=_auth_header(app, "admin"),
        )
        assert resp.status_code == 403

    def test_put_user_permissions_operator_403(self, client, app):
        resp = client.put(
            f"/api/v1/admin/users/{uuid4()}/permissions",
            json={"overrides": [{"permission_key": "training:read", "allow": True}]},
            headers=_auth_header(app, "operator"),
        )
        assert resp.status_code == 403


# ── Isolamento multi-tenant dos overrides ────────────────────────────────────


class _FakeOverrideRepo:
    """Armazena overrides por user_id — como a tabela real (índice por user)."""

    def __init__(self) -> None:
        self._rows: dict[str, list[dict]] = {}

    def add(self, user_id: str, tenant_id: str, key: str, allow: bool) -> None:
        self._rows.setdefault(user_id, []).append({
            "user_id": user_id, "tenant_id": tenant_id,
            "permission_key": key, "allow": allow,
        })

    def list_by_user(self, user_id: str) -> list[dict]:
        return list(self._rows.get(user_id, []))


class TestOverrideTenantIsolation:
    def test_override_of_tenant_a_user_does_not_leak_to_tenant_b_user(self):
        user_a = str(uuid4())
        user_b = str(uuid4())
        repo = _FakeOverrideRepo()
        repo.add(user_a, TENANT_A, "retention:write", allow=True)

        svc = PermissionService(repo, MagicMock())  # type: ignore[arg-type]

        effective_a = svc.resolve_effective(
            {"id": user_a, "role": "viewer", "tenant_id": TENANT_A}
        )
        effective_b = svc.resolve_effective(
            {"id": user_b, "role": "viewer", "tenant_id": TENANT_B}
        )

        assert "retention:write" in effective_a
        assert "retention:write" not in effective_b
        assert effective_b == permissions_for_role("viewer")
