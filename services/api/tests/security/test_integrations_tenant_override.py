"""Security tests: override ?tenant_id= nas integrações (WS6).

Cobertura:
  - superadmin com ?tenant_id=X opera a integração do tenant X (list/upsert/
    test/delete) — capacidade nova (falhava antes do _resolve_tenant_id)
  - sem query param → tenant do JWT (regressão do fix f6df666 protegida)
  - admin/roles menores → 403 em todos os endpoints (gate preservado)
  - audit_log registra o tenant ALVO, não o do JWT

  task-058 (BYO-DB, WS6.1) — admin do tenant e o tipo escopado `byo_db`:
  - admin gerencia `byo_db` do PRÓPRIO tenant (upsert/test/delete) — sucesso
  - admin tenta gerenciar `byo_db` de OUTRO tenant via ?tenant_id= — 403
    explícito (nunca cai silenciosamente para o próprio tenant)
  - admin continua tomando 403 para r2/vast_ai/generic_gpu/notification —
    tipos de PLATAFORMA não afrouxados por essa mudança
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

_POOL_PATH = "app.api.v1.admin.integration_routes.DatabasePool"
_SVC_PATH = "app.api.v1.admin.integration_routes.IntegrationService"
_REPO_PATH = "app.api.v1.admin.integration_routes.IntegrationRepository"

JWT_TENANT = "11111111-1111-1111-1111-111111111111"
TARGET_TENANT = "22222222-2222-2222-2222-222222222222"

ADMIN_JWT_TENANT = "33333333-3333-3333-3333-333333333333"
OTHER_TENANT = "44444444-4444-4444-4444-444444444444"


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


def _admin_auth_header(app, tenant_id: str = ADMIN_JWT_TENANT) -> dict[str, str]:
    """JWT de um admin de tenant (não superadmin) — usado nos testes de byo_db."""
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": tenant_id,
                "tenant_schema": "tenant_test",
                "email": "admin@test.dev",
                "role": "admin",
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_service():
    svc = MagicMock()
    svc.list_integrations.return_value = []
    svc.save_integration.return_value = {"id": str(uuid4()), "integration_type": "r2"}
    svc.test_r2_connection.return_value = {"ok": True, "error": None}
    svc.test_generic_connection.return_value = {"ok": True, "error": None}
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


# ── BYO-DB — admin do tenant (task-058, GAP 2) ────────────────────────────────


class TestByoDbAdminOwnTenant:
    """Admin do tenant gerencia `byo_db` do PRÓPRIO tenant — sucesso."""

    def test_admin_upsert_own_tenant_byo_db_succeeds(self, client, app):
        svc = _mock_service()
        svc.save_integration.return_value = {"id": str(uuid4()), "integration_type": "byo_db"}
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.put(
                "/api/v1/admin/integrations/byo_db",
                json={
                    "config": {"host": "db.cliente.com", "database": "recognition"},
                    "secret": "s3cr3t",
                },
                headers=_admin_auth_header(app),
            )
        assert resp.status_code == 200
        assert svc.save_integration.call_args.kwargs["tenant_id"] == ADMIN_JWT_TENANT
        # Audit registra o role real do ator — não mais "superadmin" hardcoded
        assert svc.audit_log.call_args.kwargs["actor_role"] == "admin"
        assert svc.audit_log.call_args.kwargs["tenant_id"] == ADMIN_JWT_TENANT

    def test_admin_upsert_own_tenant_via_matching_override_succeeds(self, client, app):
        """?tenant_id= igual ao do próprio JWT é redundante, mas não deve
        ser bloqueado — só o override para tenant DIFERENTE é rejeitado."""
        svc = _mock_service()
        svc.save_integration.return_value = {"id": str(uuid4()), "integration_type": "byo_db"}
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.put(
                f"/api/v1/admin/integrations/byo_db?tenant_id={ADMIN_JWT_TENANT}",
                json={"config": {"host": "db.cliente.com"}},
                headers=_admin_auth_header(app),
            )
        assert resp.status_code == 200
        assert svc.save_integration.call_args.kwargs["tenant_id"] == ADMIN_JWT_TENANT

    def test_admin_test_connection_own_tenant_byo_db_succeeds(self, client, app):
        svc = _mock_service()
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.post(
                "/api/v1/admin/integrations/byo_db/test",
                headers=_admin_auth_header(app),
            )
        assert resp.status_code == 200
        svc.test_generic_connection.assert_called_once_with(ADMIN_JWT_TENANT, "byo_db")

    def test_admin_delete_own_tenant_byo_db_succeeds(self, client, app):
        svc = _mock_service()
        repo = MagicMock()
        repo.delete_integration.return_value = 1
        with (
            patch(_POOL_PATH),
            patch(_SVC_PATH, return_value=svc),
            patch(_REPO_PATH, return_value=repo),
        ):
            resp = client.delete(
                "/api/v1/admin/integrations/byo_db",
                headers=_admin_auth_header(app),
            )
        assert resp.status_code == 200
        repo.delete_integration.assert_called_once_with(ADMIN_JWT_TENANT, "byo_db")


class TestByoDbAdminCrossTenantBlocked:
    """Admin tenta gerenciar `byo_db` de OUTRO tenant via override — 403.

    Este é o ponto mais sensível do fix: o override nunca deve cair
    silenciosamente para o tenant do JWT (o que mascararia a tentativa como
    um "sucesso no tenant errado") nem, pior, operar de fato no tenant
    informado — a request precisa ser rejeitada de forma explícita.
    """

    def test_admin_upsert_other_tenant_byo_db_via_override_403(self, client, app):
        svc = _mock_service()
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.put(
                f"/api/v1/admin/integrations/byo_db?tenant_id={OTHER_TENANT}",
                json={"config": {"host": "db.outro-cliente.com"}},
                headers=_admin_auth_header(app),
            )
        assert resp.status_code == 403
        svc.save_integration.assert_not_called()

    def test_admin_test_other_tenant_byo_db_via_override_403(self, client, app):
        svc = _mock_service()
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.post(
                f"/api/v1/admin/integrations/byo_db/test?tenant_id={OTHER_TENANT}",
                headers=_admin_auth_header(app),
            )
        assert resp.status_code == 403
        svc.test_generic_connection.assert_not_called()

    def test_admin_delete_other_tenant_byo_db_via_override_403(self, client, app):
        svc = _mock_service()
        repo = MagicMock()
        with (
            patch(_POOL_PATH),
            patch(_SVC_PATH, return_value=svc),
            patch(_REPO_PATH, return_value=repo),
        ):
            resp = client.delete(
                f"/api/v1/admin/integrations/byo_db?tenant_id={OTHER_TENANT}",
                headers=_admin_auth_header(app),
            )
        assert resp.status_code == 403
        repo.delete_integration.assert_not_called()


class TestByoDbAdminPlatformTypesStillBlocked:
    """Admin ainda toma 403 pra r2/vast_ai/generic_gpu/notification —
    comportamento antigo preservado, tipos de PLATAFORMA não afrouxados."""

    @pytest.mark.parametrize(
        "integration_type", ["r2", "vast_ai", "generic_gpu", "notification"]
    )
    def test_admin_upsert_platform_type_403(self, client, app, integration_type):
        svc = _mock_service()
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.put(
                f"/api/v1/admin/integrations/{integration_type}",
                json={"config": {}},
                headers=_admin_auth_header(app),
            )
        assert resp.status_code == 403
        svc.save_integration.assert_not_called()

    @pytest.mark.parametrize(
        "integration_type", ["r2", "vast_ai", "generic_gpu", "notification"]
    )
    def test_admin_upsert_platform_type_via_own_tenant_override_still_403(
        self, client, app, integration_type
    ):
        """Mesmo passando o PRÓPRIO tenant no override, tipos de plataforma
        continuam bloqueados pra admin — só `byo_db` é escopado ao tenant."""
        svc = _mock_service()
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.put(
                f"/api/v1/admin/integrations/{integration_type}?tenant_id={ADMIN_JWT_TENANT}",
                json={"config": {}},
                headers=_admin_auth_header(app),
            )
        assert resp.status_code == 403

    @pytest.mark.parametrize(
        "integration_type", ["r2", "vast_ai", "generic_gpu", "notification"]
    )
    def test_admin_test_platform_type_403(self, client, app, integration_type):
        svc = _mock_service()
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.post(
                f"/api/v1/admin/integrations/{integration_type}/test",
                headers=_admin_auth_header(app),
            )
        assert resp.status_code == 403

    @pytest.mark.parametrize(
        "integration_type", ["r2", "vast_ai", "generic_gpu", "notification"]
    )
    def test_admin_delete_platform_type_403(self, client, app, integration_type):
        svc = _mock_service()
        repo = MagicMock()
        with (
            patch(_POOL_PATH),
            patch(_SVC_PATH, return_value=svc),
            patch(_REPO_PATH, return_value=repo),
        ):
            resp = client.delete(
                f"/api/v1/admin/integrations/{integration_type}",
                headers=_admin_auth_header(app),
            )
        assert resp.status_code == 403
        repo.delete_integration.assert_not_called()

    def test_admin_list_still_403(self, client, app):
        """Endpoint de listagem continua superadmin-only — inalterado."""
        resp = client.get(
            "/api/v1/admin/integrations/", headers=_admin_auth_header(app)
        )
        assert resp.status_code == 403


class TestByoDbSuperadminUnaffected:
    """Superadmin continua podendo gerenciar `byo_db` de qualquer tenant via
    override — comportamento idêntico ao dos outros tipos, sem regressão."""

    def test_superadmin_upsert_byo_db_any_tenant_via_override(self, client, app):
        svc = _mock_service()
        svc.save_integration.return_value = {"id": str(uuid4()), "integration_type": "byo_db"}
        with patch(_POOL_PATH), patch(_SVC_PATH, return_value=svc):
            resp = client.put(
                f"/api/v1/admin/integrations/byo_db?tenant_id={TARGET_TENANT}",
                json={"config": {"host": "db.cliente.com"}, "secret": "s3cr3t"},
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        assert svc.save_integration.call_args.kwargs["tenant_id"] == TARGET_TENANT
        assert svc.audit_log.call_args.kwargs["actor_role"] == "superadmin"
