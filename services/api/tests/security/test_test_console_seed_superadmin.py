"""
Segurança — POST /api/v1/admin/test-console/seed restrito a superadmin e sem
senha default hardcoded.

Achado (grupo ADMIN): a rota estava atrás de `require_admin` — admin de
QUALQUER tenant cliente podia criar/resetar um usuário admin
(test-admin@epi-ci.internal) com senha default hardcoded
('ci-test-password-2026') no tenant de teste. Sem consumidor no front nem em
scripts/CI (o seed real é scripts/seed_test_tenant.py).

Protocolo falha-antes/passa-depois:
  (a) admin de tenant → 403 (ANTES: passava o gate e executava o seed);
  (b) superadmin sem senha (body ou env TEST_CONSOLE_SEED_PASSWORD) → 400
      (ANTES: 200 com a senha hardcoded);
  (c) superadmin com body.password → 200;
  (d) superadmin com env TEST_CONSOLE_SEED_PASSWORD → 200;
  (e) nenhuma resposta/código-fonte expõe a senha default.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import app.api.v1.admin.test_console_routes as tc
from tests.security._helpers_tenant import make_user_jwt

SEED_URL = "/api/v1/admin/test-console/seed"
LEGACY_DEFAULT_PASS = "ci-test-password-2026"


def _headers(app, role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_user_jwt(app, uuid4(), role=role)}"}


@pytest.fixture()
def seed_pool(monkeypatch):
    """Pool mockado — o seed nunca toca banco real; fetchone devolve tuplas
    como o psycopg2 cursor padrão usado pela rota (tenant_row[1], user_row[2])."""
    cur = MagicMock()
    cur.fetchone.side_effect = [
        (tc.TEST_TENANT_ID, "test-epi-ci"),
        (str(uuid4()), "test-admin@epi-ci.internal", "admin"),
    ]
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    pool = MagicMock()
    pool.get_connection.return_value.__enter__.return_value = conn
    monkeypatch.setattr(tc, "_get_pool", lambda: pool)
    monkeypatch.delenv("TEST_CONSOLE_SEED_PASSWORD", raising=False)
    return cur


class TestSeedRoleGate:
    def test_admin_of_client_tenant_gets_403(self, app, client, seed_pool):
        """FALHA-ANTES (executava o seed) / PASSA-DEPOIS: admin → 403."""
        resp = client.post(SEED_URL, json={"password": "x"}, headers=_headers(app, "admin"))
        assert resp.status_code == 403, resp.get_json()
        seed_pool.execute.assert_not_called()

    def test_operator_gets_403(self, app, client, seed_pool):
        resp = client.post(SEED_URL, json={"password": "x"}, headers=_headers(app, "operator"))
        assert resp.status_code == 403
        seed_pool.execute.assert_not_called()


class TestSeedPasswordRequired:
    def test_superadmin_without_password_gets_400(self, app, client, seed_pool):
        """FALHA-ANTES (200 com senha hardcoded) / PASSA-DEPOIS: 400."""
        resp = client.post(SEED_URL, json={}, headers=_headers(app, "superadmin"))
        assert resp.status_code == 400, resp.get_json()
        seed_pool.execute.assert_not_called()

    def test_superadmin_with_body_password_seeds(self, app, client, seed_pool):
        resp = client.post(
            SEED_URL, json={"password": "s3nh4-forte"}, headers=_headers(app, "superadmin")
        )
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()
        assert body["data"]["seeded"] is True
        assert seed_pool.execute.call_count == 3
        assert LEGACY_DEFAULT_PASS not in resp.get_data(as_text=True)

    def test_superadmin_with_env_password_seeds(self, app, client, seed_pool, monkeypatch):
        monkeypatch.setenv("TEST_CONSOLE_SEED_PASSWORD", "env-s3nh4")
        resp = client.post(SEED_URL, json={}, headers=_headers(app, "superadmin"))
        assert resp.status_code == 200, resp.get_json()
        assert seed_pool.execute.call_count == 3


def test_no_hardcoded_default_password_in_source():
    """Guarda estática: a senha default não pode voltar ao código-fonte."""
    src = Path(tc.__file__).read_text(encoding="utf-8")
    assert LEGACY_DEFAULT_PASS not in src
