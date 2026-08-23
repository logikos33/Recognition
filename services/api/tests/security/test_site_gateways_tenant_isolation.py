"""
Segurança — /api/v1/site-gateways/<site_id> escopado pelo tenant do JWT (C-01).

Achado (mutirão cross-tenant, grupo EDGE):
  PUT /api/v1/site-gateways/<site_id> fazia upsert direto — ON CONFLICT
  (site_id) DO UPDATE sem cláusula de tenant — então admin do tenant B,
  conhecendo o UUID do site de A, sobrescrevia wg_public_key/endpoint/
  lan_subnet/config do gateway de A (o INSERT de B colidia no site_id e
  virava UPDATE na linha de A). E GET não exigia permissão: qualquer role
  do tenant lia chave pública WG, endpoint e subnet.

Protocolo falha-antes/passa-depois:
  (a) admin de B faz PUT no site de A → 404, repo.upsert NÃO é chamado;
  (b) admin de A faz PUT no próprio site → 200 (controle);
  (c) SQL do upsert só atualiza na colisão se o tenant bater (defesa em
      profundidade no repositório);
  (d) GET exige gateways:manage — viewer/operator → 403; admin e
      superadmin (contexto assumido) → 200;
  (e) GET cross-tenant → 404 (guarda de regressão: SQL já filtrava).

Repositórios mockados (padrão tests/unit/test_edge_admin_gates.py); site
repo devolve linha só quando (site_id, tenant_id) batem — espelha o SQL
real de EdgeSiteRepository.get_site_by_id.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from unittest.mock import MagicMock

import app.api.v1.site_gateways.routes as gw_routes
from app.infrastructure.database.repositories.site_gateway_repository import (
    SiteGatewayRepository,
)
from tests.security._helpers_tenant import make_two_tenant_contexts, make_user_jwt

_BODY = {"kind": "mikrotik", "wg_public_key": "pk-B", "wg_endpoint": "1.2.3.4:51820"}


def _site_repo_owning(ctx) -> MagicMock:
    repo = MagicMock()

    def _get_site_by_id(site_id, tenant_id):
        if str(site_id) == str(ctx.site_id) and str(tenant_id) == str(ctx.tenant_id):
            return {"id": str(ctx.site_id), "tenant_id": str(ctx.tenant_id)}
        return None

    repo.get_site_by_id.side_effect = _get_site_by_id
    return repo


def _gateway_repo_owning(ctx) -> MagicMock:
    repo = MagicMock()
    repo.upsert.return_value = {"id": "gw-1", "kind": "mikrotik", "status": "provisioning"}

    def _get_by_site(tenant_id, site_id):
        if str(site_id) == str(ctx.site_id) and str(tenant_id) == str(ctx.tenant_id):
            return {"id": "gw-1", "kind": "mikrotik", "wg_public_key": "pk-A"}
        return None

    repo.get_by_site.side_effect = _get_by_site
    return repo


def _wire(monkeypatch, ctx_owner) -> MagicMock:
    gw_repo = _gateway_repo_owning(ctx_owner)
    monkeypatch.setattr(gw_routes, "_get_repo", lambda: gw_repo)
    # raising=False: roda contra o código PRÉ-fix (falha-antes), onde
    # _get_site_repo ainda não existia no módulo.
    monkeypatch.setattr(
        gw_routes, "_get_site_repo", lambda: _site_repo_owning(ctx_owner), raising=False
    )
    return gw_repo


class TestUpsertGatewayTenantScope:
    def test_admin_of_other_tenant_gets_404_and_nothing_is_written(
        self, app, client, monkeypatch
    ):
        """FALHA-ANTES: admin de B sobrescrevia o gateway do site de A (200)."""
        ctx_a, ctx_b = make_two_tenant_contexts(app)
        gw_repo = _wire(monkeypatch, ctx_owner=ctx_a)

        resp = client.put(
            f"/api/v1/site-gateways/{ctx_a.site_id}",
            json=_BODY,
            headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
        )

        assert resp.status_code == 404, (
            f"Cross-tenant deve ser 404 (C-01), got {resp.status_code}"
        )
        gw_repo.upsert.assert_not_called()

    def test_admin_of_own_tenant_upserts_200(self, app, client, monkeypatch):
        ctx_a, _ = make_two_tenant_contexts(app)
        gw_repo = _wire(monkeypatch, ctx_owner=ctx_a)

        resp = client.put(
            f"/api/v1/site-gateways/{ctx_a.site_id}",
            json=_BODY,
            headers={"Authorization": f"Bearer {ctx_a.jwt_token}"},
        )

        assert resp.status_code == 200
        kwargs = gw_repo.upsert.call_args.kwargs
        assert kwargs["tenant_id"] == str(ctx_a.tenant_id)
        assert kwargs["site_id"] == str(ctx_a.site_id)

    def test_superadmin_assumed_context_uses_jwt_tenant(self, app, client, monkeypatch):
        """Override por role preservado: tenant efetivo = claim do JWT."""
        ctx_a, _ = make_two_tenant_contexts(app)
        gw_repo = _wire(monkeypatch, ctx_owner=ctx_a)
        token = make_user_jwt(app, ctx_a.tenant_id, role="superadmin")

        resp = client.put(
            f"/api/v1/site-gateways/{ctx_a.site_id}",
            json=_BODY,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert gw_repo.upsert.call_args.kwargs["tenant_id"] == str(ctx_a.tenant_id)


class _MockPool:
    def __init__(self) -> None:
        self.cursor = MagicMock()
        self.cursor.fetchone.return_value = None
        conn = MagicMock()
        conn.cursor.return_value = self.cursor
        self._conn = conn

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self._conn


class TestUpsertRepositoryGuard:
    def test_on_conflict_update_is_guarded_by_tenant(self):
        """FALHA-ANTES: DO UPDATE sem WHERE de tenant — colisão em site_id
        de outro tenant virava UPDATE na linha alheia."""
        pool = _MockPool()
        repo = SiteGatewayRepository(pool)  # type: ignore[arg-type]

        repo.upsert(
            tenant_id="tenant-b", site_id="site-a", kind="mikrotik", model=None,
            wg_public_key="pk", wg_endpoint=None, lan_subnet=None, config={},
        )

        sql, _ = pool.cursor.execute.call_args[0]
        assert re.search(
            r"do update set.*?where\s+public\.site_gateways\.tenant_id\s*=\s*excluded\.tenant_id",
            sql.lower(), re.DOTALL,
        ), "ON CONFLICT DO UPDATE deve exigir tenant_id igual (C-01)"


class TestGetGatewayGate:
    def test_viewer_of_tenant_gets_403(self, app, client, monkeypatch):
        """FALHA-ANTES: GET sem gate — qualquer role lia wg_public_key/endpoint."""
        ctx_a, _ = make_two_tenant_contexts(app)
        gw_repo = _wire(monkeypatch, ctx_owner=ctx_a)
        token = make_user_jwt(app, ctx_a.tenant_id, role="viewer")

        resp = client.get(
            f"/api/v1/site-gateways/{ctx_a.site_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 403
        gw_repo.get_by_site.assert_not_called()

    def test_operator_of_tenant_gets_403(self, app, client, monkeypatch):
        ctx_a, _ = make_two_tenant_contexts(app)
        _wire(monkeypatch, ctx_owner=ctx_a)
        token = make_user_jwt(app, ctx_a.tenant_id, role="operator")

        resp = client.get(
            f"/api/v1/site-gateways/{ctx_a.site_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 403

    def test_admin_of_tenant_gets_200(self, app, client, monkeypatch):
        ctx_a, _ = make_two_tenant_contexts(app)
        _wire(monkeypatch, ctx_owner=ctx_a)

        resp = client.get(
            f"/api/v1/site-gateways/{ctx_a.site_id}",
            headers={"Authorization": f"Bearer {ctx_a.jwt_token}"},
        )

        assert resp.status_code == 200
        assert resp.get_json()["data"]["gateway"]["wg_public_key"] == "pk-A"

    def test_superadmin_assumed_context_gets_200(self, app, client, monkeypatch):
        """Override por role preservado no gate novo do GET: superadmin com
        tenant A no JWT (contexto assumido) passa e lê o gateway de A."""
        ctx_a, _ = make_two_tenant_contexts(app)
        _wire(monkeypatch, ctx_owner=ctx_a)
        token = make_user_jwt(app, ctx_a.tenant_id, role="superadmin")

        resp = client.get(
            f"/api/v1/site-gateways/{ctx_a.site_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert resp.get_json()["data"]["gateway"]["wg_public_key"] == "pk-A"

    def test_admin_of_other_tenant_gets_404(self, app, client, monkeypatch):
        """Guarda de regressão: GET cross-tenant → 404 (nunca 200)."""
        ctx_a, ctx_b = make_two_tenant_contexts(app)
        _wire(monkeypatch, ctx_owner=ctx_a)

        resp = client.get(
            f"/api/v1/site-gateways/{ctx_a.site_id}",
            headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
        )

        assert resp.status_code == 404
