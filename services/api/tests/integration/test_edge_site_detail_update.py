"""Tests for task-017: GET /api/v1/edge/sites/<site_id> and PATCH /api/v1/edge/sites/<site_id>.

Eval cases (spec):
  1. GET detalhe retorna campos completos + nº devices + saúde derivada (Postgres real)
  2. saúde derivada usa helper compartilhado de 005/016 (sem regra divergente)
  3. GET site de outro tenant → 404 (C-01)
  4. PATCH altera só os campos enviados; enums inválidos → 400
  5. PATCH ignora tenant_id do body (imutável)
  6. PATCH site de outro tenant → 404 + nada muda (C-01)
  7. role insuficiente → 403; sem JWT → 401

Testes 1–3, 4–6 (repo level): Postgres REAL via pg_pool/pg_raw/tenant_id fixtures.
Testes 7 + enum + shape (HTTP level): Flask test client com repos mockados.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.core.edge_offline import (
    OFFLINE_THRESHOLD_SECONDS,
    derive_site_health_status,
)
from app.infrastructure.database.repositories.edge_site_repository import (
    EdgeSiteRepository,
)


# ---------------------------------------------------------------------------
# Helpers de seed (reutilizam o padrão de test_edge_fleet_overview)
# ---------------------------------------------------------------------------

def _insert_site(cur, tenant_id: str, status: str = "active", name: str | None = None) -> str:
    sid = str(uuid4())
    cur.execute(
        """
        INSERT INTO public.edge_sites (id, tenant_id, name, deployment_mode, status)
        VALUES (%s, %s, %s, 'edge', %s)
        """,
        (sid, tenant_id, name or f"site-{sid[:8]}", status),
    )
    return sid


def _insert_heartbeat(
    cur,
    tenant_id: str,
    site_id: str,
    received_at: datetime,
    status: str = "healthy",
) -> None:
    device_id = f"dev-{str(uuid4())[:8]}"
    cur.execute(
        """
        INSERT INTO public.edge_heartbeats
            (tenant_id, site_id, device_id, received_at, status)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (tenant_id, site_id, device_id, received_at, status),
    )


def _insert_device(cur, tenant_id: str, site_id: str) -> str:
    device_id = f"dev-{str(uuid4())[:8]}"
    cur.execute(
        """
        INSERT INTO public.device_tokens
            (tenant_id, site_id, device_id, public_key_pem, fingerprint, revoked)
        VALUES (%s, %s, %s, 'fake-pem', 'fake-fp', false)
        """,
        (tenant_id, site_id, device_id),
    )
    return device_id


def _make_jwt(app, tenant_id, role: str = "admin") -> str:
    from flask_jwt_extended import create_access_token
    with app.app_context():
        return create_access_token(
            identity=str(uuid4()),
            additional_claims={"tenant_id": str(tenant_id), "role": role},
        )


# ---------------------------------------------------------------------------
# Integration tests: get_site_detail — Postgres REAL
# ---------------------------------------------------------------------------

