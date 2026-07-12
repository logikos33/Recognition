"""Tests: POST /api/v1/admin/tenants — senha temporária aleatória (task-076, achado #4).

Regra da casa (falha-antes/passa-depois): antes do fix, `temp_password` era
derivada do slug (`f"EpiMonitor@{slug[:4].upper()}2024!"`) — previsível para
qualquer um que conhecesse o slug (público) do tenant, com ano hardcoded
`2024`. Agora deve ser gerada com `secrets.token_urlsafe`, diferente a cada
criação, sem conter o slug nem seguir o padrão antigo, e o admin do tenant
deve nascer com `force_password_reset=true` (mesma coluna já usada em
POST /users e POST /users/<id>/force-password-reset — troca obrigatória
no 1º login).
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


def _mock_pool(slug: str, tenant_id: str) -> MagicMock:
    """Pool fake: slug livre (fetchone -> None) + INSERT tenants RETURNING linha."""
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()
    tenant_row = {
        "id": tenant_id,
        "slug": slug,
        "name": "Tenant Teste",
        "plan": "standard",
        "schema_name": slug,
        "is_active": True,
    }
    cur.fetchone.side_effect = [None, tenant_row]
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    pool.get_connection.return_value.__enter__.return_value = conn
    pool.get_connection.return_value.__exit__.return_value = False
    return pool


def _create_tenant(app, client, slug: str, name: str = "Tenant Teste"):
    pool = _mock_pool(slug, str(uuid4()))
    with (
        patch("app.api.v1.admin.routes.DatabasePool.get_instance", return_value=pool),
        patch("app.api.v1.admin.routes.invalidate_schema_cache"),
        patch("app.api.v1.admin.routes.log_audit"),
    ):
        resp = client.post(
            "/api/v1/admin/tenants",
            json={"name": name, "slug": slug, "plan": "standard"},
            headers=_auth_header(app),
        )
    return resp, pool


class TestCreateTenantTempPassword:
    """POST /tenants deve gerar senha aleatória forte, não derivada do slug."""

    def test_temp_password_is_random_and_not_derived_from_slug(self, app, client) -> None:
        slug = "acme"
        resp, _ = _create_tenant(app, client, slug, name="Acme Corp")

        assert resp.status_code == 201
        body = resp.get_json()
        temp_password = body["data"]["temp_password"]

        # >=16 chars de entropia real (token_urlsafe(12) ~ 96 bits)
        assert len(temp_password) >= 16
        # não deriva do slug nem segue o padrão antigo previsível
        assert slug.upper() not in temp_password.upper()
        assert not temp_password.startswith("EpiMonitor@")
        assert not temp_password.endswith("2024!")

    def test_two_creations_produce_different_passwords(self, app, client) -> None:
        resp_a, _ = _create_tenant(app, client, "tenant-um", name="Tenant Um")
        resp_b, _ = _create_tenant(app, client, "tenant-dois", name="Tenant Dois")

        assert resp_a.status_code == 201
        assert resp_b.status_code == 201
        pwd_a = resp_a.get_json()["data"]["temp_password"]
        pwd_b = resp_b.get_json()["data"]["temp_password"]

        assert pwd_a != pwd_b

    def test_admin_user_created_with_force_password_reset_flag(self, app, client) -> None:
        slug = "beta"
        resp, pool = _create_tenant(app, client, slug, name="Beta Co")

        assert resp.status_code == 201

        conn = pool.get_connection.return_value.__enter__.return_value
        cur = conn.cursor.return_value.__enter__.return_value
        insert_user_call = next(
            call
            for call in cur.execute.call_args_list
            if "INSERT INTO users" in call.args[0]
        )
        insert_sql, insert_params = insert_user_call.args
        assert "force_password_reset" in insert_sql
        # VALUES (%s, %s, %s, 'admin', %s, true, true) — is_active e
        # force_password_reset ambos hardcoded 'true' no SQL (não são params)
        assert insert_sql.count("true") >= 2

    def test_temp_password_never_logged(self, app, client, caplog) -> None:
        slug = "gamma"
        with caplog.at_level("DEBUG"):
            resp, _ = _create_tenant(app, client, slug, name="Gamma Ltda")

        assert resp.status_code == 201
        temp_password = resp.get_json()["data"]["temp_password"]
        for record in caplog.records:
            assert temp_password not in record.getMessage()
