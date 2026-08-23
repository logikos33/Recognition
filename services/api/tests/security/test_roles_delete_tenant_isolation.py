"""
Segurança — DELETE /api/admin/roles/<role_id> não pode vazar existência de
role de outro tenant (C-01: cross-tenant → 404, nunca 409/403).

Achado (grupo ADMIN): routes.py chamava
`repo.count_users_with_role(role_id)` SEM tenant antes de qualquer checagem de
posse. Admin do tenant B que tentasse deletar role do tenant A recebia 409 com
a contagem de usuários de A ("Esta role possui N usuário(s)...") — vaza
existência e volume de outro tenant.

Protocolo falha-antes/passa-depois (pela rota, JWT de dois tenants):
  (a) admin B → DELETE role de A → 404 (ANTES: 409 com contagem de A);
  (b) a contagem só acontece DEPOIS de resolver a role por (id, tenant_id) e
      é filtrada pelo tenant efetivo (ANTES: count(role_id) sem tenant);
  (c) admin A com usuários vinculados → 409 (comportamento preservado);
  (d) admin A sem usuários → 200 deleted;
  (e) superadmin com ?tenant_id=A → opera em A (override preservado);
  (f) repository: SQL do COUNT filtra por tenant_id.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import app.api.v1.roles.routes as roles_routes
from app.infrastructure.database.repositories.custom_role_repository import (
    CustomRoleRepository,
)
from tests.security._helpers_tenant import make_two_tenant_contexts, make_user_jwt

ROLE_ID = "33333333-3333-3333-3333-333333333333"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def ctxs(app):
    return make_two_tenant_contexts(app)


@pytest.fixture()
def repo(monkeypatch, ctxs):
    """Repositório mockado: ROLE_ID pertence ao tenant A e tem 3 usuários ativos."""
    ctx_a, _ = ctxs
    owner = str(ctx_a.tenant_id)
    mock = MagicMock(spec=CustomRoleRepository)

    def _get_by_id(role_id, tenant_id):
        if role_id == ROLE_ID and str(tenant_id) == owner:
            return {"id": ROLE_ID, "tenant_id": owner, "name": "Supervisor", "permissions": {}}
        return None

    def _delete(role_id, tenant_id):
        return role_id == ROLE_ID and str(tenant_id) == owner

    mock.get_by_id.side_effect = _get_by_id
    mock.delete.side_effect = _delete
    mock.count_users_with_role.return_value = 3
    monkeypatch.setattr(roles_routes, "_repo", lambda: mock)
    return mock


class TestDeleteRoleCrossTenant:
    def test_admin_b_deleting_role_of_a_gets_404(self, client, ctxs, repo):
        """FALHA-ANTES (409 com contagem de A) / PASSA-DEPOIS: 404."""
        _, ctx_b = ctxs
        resp = client.delete(f"/api/admin/roles/{ROLE_ID}", headers=_bearer(ctx_b.jwt_token))
        assert resp.status_code == 404, resp.get_json()
        assert "usuário" not in (resp.get_json().get("error") or "")
        repo.delete.assert_not_called()

    def test_count_is_scoped_to_effective_tenant(self, client, ctxs, repo):
        """FALHA-ANTES (count(role_id) sem tenant) / PASSA-DEPOIS: count(role_id, tenant_a)."""
        ctx_a, _ = ctxs
        repo.count_users_with_role.return_value = 0
        resp = client.delete(f"/api/admin/roles/{ROLE_ID}", headers=_bearer(ctx_a.jwt_token))
        assert resp.status_code == 200, resp.get_json()
        repo.count_users_with_role.assert_called_once_with(ROLE_ID, str(ctx_a.tenant_id))


class TestDeleteRoleOwnTenantPreserved:
    def test_admin_a_with_linked_users_gets_409(self, client, ctxs, repo):
        ctx_a, _ = ctxs
        resp = client.delete(f"/api/admin/roles/{ROLE_ID}", headers=_bearer(ctx_a.jwt_token))
        assert resp.status_code == 409, resp.get_json()
        assert "3 usuário" in resp.get_json()["error"]
        repo.delete.assert_not_called()

    def test_admin_a_without_users_deletes(self, client, ctxs, repo):
        ctx_a, _ = ctxs
        repo.count_users_with_role.return_value = 0
        resp = client.delete(f"/api/admin/roles/{ROLE_ID}", headers=_bearer(ctx_a.jwt_token))
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["data"] == {"deleted": True, "role_id": ROLE_ID}
        repo.delete.assert_called_once_with(role_id=ROLE_ID, tenant_id=str(ctx_a.tenant_id))

    def test_superadmin_override_tenant_id_query(self, app, client, ctxs, repo):
        """Superadmin de outro tenant com ?tenant_id=A opera em A (override preservado)."""
        ctx_a, _ = ctxs
        repo.count_users_with_role.return_value = 0
        token = make_user_jwt(app, uuid4(), role="superadmin")
        resp = client.delete(
            f"/api/admin/roles/{ROLE_ID}?tenant_id={ctx_a.tenant_id}", headers=_bearer(token)
        )
        assert resp.status_code == 200, resp.get_json()
        repo.get_by_id.assert_called_once_with(ROLE_ID, str(ctx_a.tenant_id))


class TestCountUsersWithRoleRepo:
    """SQL do COUNT deve filtrar por tenant_id (defesa em profundidade)."""

    def test_sql_filters_by_tenant_id(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"cnt": 0}
        conn = MagicMock()
        conn.cursor.return_value = cur

        @contextmanager
        def _conn():
            yield conn

        pool = MagicMock()
        pool.get_connection.side_effect = _conn
        tenant_id = str(uuid4())

        CustomRoleRepository(pool).count_users_with_role(ROLE_ID, tenant_id)

        sql, params = cur.execute.call_args[0]
        assert "tenant_id = %s" in sql
        assert params == (ROLE_ID, tenant_id)
