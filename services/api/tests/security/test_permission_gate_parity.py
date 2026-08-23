"""Security tests: paridade dos gates convertidos p/ require_permission v2 (WS7).

Para cada gate inline convertido, o MESMO role-set aceita/nega igual antes e
depois da conversão (tokens sem claim 'perms' → fallback por role). Além
disso, a claim granular passa a valer (viewer com grant passa o gate).

Também cobre os 2 fixes P1/P2 (falha-antes/passa-depois):
  - _is_admin (cameras/helpers.py) excluía superadmin
  - module gate (cameras/module_handler.py) fail-open com claim modules vazia
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

TENANT = "11111111-1111-1111-1111-111111111111"


def _auth_header(app, role: str, perms: list[str] | None = None) -> dict[str, str]:
    claims = {
        "tenant_id": TENANT,
        "tenant_schema": "tenant_test",
        "role": role,
    }
    if perms is not None:
        claims["perms"] = perms
    with app.app_context():
        token = create_access_token(identity=str(uuid4()), additional_claims=claims)
    return {"Authorization": f"Bearer {token}"}


# ── Fix P1: _is_admin exclui superadmin (cameras/helpers.py:28) ──────────────


class TestIsAdminSuperadminFix:
    def _call(self, role: str) -> bool:
        from app.api.v1.cameras import helpers

        with patch.object(helpers, "DatabasePool") as pool_cls, \
             patch.object(helpers, "UserRepository") as repo_cls:
            pool_cls.get_instance.return_value = MagicMock()
            repo_cls.return_value.get_by_id.return_value = {"role": role}
            return helpers._is_admin(str(uuid4()))

    def test_superadmin_has_admin_override(self):
        # FALHA-ANTES: role == 'admin' excluía superadmin do override
        assert self._call("superadmin") is True

    def test_tenant_admin_has_no_global_override(self):
        # C-01: 'admin' é admin DE TENANT — escopo é get_tenant_id(), não global
        # (ver tests/security/test_camera_admin_tenant_scope.py)
        assert self._call("admin") is False

    def test_operator_has_no_override(self):
        assert self._call("operator") is False

    def test_viewer_has_no_override(self):
        assert self._call("viewer") is False

    def test_user_not_found_is_false(self):
        from app.api.v1.cameras import helpers

        with patch.object(helpers, "DatabasePool") as pool_cls, \
             patch.object(helpers, "UserRepository") as repo_cls:
            pool_cls.get_instance.return_value = MagicMock()
            repo_cls.return_value.get_by_id.return_value = None
            assert helpers._is_admin(str(uuid4())) is False


# ── Fix P2: module gate fail-open com claim modules vazia ────────────────────


class TestModuleGateFailClosed:
    def _allowed(self, module: str, claims: dict, db_modules=None) -> bool:
        from app.api.v1.cameras import module_handler

        with patch("flask_jwt_extended.get_jwt", return_value=claims), \
             patch.object(
                 module_handler, "_fetch_tenant_modules",
                 return_value=db_modules if db_modules is not None else [],
             ):
            return module_handler._is_module_allowed(module)

    def test_empty_claim_denies_module(self):
        # FALHA-ANTES: claim presente e vazia deixava passar qualquer módulo
        assert self._allowed("epi", {"modules": []}) is False

    def test_none_module_always_allowed(self):
        assert self._allowed("none", {"modules": []}) is True

    def test_module_in_claim_allowed(self):
        assert self._allowed("epi", {"modules": ["epi"]}) is True

    def test_module_not_in_claim_denied(self):
        assert self._allowed("counting", {"modules": ["epi"]}) is False

    def test_absent_claim_falls_back_to_db(self):
        # Token antigo sem claim modules → consulta tenants.modules_enabled
        assert self._allowed("epi", {}, db_modules=["epi"]) is True

    def test_absent_claim_db_empty_denies(self):
        assert self._allowed("epi", {}, db_modules=[]) is False


# ── Paridade: retention tenant (retention/routes.py → retention:write) ───────


class TestRetentionRoutesParity:
    URL = "/api/v1/tenant/retention"

    def test_viewer_403(self, client, app):
        resp = client.put(self.URL, json={"default_retention_days": 7},
                          headers=_auth_header(app, "viewer"))
        assert resp.status_code == 403

    def test_operator_403(self, client, app):
        resp = client.put(self.URL, json={"default_retention_days": 7},
                          headers=_auth_header(app, "operator"))
        assert resp.status_code == 403

    def test_admin_passes_gate(self, client, app):
        resp = client.put(self.URL, json={"default_retention_days": 7},
                          headers=_auth_header(app, "admin"))
        assert resp.status_code != 403

    def test_superadmin_passes_gate(self, client, app):
        resp = client.put(self.URL, json={"default_retention_days": 7},
                          headers=_auth_header(app, "superadmin"))
        assert resp.status_code != 403


# ── Paridade: notificações (notifications/routes.py → notifications:manage) ──


class TestNotificationsGateParity:
    URL = "/api/v1/notifications/channels"

    def test_viewer_403(self, client, app):
        resp = client.post(self.URL, json={"type": "email"},
                           headers=_auth_header(app, "viewer"))
        assert resp.status_code == 403

    def test_analyst_403(self, client, app):
        resp = client.post(self.URL, json={"type": "email"},
                           headers=_auth_header(app, "analyst"))
        assert resp.status_code == 403

    def test_admin_passes_gate(self, client, app):
        # Body inválido → 422 DEPOIS do gate (paridade sem DB)
        resp = client.post(self.URL, json={"type": "bogus"},
                           headers=_auth_header(app, "admin"))
        assert resp.status_code == 422

    def test_granular_grant_passes_gate(self, client, app):
        resp = client.post(
            self.URL, json={"type": "bogus"},
            headers=_auth_header(app, "viewer", perms=["notifications:manage"]),
        )
        assert resp.status_code == 422  # passou o gate; barrou na validação


# ── Paridade: devices claim-codes (devices/routes.py → devices:manage) ───────


class TestDevicesGateParity:
    URL = "/api/devices/claim-codes"

    def test_viewer_403(self, client, app):
        resp = client.post(self.URL, json={}, headers=_auth_header(app, "viewer"))
        assert resp.status_code == 403

    def test_operator_403(self, client, app):
        resp = client.post(self.URL, json={}, headers=_auth_header(app, "operator"))
        assert resp.status_code == 403

    def test_admin_passes_gate(self, client, app):
        resp = client.post(self.URL, json={}, headers=_auth_header(app, "admin"))
        assert resp.status_code != 403


# ── Paridade: site gateways (site_gateways/routes.py → gateways:manage) ──────


class TestSiteGatewaysGateParity:
    URL = f"/api/v1/site-gateways/{uuid4()}"

    def test_operator_403(self, client, app):
        resp = client.put(self.URL, json={"kind": "mikrotik"},
                          headers=_auth_header(app, "operator"))
        assert resp.status_code == 403

    def test_admin_passes_gate(self, client, app):
        resp = client.put(self.URL, json={"kind": "bogus"},
                          headers=_auth_header(app, "admin"))
        assert resp.status_code == 422  # gate passou; validação barrou


# ── Paridade: edge (edge/routes.py → edge:manage, 13 endpoints) ──────────────


class TestEdgeGateParity:
    URL = "/api/v1/edge/sites"

    def test_viewer_403(self, client, app):
        resp = client.get(self.URL, headers=_auth_header(app, "viewer"))
        assert resp.status_code == 403

    def test_trainer_403(self, client, app):
        resp = client.get(self.URL, headers=_auth_header(app, "trainer"))
        assert resp.status_code == 403

    def test_admin_passes_gate(self, client, app):
        resp = client.get(self.URL, headers=_auth_header(app, "admin"))
        assert resp.status_code != 403

    def test_granular_grant_passes_gate(self, client, app):
        resp = client.get(
            self.URL, headers=_auth_header(app, "viewer", perms=["edge:manage"]),
        )
        assert resp.status_code != 403

    def test_granular_deny_blocks_admin(self, client, app):
        resp = client.get(self.URL, headers=_auth_header(app, "admin", perms=[]))
        assert resp.status_code == 403


# ── Paridade: probe (cameras/probe_handler.py → cameras:test) ────────────────


class TestProbeGateParity:
    URL = "/api/cameras/probe"

    def test_viewer_403(self, client, app):
        resp = client.post(self.URL, json={}, headers=_auth_header(app, "viewer"))
        assert resp.status_code == 403

    def test_analyst_403(self, client, app):
        resp = client.post(self.URL, json={}, headers=_auth_header(app, "analyst"))
        assert resp.status_code == 403

    def test_operator_passes_gate(self, client, app):
        # operator faz parte do role-set original (admin, operator, superadmin)
        resp = client.post(self.URL, json={}, headers=_auth_header(app, "operator"))
        assert resp.status_code == 422  # gate passou; ip_or_host obrigatório

    def test_admin_passes_gate(self, client, app):
        resp = client.post(self.URL, json={}, headers=_auth_header(app, "admin"))
        assert resp.status_code == 422


# ── Paridade: retenção por câmera e por tenant (cameras/*retention_handler) ──


class TestCameraRetentionGateParity:
    def test_viewer_403_camera(self, client, app):
        resp = client.put(f"/api/cameras/{uuid4()}/retention",
                          json={"retention_days": 7},
                          headers=_auth_header(app, "viewer"))
        assert resp.status_code == 403

    def test_admin_passes_gate_camera(self, client, app):
        # Tier inválido → 422 DEPOIS do gate
        resp = client.put(f"/api/cameras/{uuid4()}/retention",
                          json={"retention_days": 5},
                          headers=_auth_header(app, "admin"))
        assert resp.status_code == 422

    def test_viewer_403_tenant(self, client, app):
        resp = client.put("/api/cameras/tenant/retention",
                          json={"retention_days": 7},
                          headers=_auth_header(app, "viewer"))
        assert resp.status_code == 403

    def test_admin_passes_gate_tenant(self, client, app):
        resp = client.put("/api/cameras/tenant/retention",
                          json={"retention_days": 5},
                          headers=_auth_header(app, "admin"))
        assert resp.status_code == 400  # tier inválido — validação após o gate
