"""Tests for task-016: GET /api/v1/edge/overview — fleet overview.

Eval cases (spec):
  1. contagens corretas com seed conhecido (N sites, M devices, K offline)
  2. site em 'provisioning' sem heartbeat → NÃO entra em sites_offline
  3. consistência 005/016: derive_site_health_status e is_site_offline concordam sobre
     os mesmos dados (mesma fonte de verdade)
  4. isolamento cross-tenant: seed 2 tenants, contagens de um não incluem outro
  5. contagens de devices: total, online (last_seen recente), revoked
  6. sem JWT → 401; role insuficiente → 403

Testes 1–5: Postgres REAL via pg_pool/pg_raw/tenant_id fixtures (C-04, PR #25).
Teste 6: Flask test client com mock para validar auth (não testa contagem).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.core.edge_offline import (
    OFFLINE_THRESHOLD_SECONDS,
    derive_site_health_status,
    is_site_offline,
)
from app.infrastructure.database.repositories.edge_heartbeat_repository import (
    EdgeHeartbeatRepository,
)
from app.infrastructure.database.repositories.edge_site_repository import (
    EdgeSiteRepository,
)


# ---------------------------------------------------------------------------
# Helpers de seed
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


def _insert_device(
    cur,
    tenant_id: str,
    site_id: str,
    revoked: bool = False,
    last_seen_offset_s: int | None = None,
) -> str:
    device_id = f"dev-{str(uuid4())[:8]}"
    last_seen = None
    if last_seen_offset_s is not None:
        last_seen = datetime.now(timezone.utc) - timedelta(seconds=last_seen_offset_s)
    cur.execute(
        """
        INSERT INTO public.device_tokens
            (tenant_id, site_id, device_id, public_key_pem, fingerprint, revoked, last_seen_at)
        VALUES (%s, %s, %s, 'fake-pem', 'fake-fp', %s, %s)
        """,
        (tenant_id, site_id, device_id, revoked, last_seen),
    )
    return device_id


# ---------------------------------------------------------------------------
# Integration tests: Postgres REAL — NÃO mockar o repositório
# ---------------------------------------------------------------------------

class TestRepositoryCounts:
    """Valida SQL real (DISTINCT ON, FILTER) contra Postgres efêmero."""

    def test_site_status_counts_match_seed(self, pg_pool, pg_raw, tenant_id):
        """get_site_status_counts retorna contagem exata por status."""
        repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()
        _insert_site(cur, tenant_id, "active")
        _insert_site(cur, tenant_id, "active")
        _insert_site(cur, tenant_id, "inactive")
        _insert_site(cur, tenant_id, "maintenance")
        _insert_site(cur, tenant_id, "provisioning")

        rows = repo.get_site_status_counts(tenant_id)
        counts = {r["status"]: r["count"] for r in rows}

        assert counts.get("active", 0) == 2
        assert counts.get("inactive", 0) == 1
        assert counts.get("maintenance", 0) == 1
        assert counts.get("provisioning", 0) == 1

    def test_offline_count_via_distinct_on(self, pg_pool, pg_raw, tenant_id):
        """Sites offline derivados corretamente via DISTINCT ON + helper."""
        hb_repo = EdgeHeartbeatRepository(pg_pool)
        cur = pg_raw.cursor()

        recent = datetime.now(timezone.utc) - timedelta(seconds=10)
        stale = datetime.now(timezone.utc) - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS + 60)

        # site com heartbeat recente → online
        sid_online = _insert_site(cur, tenant_id, "active", "site-online")
        _insert_heartbeat(cur, tenant_id, sid_online, recent, "healthy")

        # site com heartbeat stale → offline
        sid_stale = _insert_site(cur, tenant_id, "active", "site-stale")
        _insert_heartbeat(cur, tenant_id, sid_stale, stale, "healthy")

        # site sem heartbeat → offline
        _insert_site(cur, tenant_id, "active", "site-nohb")

        rows = hb_repo.get_last_heartbeat_per_site_with_status(tenant_id)
        offline_count = sum(
            1
            for r in rows
            if is_site_offline(r.get("received_at"), r.get("heartbeat_status"), r["site_status"])
        )
        assert offline_count == 2

    def test_provisioning_not_counted_as_offline(self, pg_pool, pg_raw, tenant_id):
        """Site em 'provisioning' sem heartbeat NÃO entra em sites_offline (PR #25)."""
        hb_repo = EdgeHeartbeatRepository(pg_pool)
        cur = pg_raw.cursor()

        _insert_site(cur, tenant_id, "provisioning", "site-prov")

        rows = hb_repo.get_last_heartbeat_per_site_with_status(tenant_id)
        offline_count = sum(
            1
            for r in rows
            if is_site_offline(r.get("received_at"), r.get("heartbeat_status"), r["site_status"])
        )
        assert offline_count == 0

    def test_consistency_health_and_overview(self, pg_pool, pg_raw, tenant_id):
        """derive_site_health_status (005) e is_site_offline (016) concordam nos mesmos dados."""
        hb_repo = EdgeHeartbeatRepository(pg_pool)
        cur = pg_raw.cursor()

        recent = datetime.now(timezone.utc) - timedelta(seconds=10)
        stale = datetime.now(timezone.utc) - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS + 60)

        # Mix de sites com e sem heartbeat
        for _ in range(2):
            sid = _insert_site(cur, tenant_id, "active")
            _insert_heartbeat(cur, tenant_id, sid, recent, "healthy")
        for _ in range(2):
            sid = _insert_site(cur, tenant_id, "active")
            _insert_heartbeat(cur, tenant_id, sid, stale, "healthy")
        _insert_site(cur, tenant_id, "active")          # sem heartbeat
        _insert_site(cur, tenant_id, "provisioning")    # provisioning → não offline

        rows = hb_repo.get_last_heartbeat_per_site_with_status(tenant_id)

        offline_via_overview = sum(
            1
            for r in rows
            if is_site_offline(r.get("received_at"), r.get("heartbeat_status"), r["site_status"])
        )
        offline_via_health = sum(
            1
            for r in rows
            # health usa derive_site_health_status diretamente (ignora provisioning)
            # mas provisioning aqui não teria heartbeat → seria "offline" pelo health
            # O assert relevante é: para sites NÃO provisioning, ambos concordam
            if r["site_status"] != "provisioning"
            and derive_site_health_status(r.get("received_at"), r.get("heartbeat_status")) == "offline"
        )
        assert offline_via_overview == offline_via_health, (
            "derive_site_health_status e is_site_offline divergem — fonte única violada"
        )

    def test_cross_tenant_isolation(self, pg_pool, pg_raw, tenant_id):
        """Contagens de tenant_a NÃO incluem dados de tenant_b (C-01)."""
        site_repo = EdgeSiteRepository(pg_pool)
        hb_repo = EdgeHeartbeatRepository(pg_pool)

        # tenant_b separado
        tid_b = str(uuid4())
        slug_b = f"inttest-b-{tid_b[:8]}"

        cur = pg_raw.cursor()
        cur.execute(
            "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
            (tid_b, f"IntTest B {slug_b}", slug_b),
        )
        try:
            # Seed tenant_a: 2 sites active
            _insert_site(cur, tenant_id, "active", "a-site-1")
            _insert_site(cur, tenant_id, "active", "a-site-2")

            # Seed tenant_b: 5 sites
            for i in range(5):
                _insert_site(cur, tid_b, "active", f"b-site-{i}")

            counts_a = {r["status"]: r["count"] for r in site_repo.get_site_status_counts(tenant_id)}
            counts_b = {r["status"]: r["count"] for r in site_repo.get_site_status_counts(tid_b)}

            # Se o WHERE tenant_id falhasse, counts_a teria 7 (2+5), não 2.
            assert counts_a.get("active", 0) == 2, "tenant_a: 2 sites, sem vazamento de tenant_b"
            assert counts_b.get("active", 0) == 5, "tenant_b: 5 sites, sem vazamento de tenant_a"

            # Heartbeats também não vazam
            rows_a = hb_repo.get_last_heartbeat_per_site_with_status(tenant_id)
            rows_b = hb_repo.get_last_heartbeat_per_site_with_status(tid_b)
            assert len(rows_a) == 2
            assert len(rows_b) == 5
        finally:
            cur.execute("DELETE FROM public.tenants WHERE id = %s", (tid_b,))

    def test_device_counts(self, pg_pool, pg_raw, tenant_id):
        """get_device_fleet_counts retorna total/online/revoked corretos (FILTER)."""
        site_repo = EdgeSiteRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, "active", "dev-site")

        threshold = 120
        _insert_device(cur, tenant_id, sid, revoked=False, last_seen_offset_s=10)    # online
        _insert_device(cur, tenant_id, sid, revoked=False, last_seen_offset_s=300)   # stale
        _insert_device(cur, tenant_id, sid, revoked=True,  last_seen_offset_s=10)    # revoked
        _insert_device(cur, tenant_id, sid, revoked=False, last_seen_offset_s=None)  # nunca visto

        counts = site_repo.get_device_fleet_counts(tenant_id, threshold)
        assert counts["total"] == 4
        assert counts["online"] == 1
        assert counts["revoked"] == 1


