"""
Recognition — Tests: Quality Demo Seed Authorization (task-072 / achado #5).

Antes do fix, POST /api/v1/quality/demo/seed só exigia JWT válido + módulo
'quality' habilitado no tenant — qualquer usuário comum (role=operator)
conseguia chamar ?force=true e apagar dados reais (DELETE FROM
quality_reworks/quality_pieces/quality_stations) recriando fake por cima.

Cobre falha-antes/passa-depois do gate de admin:
  - Usuário comum do tenant (role=operator) → 403 (antes: 200 + seed executado).
  - Admin do tenant → 200 (seed normal, sem force).
  - force=true sem role superadmin (mesmo sendo admin de tenant) → 403.
  - force=true com superadmin mas sem confirmação explícita no body → 400.
  - force=true com superadmin + confirm=true → 200 (executa DELETE+INSERT).
  - Sem token → 401/422.
  - Módulo 'quality' desabilitado no tenant → 403.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


def _make_headers(app, role, modules=None):
    """JWT real com role/tenant_schema/modules como additional_claims."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "role": role,
                "tenant_schema": "tenant_test",
                "modules": modules if modules is not None else ["quality"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_headers(app):
    """JWT com role=operator (usuário comum do tenant)."""
    return _make_headers(app, "operator")


@pytest.fixture
def admin_headers(app):
    """JWT com role=admin (admin de tenant — não é superadmin)."""
    return _make_headers(app, "admin")


@pytest.fixture
def superadmin_headers(app):
    """JWT com role=superadmin."""
    return _make_headers(app, "superadmin")


def _mock_pool(existing_stations: int):
    """Pool mockado: SELECT COUNT(*) FROM quality_stations retorna `existing_stations`."""
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = (existing_stations,)
    conn.cursor.return_value = cur
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    pool.get_connection.return_value = conn
    return pool, conn, cur


_PATCH_TARGET = "app.infrastructure.database.connection.DatabasePool.get_instance"


class TestDemoSeedRoleGate:
    """Gate de role admin/superadmin no endpoint (achado #5)."""

    def test_operator_cannot_seed(self, client, operator_headers):
        """Usuário comum do tenant deve receber 403 — nunca deve tocar o banco."""
        pool, conn, cur = _mock_pool(0)
        with patch(_PATCH_TARGET, return_value=pool):
            res = client.post("/api/v1/quality/demo/seed", headers=operator_headers)

        assert res.status_code == 403, f"Esperado 403, obtido {res.status_code}"
        data = res.get_json()
        assert data["success"] is False
        pool.get_connection.assert_not_called()

    def test_admin_can_seed_without_force(self, client, admin_headers):
        """Admin de tenant consegue rodar o seed normal (sem force)."""
        pool, conn, cur = _mock_pool(0)
        with patch(_PATCH_TARGET, return_value=pool):
            res = client.post("/api/v1/quality/demo/seed", headers=admin_headers)

        assert res.status_code == 200, f"Esperado 200, obtido {res.status_code}"
        data = res.get_json()
        assert data["data"]["seeded"] is True

    def test_unauthenticated_cannot_seed(self, client):
        """Sem token JWT deve receber 401 ou 422."""
        res = client.post("/api/v1/quality/demo/seed")
        assert res.status_code in (401, 422), f"Esperado 401/422, obtido {res.status_code}"

    def test_quality_module_disabled_denied(self, client, app):
        """Admin sem o módulo 'quality' habilitado no tenant → 403."""
        headers = _make_headers(app, "admin", modules=[])
        res = client.post("/api/v1/quality/demo/seed", headers=headers)
        assert res.status_code == 403


class TestDemoSeedForceGate:
    """force=true (destrutivo) — restrito a superadmin + confirmação explícita."""

    def test_admin_force_true_denied_without_superadmin(self, client, admin_headers):
        """Admin de tenant (não superadmin) não pode disparar force=true."""
        pool, conn, cur = _mock_pool(2)
        with patch(_PATCH_TARGET, return_value=pool):
            res = client.post(
                "/api/v1/quality/demo/seed?force=true", headers=admin_headers
            )

        assert res.status_code == 403, f"Esperado 403, obtido {res.status_code}"
        pool.get_connection.assert_not_called()

    def test_superadmin_force_true_without_confirm_rejected(
        self, client, superadmin_headers
    ):
        """Superadmin sem confirm:true no body → 400, sem apagar nada."""
        pool, conn, cur = _mock_pool(2)
        with patch(_PATCH_TARGET, return_value=pool):
            res = client.post(
                "/api/v1/quality/demo/seed?force=true", headers=superadmin_headers
            )

        assert res.status_code == 400, f"Esperado 400, obtido {res.status_code}"
        pool.get_connection.assert_not_called()

    def test_superadmin_force_true_with_confirm_seeds(self, client, superadmin_headers):
        """Superadmin + confirm:true → 200, executa o seed destrutivo."""
        pool, conn, cur = _mock_pool(2)
        with patch(_PATCH_TARGET, return_value=pool):
            res = client.post(
                "/api/v1/quality/demo/seed?force=true",
                headers=superadmin_headers,
                json={"confirm": True},
            )

        assert res.status_code == 200, f"Esperado 200, obtido {res.status_code}"
        data = res.get_json()
        assert data["data"]["seeded"] is True

        executed = [c.args[0] for c in cur.execute.call_args_list]
        assert any("DELETE FROM quality_reworks" in q for q in executed)
        assert any("DELETE FROM quality_pieces" in q for q in executed)
        assert any("DELETE FROM quality_stations" in q for q in executed)

    def test_without_force_is_noop_when_data_exists(self, client, admin_headers):
        """Sem force, se já houver bancadas, é no-op (200, seeded=False) — comportamento
        preexistente que já estava correto e não deve regredir."""
        pool, conn, cur = _mock_pool(3)
        with patch(_PATCH_TARGET, return_value=pool):
            res = client.post("/api/v1/quality/demo/seed", headers=admin_headers)

        assert res.status_code == 200
        data = res.get_json()
        assert data["data"]["seeded"] is False
        executed = [c.args[0] for c in cur.execute.call_args_list]
        assert not any("DELETE FROM" in q for q in executed)