class TestRepositorySiteDetail:
    """Valida SQL real de get_site_detail contra Postgres efêmero."""

    def test_device_count_matches_seed(self, pg_pool, pg_raw, tenant_id):
        """device_count no detalhe bate exatamente com nº de devices inseridos."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, "active", "site-count")
        _insert_device(cur, tenant_id, sid)
        _insert_device(cur, tenant_id, sid)
        _insert_device(cur, tenant_id, sid)

        row = repo.get_site_detail(sid, tenant_id)

        assert row is not None
        assert int(row["device_count"]) == 3

    def test_device_count_zero_when_no_devices(self, pg_pool, pg_raw, tenant_id):
        """Site sem devices → device_count == 0 (COALESCE protege)."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, "active", "site-empty")

        row = repo.get_site_detail(sid, tenant_id)

        assert row is not None
        assert int(row["device_count"]) == 0

    def test_derived_status_healthy_from_recent_heartbeat(self, pg_pool, pg_raw, tenant_id):
        """Heartbeat recente → derive_site_health_status retorna status do heartbeat."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, "active", "site-healthy")
        recent = datetime.now(timezone.utc) - timedelta(seconds=10)
        _insert_heartbeat(cur, tenant_id, sid, recent, "healthy")

        row = repo.get_site_detail(sid, tenant_id)
        assert row is not None

        derived = derive_site_health_status(row.get("last_heartbeat_at"), row.get("heartbeat_status"))
        assert derived == "healthy"

    def test_derived_status_offline_for_stale_heartbeat(self, pg_pool, pg_raw, tenant_id):
        """Heartbeat stale → derive_site_health_status retorna 'offline'."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, "active", "site-stale")
        stale = datetime.now(timezone.utc) - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS + 60)
        _insert_heartbeat(cur, tenant_id, sid, stale, "healthy")

        row = repo.get_site_detail(sid, tenant_id)
        assert row is not None

        derived = derive_site_health_status(row.get("last_heartbeat_at"), row.get("heartbeat_status"))
        assert derived == "offline"

    def test_derived_status_offline_for_no_heartbeat(self, pg_pool, pg_raw, tenant_id):
        """Sem heartbeat → last_heartbeat_at NULL → derived 'offline'."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, "active", "site-nohb")

        row = repo.get_site_detail(sid, tenant_id)
        assert row is not None
        assert row.get("last_heartbeat_at") is None

        derived = derive_site_health_status(None, None)
        assert derived == "offline"

    def test_cross_tenant_returns_none(self, pg_pool, pg_raw, tenant_id):
        """Site de outro tenant → None (C-01 — não vaza existência)."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()

        tid_b = str(uuid4())
        slug_b = f"inttest-b-{tid_b[:8]}"
        cur.execute(
            "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
            (tid_b, f"IntTest B {slug_b}", slug_b),
        )
        try:
            sid_b = _insert_site(cur, tid_b, "active", "b-site")

            # tenant_a não deve ver site do tenant_b
            result = repo.get_site_detail(sid_b, tenant_id)
            assert result is None
        finally:
            cur.execute("DELETE FROM public.tenants WHERE id = %s", (tid_b,))

    def test_detail_uses_same_helper_as_health_endpoint(self, pg_pool, pg_raw, tenant_id):
        """Saúde derivada do detalhe concorda com helper compartilhado de task-005/016."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()

        recent = datetime.now(timezone.utc) - timedelta(seconds=10)
        stale = datetime.now(timezone.utc) - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS + 60)

        sid_ok = _insert_site(cur, tenant_id, "active", "det-ok")
        _insert_heartbeat(cur, tenant_id, sid_ok, recent, "degraded")

        sid_ko = _insert_site(cur, tenant_id, "active", "det-ko")
        _insert_heartbeat(cur, tenant_id, sid_ko, stale, "healthy")

        row_ok = repo.get_site_detail(sid_ok, tenant_id)
        row_ko = repo.get_site_detail(sid_ko, tenant_id)

        assert derive_site_health_status(row_ok["last_heartbeat_at"], row_ok["heartbeat_status"]) == "degraded"
        assert derive_site_health_status(row_ko["last_heartbeat_at"], row_ko["heartbeat_status"]) == "offline"


# ---------------------------------------------------------------------------
# Integration tests: update_site — Postgres REAL
# ---------------------------------------------------------------------------

class TestRepositoryUpdateSite:
    """Valida SQL real de update_site (PATCH parcial) contra Postgres efêmero."""

    def test_partial_update_name_only(self, pg_pool, pg_raw, tenant_id):
        """Atualizar só name — deployment_mode/status/location permanecem inalterados."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, "active", "original-name")

        row = repo.update_site(sid, tenant_id, {"name": "new-name"})

        assert row is not None
        assert row["name"] == "new-name"
        assert row["status"] == "active"
        assert row["deployment_mode"] == "edge"

    def test_partial_update_multiple_fields(self, pg_pool, pg_raw, tenant_id):
        """Atualizar status e location simultaneamente."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, "active", "multi-field")

        row = repo.update_site(sid, tenant_id, {"status": "maintenance", "location": "Recife"})

        assert row is not None
        assert row["status"] == "maintenance"
        assert row["location"] == "Recife"

    def test_empty_updates_returns_current_site(self, pg_pool, pg_raw, tenant_id):
        """Updates vazio → site retornado sem alterar nada."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, "inactive", "no-change")

        row = repo.update_site(sid, tenant_id, {})

        assert row is not None
        assert row["status"] == "inactive"

    def test_cross_tenant_update_returns_none(self, pg_pool, pg_raw, tenant_id):
        """Update em site de outro tenant → None (C-01 — 404 na route)."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()

        tid_b = str(uuid4())
        slug_b = f"inttest-b-{tid_b[:8]}"
        cur.execute(
            "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
            (tid_b, f"IntTest B {slug_b}", slug_b),
        )
        try:
            sid_b = _insert_site(cur, tid_b, "active", "b-cross")

            # tenant_a tentando editar site do tenant_b → None
            result = repo.update_site(sid_b, tenant_id, {"name": "hacked"})
            assert result is None

            # Confirma que o site de tenant_b NÃO foi alterado
            original = repo.get_site_detail(sid_b, tid_b)
            assert original is not None
            assert original["name"] == "b-cross"
        finally:
            cur.execute("DELETE FROM public.tenants WHERE id = %s", (tid_b,))

    def test_tenant_id_not_accepted_in_updates(self, pg_pool, pg_raw, tenant_id):
        """tenant_id não está em _UPDATABLE_SITE_FIELDS — filtrado silenciosamente."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, "active", "immutable-tenant")
        fake_tenant = str(uuid4())

        row = repo.update_site(sid, tenant_id, {"tenant_id": fake_tenant, "name": "renamed"})

        assert row is not None
        assert str(row["tenant_id"]) == tenant_id  # tenant_id inalterado
        assert row["name"] == "renamed"