# ---------------------------------------------------------------------------
# Auth tests: Flask test client com mock (não testam contagem — C-07 auth)
# ---------------------------------------------------------------------------

def _make_jwt(app, tenant_id, role="admin"):
    from flask_jwt_extended import create_access_token
    with app.app_context():
        return create_access_token(
            identity=str(uuid4()),
            additional_claims={"tenant_id": str(tenant_id), "role": role},
        )


class TestFleetOverviewAuth:
    """401/403 e isolamento via Flask test client — repos mockados onde aplicável."""

    def test_no_jwt_returns_401(self, client):
        res = client.get("/api/v1/edge/overview")
        assert res.status_code == 401

    def test_tenant_b_cannot_see_tenant_a_counts(self, client, app):
        """C-01: repo é chamado com o tenant_id do JWT, nunca com o de outro tenant.

        Usa _helpers_tenant.make_two_tenant_contexts para dois contextos distintos.
        """
        from tests.security._helpers_tenant import make_two_tenant_contexts

        ctx_a, ctx_b = make_two_tenant_contexts(app)

        call_log: list[str] = []

        def mock_status_counts(tid: str):
            call_log.append(tid)
            return [{"status": "active", "count": 5}] if tid == str(ctx_a.tenant_id) else []

        mock_hb = MagicMock()
        mock_hb.get_last_heartbeat_per_site_with_status.return_value = []

        mock_site = MagicMock()
        mock_site.get_site_status_counts.side_effect = mock_status_counts
        mock_site.get_device_fleet_counts.return_value = {"total": 0, "online": 0, "revoked": 0}

        with (
            patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb),
            patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site),
        ):
            res_b = client.get(
                "/api/v1/edge/overview",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert res_b.status_code == 200
        overview_b = res_b.get_json()["data"]
        # tenant_b tem 0 sites — não vê os 5 do tenant_a
        assert overview_b["sites_total"] == 0
        # repo sempre chamado com tenant_b, nunca tenant_a
        mock_site.get_site_status_counts.assert_called_once_with(str(ctx_b.tenant_id))
        assert str(ctx_a.tenant_id) not in call_log

    def test_operator_role_returns_403(self, client, app):
        token = _make_jwt(app, uuid4(), role="operator")
        mock_hb = MagicMock()
        mock_site = MagicMock()
        with (
            patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb),
            patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site),
        ):
            res = client.get(
                "/api/v1/edge/overview",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 403
        mock_hb.get_last_heartbeat_per_site_with_status.assert_not_called()
        mock_site.get_site_status_counts.assert_not_called()

    def test_admin_returns_200_with_correct_shape(self, client, app):
        """Endpoint retorna shape esperado com repos mockados."""
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="admin")

        mock_hb = MagicMock()
        mock_hb.get_last_heartbeat_per_site_with_status.return_value = []

        mock_site = MagicMock()
        mock_site.get_site_status_counts.return_value = [
            {"status": "active", "count": 3},
            {"status": "inactive", "count": 1},
        ]
        mock_site.get_device_fleet_counts.return_value = {
            "total": 5, "online": 3, "revoked": 1,
        }

        with (
            patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb),
            patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site),
        ):
            res = client.get(
                "/api/v1/edge/overview",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        overview = data["data"]
        assert overview["sites_total"] == 4
        assert overview["sites_por_status"]["active"] == 3
        assert overview["sites_por_status"]["inactive"] == 1
        assert overview["devices_total"] == 5
        assert overview["devices_online"] == 3
        assert overview["devices_revoked"] == 1
        assert overview["sites_offline"] == 0

        mock_site.get_site_status_counts.assert_called_once_with(str(tenant_id))
        mock_site.get_device_fleet_counts.assert_called_once_with(
            str(tenant_id), OFFLINE_THRESHOLD_SECONDS
        )
        mock_hb.get_last_heartbeat_per_site_with_status.assert_called_once_with(str(tenant_id))
