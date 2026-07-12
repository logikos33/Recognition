"""Tests: POST /api/v1/admin/users — validação de existência do tenant (WS9).

Regra da casa (falha-antes/passa-depois): antes do fix, um tenant_id
inexistente passava direto pelo seat check e só estourava (ou pior,
inseria com FK quebrada) mais adiante; agora o endpoint retorna
400 'Tenant não encontrado' antes de qualquer efeito colateral.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

SUPER_TENANT = "00000000-0000-0000-0000-000000000001"


def _auth_header(app, role: str = "superadmin") -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": SUPER_TENANT,
                "tenant_schema": "public",
                "role": role,
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_pool(tenant_exists: bool) -> MagicMock:
    """Pool fake: SELECT 1 FROM tenants retorna linha ou None."""
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = {"?column?": 1} if tenant_exists else None
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    pool.get_connection.return_value.__enter__.return_value = conn
    pool.get_connection.return_value.__exit__.return_value = False
    return pool


class TestCreateUserTenantValidation:
    """POST /users deve validar o tenant antes do seat check."""

    def test_nonexistent_tenant_returns_400(self, app, client) -> None:
        pool = _mock_pool(tenant_exists=False)
        with patch(
            "app.api.v1.admin.routes.DatabasePool.get_instance",
            return_value=pool,
        ):
            resp = client.post(
                "/api/v1/admin/users",
                json={
                    "email": "novo@teste.dev",
                    "role": "operator",
                    "tenant_id": str(uuid4()),
                },
                headers=_auth_header(app),
            )

        assert resp.status_code == 400
        body = resp.get_json()
        assert body["success"] is False
        assert body["error"] == "Tenant não encontrado"

    def test_malformed_tenant_uuid_returns_400(self, app, client) -> None:
        pool = _mock_pool(tenant_exists=False)
        with patch(
            "app.api.v1.admin.routes.DatabasePool.get_instance",
            return_value=pool,
        ):
            resp = client.post(
                "/api/v1/admin/users",
                json={
                    "email": "novo@teste.dev",
                    "role": "operator",
                    "tenant_id": "nao-e-um-uuid",
                },
                headers=_auth_header(app),
            )

        assert resp.status_code == 400
        assert resp.get_json()["error"] == "Tenant não encontrado"
        # UUID malformado falha ANTES de tocar o banco
        pool.get_connection.assert_not_called()

    def test_non_superadmin_gets_403(self, app, client) -> None:
        resp = client.post(
            "/api/v1/admin/users",
            json={
                "email": "novo@teste.dev",
                "role": "operator",
                "tenant_id": str(uuid4()),
            },
            headers=_auth_header(app, role="admin"),
        )
        assert resp.status_code == 403
