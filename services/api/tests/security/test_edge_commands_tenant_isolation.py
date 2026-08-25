"""
Segurança — /api/v1/edge/commands escopado pelo tenant do JWT / do device (C-01).

Achado (mutirão cross-tenant, grupo EDGE):
  POST /api/v1/edge/commands aceitava QUALQUER body.site_id sem verificar que
  o site pertence ao tenant do JWT — admin do tenant B, sabendo o UUID do site
  do tenant A, enfileirava comando pro box de A. E o device lia pendentes só
  por site_id (list_pending sem tenant_id), então o box de A executava.

Protocolo falha-antes/passa-depois:
  (a) admin de B cria comando pro site de A → 404 (nunca 2xx, nunca 403 —
      não vaza existência), repo.create NÃO é chamado;
  (b) admin de A cria pro próprio site → 201 (controle);
  (c) superadmin com tenant A no JWT (contexto assumido) cria pro site de A
      → 201 — o tenant efetivo é SEMPRE o do JWT;
  (d) GET /pending filtra pelo tenant do token do device (defesa em
      profundidade no repositório).

Repositórios mockados (padrão tests/unit/test_edge_commands_scope.py);
site repo devolve linha só quando (site_id, tenant_id) batem — espelha o
SQL real de EdgeSiteRepository.get_site_by_id.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import app.api.v1.edge_commands.routes as cmd_routes
import app.core.device_auth as device_auth
from app.infrastructure.database.repositories.edge_command_repository import (
    EdgeCommandRepository,
)
from tests.security._helpers_tenant import make_two_tenant_contexts, make_user_jwt

_COMMANDS_READ = "commands:read"


def _site_repo_owning(ctx) -> MagicMock:
    """EdgeSiteRepository mock: só o par (site_id, tenant_id) do ctx existe."""
    repo = MagicMock()

    def _get_site_by_id(site_id, tenant_id):
        if str(site_id) == str(ctx.site_id) and str(tenant_id) == str(ctx.tenant_id):
            return {"id": str(ctx.site_id), "tenant_id": str(ctx.tenant_id)}
        return None

    repo.get_site_by_id.side_effect = _get_site_by_id
    return repo


def _wire(monkeypatch, ctx_owner) -> MagicMock:
    cmd_repo = MagicMock()
    cmd_repo.create.return_value = {"id": "row-1", "status": "pending"}
    monkeypatch.setattr(cmd_routes, "_get_repo", lambda: cmd_repo)
    # raising=False: deixa o teste rodar contra o código PRÉ-fix (falha-antes),
    # onde _get_site_repo ainda não existia no módulo.
    monkeypatch.setattr(
        cmd_routes, "_get_site_repo", lambda: _site_repo_owning(ctx_owner), raising=False
    )
    return cmd_repo


class TestCreateCommandTenantScope:
    def test_admin_of_other_tenant_gets_404_and_nothing_is_enqueued(
        self, app, client, monkeypatch
    ):
        """FALHA-ANTES: admin de B enfileirava comando pro site de A (201)."""
        ctx_a, ctx_b = make_two_tenant_contexts(app)
        cmd_repo = _wire(monkeypatch, ctx_owner=ctx_a)

        resp = client.post(
            "/api/v1/edge/commands",
            json={"site_id": str(ctx_a.site_id), "command_type": "restart"},
            headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
        )

        assert resp.status_code == 404, (
            f"Cross-tenant deve ser 404 (C-01), got {resp.status_code}"
        )
        cmd_repo.create.assert_not_called()

    def test_admin_of_own_tenant_creates_201(self, app, client, monkeypatch):
        ctx_a, _ = make_two_tenant_contexts(app)
        cmd_repo = _wire(monkeypatch, ctx_owner=ctx_a)

        resp = client.post(
            "/api/v1/edge/commands",
            json={"site_id": str(ctx_a.site_id), "command_type": "restart"},
            headers={"Authorization": f"Bearer {ctx_a.jwt_token}"},
        )

        assert resp.status_code == 201
        kwargs = cmd_repo.create.call_args.kwargs
        assert kwargs["tenant_id"] == str(ctx_a.tenant_id)
        assert kwargs["site_id"] == str(ctx_a.site_id)

    def test_superadmin_assumed_context_uses_jwt_tenant(self, app, client, monkeypatch):
        """Override por role preservado: tenant efetivo = claim do JWT."""
        ctx_a, _ = make_two_tenant_contexts(app)
        cmd_repo = _wire(monkeypatch, ctx_owner=ctx_a)
        token = make_user_jwt(app, ctx_a.tenant_id, role="superadmin")

        resp = client.post(
            "/api/v1/edge/commands",
            json={"site_id": str(ctx_a.site_id), "command_type": "restart"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 201
        assert cmd_repo.create.call_args.kwargs["tenant_id"] == str(ctx_a.tenant_id)


class _MockPool:
    def __init__(self) -> None:
        self.cursor = MagicMock()
        self.cursor.fetchall.return_value = []
        conn = MagicMock()
        conn.cursor.return_value = self.cursor
        self._conn = conn

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self._conn


class TestPollPendingTenantScope:
    def test_route_passes_device_token_tenant_to_repo(self, app, client, monkeypatch):
        """FALHA-ANTES: list_pending era chamado só com site_id."""
        ctx_a, _ = make_two_tenant_contexts(app)
        repo = MagicMock()
        repo.list_pending.return_value = []
        monkeypatch.setattr(cmd_routes, "_get_repo", lambda: repo)
        monkeypatch.setattr(
            device_auth,
            "authenticate_device",
            lambda req: (str(ctx_a.tenant_id), str(ctx_a.site_id), ctx_a.device_id, [_COMMANDS_READ]),
        )

        resp = client.get(
            "/api/v1/edge/commands/pending",
            headers={"Authorization": "Bearer device-token"},
        )

        assert resp.status_code == 200
        repo.list_pending.assert_called_once_with(
            site_id=str(ctx_a.site_id), tenant_id=str(ctx_a.tenant_id), limit=50
        )

    def test_repo_sql_filters_by_tenant(self):
        """FALHA-ANTES: TypeError (list_pending sem parâmetro tenant_id)."""
        pool = _MockPool()
        repo = EdgeCommandRepository(pool)  # type: ignore[arg-type]

        repo.list_pending(site_id="site-1", tenant_id="tenant-1", limit=10)

        sql, params = pool.cursor.execute.call_args[0]
        assert "tenant_id = %s" in sql, "SQL de pendentes deve filtrar por tenant_id"
        assert "tenant-1" in params
