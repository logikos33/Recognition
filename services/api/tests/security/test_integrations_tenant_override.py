"""Security tests: override ?tenant_id= nas integrações (WS6).

Cobertura:
  - superadmin com ?tenant_id=X opera a integração do tenant X (list/upsert/
    test/delete) — capacidade nova (falhava antes do _resolve_tenant_id)
  - sem query param → tenant do JWT (regressão do fix f6df666 protegida)
  - admin/roles menores → 403 em todos os endpoints (gate preservado)
  - audit_log registra o tenant ALVO, não o do JWT
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

_POOL_PATH = "app.api.v1.admin.integration_routes.DatabasePool"
_SVC_PATH = "app.api.v1.admin.integration_routes.IntegrationService"
_REPO_PATH = "app.api.v1.admin.integration_routes.IntegrationRepository"

JWT_TENANT = "11111111-1111-1111-1111-111111111111"
TARGET_TENANT = "22222222-2222-2222-2222-222222222222"


def _auth_header(app, role: str = "superadmin") -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": JWT_TENANT,
                "tenant_schema": "admin",
                "email": f"{role}@test.dev",
                "role": role,
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_service():
    svc = MagicMock()
    svc.list_integrations.return_value = []
    svc.save_integration.return_value = {"id": str(uuid4()), "integration_type": "r2"}
    svc.test_r2_connection.return_value = {"ok": True, "error": None}
    return svc


# ── Gate por role (regressão f6df666) ────────────────────────────────────────


class TestIntegrationsGate:
    def test_admin_403_list(self, client, app):
        resp = client.get(
            "/api/v1/admin/integrations/", headers=_auth_header(app, "admin")
        )
        assert resp.status_code == 403

    def test_admin_403_upsert_with_override(self, client, app):
        # admin não alcança o endpoint mesmo tentando o override
        resp = client.put(
            f"/api/v1/admin/integrations/r2?tenant_id={TARGET_TENANT}",
            json={"config": {"bucket": "x"}},
            headers=_auth_header(app, "admin"),
        )
        assert resp.status_code == 403

    def test_operator_403(self, client, app):
        resp = client.get(
            "/api/v1/admin/integrations/", headers=_auth_header(app, "operator")
        )
        assert resp.status_code == 403


# ── Override ?tenant_id= (WS6) ────────────────────────────────────────────────


class TestIntegrationsTenantOverride:
    def test_upsert_with_override_targets_tenant(self, client, app):
        svc = _mock_service()
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.put(
                f"/api/v1/admin/integrations/r2?tenant_id={TARGET_TENANT}",
                json={"config": {"bucket": "cliente"}, "secret": "s3cr3t"},
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        assert svc.save_integration.call_args.kwargs["tenant_id"] == TARGET_TENANT
        # Audit registra o tenant ALVO
        assert svc.audit_log.call_args.kwargs["tenant_id"] == TARGET_TENANT

    def test_upsert_without_override_uses_jwt_tenant(self, client, app):
        # Regressão do fix f6df666: sem query param, tenant do JWT
        svc = _mock_service()
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.put(
                "/api/v1/admin/integrations/r2",
                json={"config": {"bucket": "logikos"}},
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        assert svc.save_integration.call_args.kwargs["tenant_id"] == JWT_TENANT

    def test_list_with_override(self, client, app):
        svc = _mock_service()
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.get(
                f"/api/v1/admin/integrations/?tenant_id={TARGET_TENANT}",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        svc.list_integrations.assert_called_once_with(TARGET_TENANT)

    def test_list_without_override(self, client, app):
        svc = _mock_service()
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.get(
                "/api/v1/admin/integrations/", headers=_auth_header(app)
            )
        assert resp.status_code == 200
        svc.list_integrations.assert_called_once_with(JWT_TENANT)

    def test_test_connection_with_override(self, client, app):
        svc = _mock_service()
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.post(
                f"/api/v1/admin/integrations/r2/test?tenant_id={TARGET_TENANT}",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        svc.test_r2_connection.assert_called_once_with(TARGET_TENANT)

    def test_delete_with_override(self, client, app):
        svc = _mock_service()
        repo = MagicMock()
        repo.delete_integration.return_value = 1
        with (
            patch(_POOL_PATH),
            patch(_SVC_PATH, return_value=svc),
            patch(_REPO_PATH, return_value=repo),
        ):
            resp = client.delete(
                f"/api/v1/admin/integrations/r2?tenant_id={TARGET_TENANT}",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        repo.delete_integration.assert_called_once_with(TARGET_TENANT, "r2")