# ---------------------------------------------------------------------------
# HTTP tests: auth, shape e enum — Flask test client com repos mockados
# ---------------------------------------------------------------------------

def _mock_site_row(tenant_id, site_id=None) -> dict:
    """Gera row fake coerente com o shape de get_site_detail."""
    sid = str(site_id or uuid4())
    return {
        "id": sid,
        "tenant_id": str(tenant_id),
        "name": "Test Site",
        "description": None,
        "location": "São Paulo",
        "deployment_mode": "edge",
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
        "created_by": str(uuid4()),
        "device_count": 2,
        "last_heartbeat_at": datetime.now(timezone.utc) - timedelta(seconds=10),
        "heartbeat_status": "healthy",
    }


class TestSiteDetailAuth:
    """Auth (401/403) e shape dos endpoints HTTP — repos mockados."""

    # -- GET --

    def test_no_jwt_get_returns_401(self, client):
        res = client.get("/api/v1/edge/sites/some-id")
        assert res.status_code == 401

    def test_operator_role_get_returns_403(self, client, app):
        token = _make_jwt(app, uuid4(), role="operator")
        mock_repo = MagicMock()
        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                "/api/v1/edge/sites/some-id",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 403
        mock_repo.get_site_detail.assert_not_called()

    def test_site_not_found_get_returns_404(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="admin")
        mock_repo = MagicMock()
        mock_repo.get_site_detail.return_value = None

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                "/api/v1/edge/sites/nonexistent",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 404

    def test_admin_get_returns_200_with_correct_shape(self, client, app):
        """GET retorna shape esperado: site + device_count + derived_health + last_heartbeat_at."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id, role="admin")
        mock_repo = MagicMock()
        mock_repo.get_site_detail.return_value = _mock_site_row(tenant_id, site_id)

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                f"/api/v1/edge/sites/{site_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        site = body["data"]["site"]
        assert site["id"] == str(site_id)
        assert site["tenant_id"] == str(tenant_id)
        assert "device_count" in site
        assert site["device_count"] == 2
        assert "derived_health" in site
        assert site["derived_health"] == "healthy"
        assert "last_heartbeat_at" in site

        mock_repo.get_site_detail.assert_called_once_with(str(site_id), str(tenant_id))

    def test_cross_tenant_get_returns_404(self, client, app):
        """GET com JWT de tenant_b em site de tenant_a → 404 (C-01)."""
        from tests.security._helpers_tenant import make_two_tenant_contexts

        ctx_a, ctx_b = make_two_tenant_contexts(app)
        mock_repo = MagicMock()
        # Retorna None porque tenant_b não tem acesso ao site de tenant_a
        mock_repo.get_site_detail.return_value = None

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                f"/api/v1/edge/sites/{ctx_a.site_id}",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert res.status_code == 404
        # Repo chamado com tenant_b — nunca com tenant_a
        mock_repo.get_site_detail.assert_called_once_with(
            str(ctx_a.site_id), str(ctx_b.tenant_id)
        )

    # -- PATCH --

    def test_no_jwt_patch_returns_401(self, client):
        res = client.patch("/api/v1/edge/sites/some-id", json={"name": "x"})
        assert res.status_code == 401

    def test_operator_role_patch_returns_403(self, client, app):
        token = _make_jwt(app, uuid4(), role="operator")
        mock_repo = MagicMock()
        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.patch(
                "/api/v1/edge/sites/some-id",
                json={"name": "x"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 403
        mock_repo.update_site.assert_not_called()

    def test_site_not_found_patch_returns_404(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="admin")
        mock_repo = MagicMock()
        mock_repo.update_site.return_value = None

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.patch(
                "/api/v1/edge/sites/nonexistent",
                json={"name": "new"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 404

    def test_admin_patch_returns_200(self, client, app):
        """PATCH bem-sucedido retorna 200 com site atualizado."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id, role="admin")

        updated_row = {
            "id": str(site_id),
            "tenant_id": str(tenant_id),
            "name": "renamed",
            "description": None,
            "location": None,
            "deployment_mode": "edge",
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "created_by": str(uuid4()),
        }
        mock_repo = MagicMock()
        mock_repo.update_site.return_value = updated_row

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.patch(
                f"/api/v1/edge/sites/{site_id}",
                json={"name": "renamed"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        assert body["data"]["site"]["name"] == "renamed"

        mock_repo.update_site.assert_called_once_with(
            str(site_id), str(tenant_id), {"name": "renamed"}
        )

    def test_patch_invalid_status_returns_400(self, client, app):
        """Enum status inválido → 400 antes de chamar o repo."""
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="admin")
        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.patch(
                "/api/v1/edge/sites/any",
                json={"status": "broken"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        mock_repo.update_site.assert_not_called()

    def test_patch_invalid_deployment_mode_returns_400(self, client, app):
        """Enum deployment_mode inválido → 400 antes de chamar o repo."""
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="admin")
        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.patch(
                "/api/v1/edge/sites/any",
                json={"deployment_mode": "serverless"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        mock_repo.update_site.assert_not_called()

    def test_patch_tenant_id_ignored_in_body(self, client, app):
        """tenant_id no body é silenciosamente ignorado — nunca chega ao repo."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id, role="admin")
        fake_tenant = str(uuid4())

        updated_row = {
            "id": str(site_id),
            "tenant_id": str(tenant_id),
            "name": "ok",
            "description": None,
            "location": None,
            "deployment_mode": "edge",
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "created_by": str(uuid4()),
        }
        mock_repo = MagicMock()
        mock_repo.update_site.return_value = updated_row

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.patch(
                f"/api/v1/edge/sites/{site_id}",
                json={"name": "ok", "tenant_id": fake_tenant},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        # update_site chamado sem tenant_id nos updates
        call_kwargs = mock_repo.update_site.call_args
        updates_arg = call_kwargs[0][2]  # terceiro argumento posicional
        assert "tenant_id" not in updates_arg

    def test_cross_tenant_patch_returns_404(self, client, app):
        """PATCH com JWT de tenant_b em site de tenant_a → 404 (C-01)."""
        from tests.security._helpers_tenant import make_two_tenant_contexts

        ctx_a, ctx_b = make_two_tenant_contexts(app)
        mock_repo = MagicMock()
        mock_repo.update_site.return_value = None  # cross-tenant: repo retorna None

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.patch(
                f"/api/v1/edge/sites/{ctx_a.site_id}",
                json={"name": "hacked"},
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert res.status_code == 404
        # Repo chamado com tenant_b — nunca executa para tenant_a
        mock_repo.update_site.assert_called_once_with(
            str(ctx_a.site_id), str(ctx_b.tenant_id), {"name": "hacked"}
        )
