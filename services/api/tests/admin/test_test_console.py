"""
Recognition — Tests: Admin Test Console (task-056).

Cobre:
  1. Role-gate: operador (role=operator) NÃO consegue acessar — retorna 403
  2. Role-gate: admin de tenant (role=admin) NÃO consegue acessar — retorna 403
  3. Superadmin consegue acessar status (role=superadmin) — retorna 200
  4. Start retorna 201 com session_id
  5. Stop encerra sessão em andamento
  6. Integrations list retorna 200 sem expor value_encrypted
  7. Integrations upsert cifra e não retorna o valor

Isolamento: todos os requests usam mock DB — sem SQL real.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def superadmin_headers(app):
    """JWT com role=superadmin."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "role": "superadmin",
                "tenant_id": str(uuid4()),
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_headers(app):
    """JWT com role=operator — NÃO deve acessar endpoints admin."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "role": "operator",
                "tenant_id": str(uuid4()),
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(app):
    """JWT com role=admin (admin de tenant — não superadmin)."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "role": "admin",
                "tenant_id": str(uuid4()),
            },
        )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pool_no_rows():
    """DatabasePool mock que retorna cursor vazio."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor

    pool = MagicMock()
    pool.get_connection = MagicMock()
    pool.get_connection.return_value.__enter__ = lambda s: mock_conn
    pool.get_connection.return_value.__exit__ = MagicMock(return_value=False)
    return pool


# ---------------------------------------------------------------------------
# Role-gate: status endpoint
# ---------------------------------------------------------------------------

class TestRoleGateStatus:
    """GET /api/v1/admin/test-console/status deve rejeitar roles insuficientes."""

    def test_operator_receives_403(self, client, operator_headers):
        """Operador NÃO pode acessar o console de teste."""
        res = client.get(
            "/api/v1/admin/test-console/status",
            headers=operator_headers,
        )
        assert res.status_code == 403, (
            f"Esperado 403 para role=operator, recebido {res.status_code}"
        )

    def test_admin_receives_403(self, client, admin_headers):
        """Admin de tenant (role=admin) NÃO é superadmin — deve receber 403."""
        res = client.get(
            "/api/v1/admin/test-console/status",
            headers=admin_headers,
        )
        assert res.status_code == 403, (
            f"Esperado 403 para role=admin, recebido {res.status_code}"
        )

    def test_unauthenticated_receives_401(self, client):
        """Sem JWT — deve receber 401."""
        res = client.get("/api/v1/admin/test-console/status")
        assert res.status_code == 401

    def test_superadmin_receives_200(self, client, superadmin_headers):
        """Superadmin PODE acessar — retorna 200 com status."""
        with patch(
            "app.api.v1.admin.routes_test_console._check_integration_configured",
            return_value=False,
        ):
            res = client.get(
                "/api/v1/admin/test-console/status",
                headers=superadmin_headers,
            )
        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        assert "status" in body["data"]
        assert "metrics" in body["data"]


# ---------------------------------------------------------------------------
# Role-gate: start endpoint
# ---------------------------------------------------------------------------

class TestRoleGateStart:
    """POST /api/v1/admin/test-console/start deve rejeitar roles insuficientes."""

    def test_operator_receives_403_on_start(self, client, operator_headers):
        res = client.post(
            "/api/v1/admin/test-console/start",
            json={"camera_count": 1, "model_id": "pretrained"},
            headers=operator_headers,
        )
        assert res.status_code == 403

    def test_superadmin_can_start(self, client, superadmin_headers):
        """Superadmin inicia sessão — retorna 201 com session_id."""
        # Parar qualquer sessão prévia primeiro
        with patch(
            "app.api.v1.admin.routes_test_console._console_state",
            {"status": "idle", "session_id": None, "started_at": None,
             "stopped_at": None, "config": None, "metrics": {}, "log_lines": []},
        ):
            res = client.post(
                "/api/v1/admin/test-console/start",
                json={"camera_count": 2, "model_id": "pretrained"},
                headers=superadmin_headers,
            )
        assert res.status_code == 201
        body = res.get_json()
        assert body["success"] is True
        assert "session_id" in body["data"]
        assert body["data"]["status"] == "running"

    def test_invalid_camera_count_receives_400(self, client, superadmin_headers):
        """camera_count fora do intervalo 1-28 deve retornar 400."""
        res = client.post(
            "/api/v1/admin/test-console/start",
            json={"camera_count": 99, "model_id": "pretrained"},
            headers=superadmin_headers,
        )
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# Role-gate: integrations endpoints
# ---------------------------------------------------------------------------

class TestRoleGateIntegrations:
    """Integrations endpoints — somente superadmin."""

    def test_operator_cannot_list_integrations(self, client, operator_headers):
        res = client.get(
            "/api/v1/admin/integrations",
            headers=operator_headers,
        )
        assert res.status_code == 403

    def test_operator_cannot_upsert_integration(self, client, operator_headers):
        res = client.put(
            "/api/v1/admin/integrations/vast_ai",
            json={"value": "sk-abc123", "tenant_id": str(uuid4())},
            headers=operator_headers,
        )
        assert res.status_code == 403

    def test_superadmin_can_list_integrations(self, client, superadmin_headers):
        """Superadmin lista integrações — retorna 200 (blueprint task-058)."""
        mock_svc = MagicMock()
        mock_svc.list_integrations.return_value = []
        with patch(
            "app.api.v1.admin.integration_routes._get_service",
            return_value=mock_svc,
        ):
            res = client.get(
                "/api/v1/admin/integrations",
                headers=superadmin_headers,
            )
        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        assert "integrations" in body["data"]


# ---------------------------------------------------------------------------
# Integrations: value never exposed
# ---------------------------------------------------------------------------

class TestIntegrationsSecrecy:
    """Valores de integrações NUNCA devem ser retornados na API."""

    def test_list_does_not_expose_secret_encrypted(self, client, superadmin_headers):
        """Rota GET /integrations mascara secret_encrypted mesmo se o repo o retornar."""
        from app.domain.services.integration_service import IntegrationService

        mock_repo = MagicMock()
        mock_repo.list_integrations.return_value = [
            {
                "id": str(uuid4()),
                "integration_type": "vast_ai",
                "label": "vast_ai",
                "config": {},
                "secret_encrypted": "SENSITIVE_ENCRYPTED_DATA",
                "last4": "cdef",
                "status": "ok",
                "last_tested_at": None,
                "last_error": None,
                "created_at": None,
                "updated_at": None,
            }
        ]

        with patch(
            "app.api.v1.admin.integration_routes._get_service",
            return_value=IntegrationService(mock_repo),
        ):
            res = client.get(
                "/api/v1/admin/integrations",
                headers=superadmin_headers,
            )

        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        items = body["data"]["integrations"]
        assert len(items) == 1
        for item in items:
            assert "secret_encrypted" not in item, (
                "secret_encrypted não deve ser exposto na lista de integrações"
            )
            assert "SENSITIVE_ENCRYPTED_DATA" not in str(item)


# ---------------------------------------------------------------------------
# Tenant isolation: integrations
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    """Integrações são escopadas pelo tenant do JWT — nunca pelo user id."""

    def test_upsert_scopes_by_tenant_claim_not_user_id(self, app, client):
        """tenant_id vem do claim do JWT (get_tenant_id), não do identity.

        Usar o user id como tenant_id violaria a FK tenants(id) no primeiro
        save real e quebraria o escopo multi-tenant das integrações.
        """
        from flask_jwt_extended import create_access_token

        user_id = str(uuid4())
        tenant_id = str(uuid4())
        with app.app_context():
            token = create_access_token(
                identity=user_id,
                additional_claims={"role": "superadmin", "tenant_id": tenant_id},
            )

        mock_svc = MagicMock()
        mock_svc.save_integration.return_value = {"integration_type": "vast_ai"}
        with patch(
            "app.api.v1.admin.integration_routes._get_service",
            return_value=mock_svc,
        ):
            res = client.put(
                "/api/v1/admin/integrations/vast_ai",
                json={"secret": "sk-test-key"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        _, save_kwargs = mock_svc.save_integration.call_args
        assert save_kwargs["tenant_id"] == tenant_id
        assert save_kwargs["tenant_id"] != user_id
        # audit registra o par correto: tenant do claim, user do identity
        _, audit_kwargs = mock_svc.audit_log.call_args
        assert str(audit_kwargs["tenant_id"]) == tenant_id
        assert str(audit_kwargs["user_id"]) == user_id

    def test_upsert_with_invalid_key_returns_400(self, client, superadmin_headers):
        """Key com caracteres inválidos → 400."""
        res = client.put(
            "/api/v1/admin/integrations/INVALID KEY!",
            json={"value": "sk-test-key", "tenant_id": str(uuid4())},
            headers=superadmin_headers,
        )
        assert res.status_code == 400
