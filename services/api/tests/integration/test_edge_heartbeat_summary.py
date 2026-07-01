"""Tests for task-018: GET /api/v1/edge/sites/<site_id>/heartbeat-summary.

Eval cases (spec):
  1. seed conhecido → agregados corretos (avg/max/uptime/contagem) via Postgres REAL
  2. window filtra corretamente (heartbeats fora da janela não entram no agregado)
  3. window acima do máximo é clampada na rota
  4. site sem heartbeat na janela → resposta coerente (zeros/null, não 500)
  5. isolamento cross-tenant: dados de outro tenant nunca entram no agregado
  6. site de outro tenant → 404 (C-01)
  7. sem JWT → 401

Testes 1–5: Postgres REAL via pg_pool/pg_raw/tenant_id fixtures.
Testes 3, 6, 7: Flask test client com mock.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

from app.infrastructure.database.repositories.edge_heartbeat_repository import (
    EdgeHeartbeatRepository,
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
    inference_fps: float | None = None,
    inference_latency_ms: float | None = None,
) -> None:
    device_id = f"dev-{str(uuid4())[:8]}"
    cur.execute(
        """
        INSERT INTO public.edge_heartbeats
            (tenant_id, site_id, device_id, received_at, status,
             inference_fps, inference_latency_ms)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (tenant_id, site_id, device_id, received_at, status,
         inference_fps, inference_latency_ms),
    )


def _make_jwt(app, tenant_id, role="admin"):
    with app.app_context():
        return create_access_token(
            identity=str(uuid4()),
            additional_claims={"tenant_id": str(tenant_id), "role": role},
        )


# ---------------------------------------------------------------------------
# Integration tests: Postgres REAL — NÃO mockar o repositório
# ---------------------------------------------------------------------------

class TestSummaryRepositoryAggregates:
    """Valida SQL de agregação real contra Postgres efêmero."""

    def test_aggregates_match_seed(self, pg_pool, pg_raw, tenant_id):
        """avg/max/uptime/count corretos com seed conhecido."""
        repo = EdgeHeartbeatRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, name="agg-site")

        now = datetime.now(timezone.utc)
        # 3 heartbeats na janela: 2 healthy, 1 degraded
        _insert_heartbeat(cur, tenant_id, sid, now - timedelta(minutes=5),
                          status="healthy", inference_fps=10.0, inference_latency_ms=20.0)
        _insert_heartbeat(cur, tenant_id, sid, now - timedelta(minutes=10),
                          status="healthy", inference_fps=5.0, inference_latency_ms=30.0)
        _insert_heartbeat(cur, tenant_id, sid, now - timedelta(minutes=15),
                          status="degraded", inference_fps=2.0, inference_latency_ms=50.0)

        summary = repo.summary_for_site(tenant_id, sid, window_seconds=3600)

        assert summary["heartbeat_count"] == 3
        assert abs(float(summary["avg_inference_fps"]) - (10.0 + 5.0 + 2.0) / 3) < 0.01
        assert abs(float(summary["max_inference_fps"]) - 10.0) < 0.01
        assert abs(float(summary["avg_inference_latency_ms"]) - (20.0 + 30.0 + 50.0) / 3) < 0.01
        # uptime_pct: 2 healthy / 3 total = 66.66...%
        assert abs(float(summary["uptime_pct"]) - (2 / 3 * 100.0)) < 0.01
        assert summary["last_status"] is not None

    def test_window_filters_old_heartbeats(self, pg_pool, pg_raw, tenant_id):
        """Heartbeats fora da janela não entram no agregado."""
        repo = EdgeHeartbeatRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, name="window-site")

        now = datetime.now(timezone.utc)
        # 1 heartbeat na janela (30 min atrás), 1 fora (3 horas atrás)
        _insert_heartbeat(cur, tenant_id, sid, now - timedelta(minutes=30),
                          status="healthy", inference_fps=8.0)
        _insert_heartbeat(cur, tenant_id, sid, now - timedelta(hours=3),
                          status="degraded", inference_fps=1.0)

        # janela de 1h → pega apenas o de 30 min
        summary = repo.summary_for_site(tenant_id, sid, window_seconds=3600)
        assert summary["heartbeat_count"] == 1
        assert abs(float(summary["avg_inference_fps"]) - 8.0) < 0.01
        assert summary["last_status"] == "healthy"

    def test_empty_window_returns_coherent_zeros(self, pg_pool, pg_raw, tenant_id):
        """Site sem heartbeat na janela → zeros/null coerentes, nunca 500."""
        repo = EdgeHeartbeatRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, name="empty-site")

        # heartbeat muito antigo (fora da janela de 1h)
        _insert_heartbeat(cur, tenant_id, sid,
                          datetime.now(timezone.utc) - timedelta(hours=5),
                          status="healthy")

        summary = repo.summary_for_site(tenant_id, sid, window_seconds=3600)
        assert summary["heartbeat_count"] == 0
        assert summary["avg_inference_fps"] is None
        assert summary["max_inference_fps"] is None
        assert summary["avg_inference_latency_ms"] is None
        assert summary["uptime_pct"] is None
        assert summary["last_received_at"] is None
        assert summary["last_status"] is None

    def test_uptime_all_healthy(self, pg_pool, pg_raw, tenant_id):
        """100% uptime quando todos os heartbeats são healthy."""
        repo = EdgeHeartbeatRepository(pg_pool)
        cur = pg_raw.cursor()
        sid = _insert_site(cur, tenant_id, name="allhealthy-site")

        now = datetime.now(timezone.utc)
        for i in range(4):
            _insert_heartbeat(cur, tenant_id, sid, now - timedelta(minutes=i * 5),
                               status="healthy")

        summary = repo.summary_for_site(tenant_id, sid, window_seconds=3600)
        assert summary["heartbeat_count"] == 4
        assert abs(float(summary["uptime_pct"]) - 100.0) < 0.01

    def test_cross_tenant_isolation(self, pg_pool, pg_raw, tenant_id):
        """Dados de outro tenant nunca entram no agregado (C-01)."""
        repo = EdgeHeartbeatRepository(pg_pool)
        cur = pg_raw.cursor()

        tid_b = str(uuid4())
        slug_b = f"inttest-b-{tid_b[:8]}"
        cur.execute(
            "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
            (tid_b, f"IntTest B {slug_b}", slug_b),
        )

        try:
            now = datetime.now(timezone.utc)
            sid_a = _insert_site(cur, tenant_id, name="a-site")
            sid_b = _insert_site(cur, tid_b, name="b-site")

            # tenant_a: 2 heartbeats fps=10
            _insert_heartbeat(cur, tenant_id, sid_a, now - timedelta(minutes=5),
                               status="healthy", inference_fps=10.0)
            _insert_heartbeat(cur, tenant_id, sid_a, now - timedelta(minutes=10),
                               status="healthy", inference_fps=10.0)

            # tenant_b: 10 heartbeats fps=1 — NÃO devem aparecer em tenant_a
            for _ in range(10):
                _insert_heartbeat(cur, tid_b, sid_b, now - timedelta(minutes=5),
                                   status="degraded", inference_fps=1.0)

            summary_a = repo.summary_for_site(tenant_id, sid_a, window_seconds=3600)
            assert summary_a["heartbeat_count"] == 2
            assert abs(float(summary_a["avg_inference_fps"]) - 10.0) < 0.01
        finally:
            cur.execute("DELETE FROM public.tenants WHERE id = %s", (tid_b,))


# ---------------------------------------------------------------------------
# Route tests: Flask test client (window clamping, auth, 404)
# ---------------------------------------------------------------------------

class TestHeartbeatSummaryRoute:

    def _mock_site_repo(self, tenant_id, site_id, found: bool = True):
        repo = MagicMock()
        repo.get_site_by_id.return_value = (
            {"id": str(site_id), "tenant_id": str(tenant_id),
             "name": "Site X", "deployment_mode": "edge", "status": "active"}
            if found else None
        )
        return repo

    def _mock_hb_repo(self, summary_data: dict | None = None):
        repo = MagicMock()
        default = {
            "heartbeat_count": 5,
            "avg_inference_fps": 7.5,
            "max_inference_fps": 10.0,
            "avg_inference_latency_ms": 25.0,
            "uptime_pct": 80.0,
            "last_received_at": datetime.now(timezone.utc),
            "last_status": "healthy",
        }
        repo.summary_for_site.return_value = summary_data if summary_data is not None else default
        return repo

    def test_no_jwt_returns_401(self, client):
        res = client.get(f"/api/v1/edge/sites/{uuid4()}/heartbeat-summary")
        assert res.status_code == 401

    def test_operator_role_returns_403(self, client, app):
        token = _make_jwt(app, uuid4(), role="operator")
        res = client.get(
            f"/api/v1/edge/sites/{uuid4()}/heartbeat-summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403

    def test_cross_tenant_site_returns_404(self, client, app):
        """C-01: site de outro tenant → 404; repo.summary_for_site nunca chamado."""
        from tests.security._helpers_tenant import make_two_tenant_contexts
        ctx_a, ctx_b = make_two_tenant_contexts(app)

        mock_site = self._mock_site_repo(ctx_b.tenant_id, ctx_a.site_id, found=False)
        mock_hb = self._mock_hb_repo()

        with (
            patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site),
            patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb),
        ):
            res = client.get(
                f"/api/v1/edge/sites/{ctx_a.site_id}/heartbeat-summary",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert res.status_code == 404
        mock_hb.summary_for_site.assert_not_called()

    def test_window_above_max_is_clamped(self, client, app):
        """window=30d (> 7d máx) → clampado a 604800s na chamada ao repo."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_site = self._mock_site_repo(tenant_id, site_id)
        mock_hb = self._mock_hb_repo()

        with (
            patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site),
            patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb),
        ):
            client.get(
                f"/api/v1/edge/sites/{site_id}/heartbeat-summary?window=30d",
                headers={"Authorization": f"Bearer {token}"},
            )

        call_args = mock_hb.summary_for_site.call_args
        window_used = call_args.args[2] if call_args.args else call_args.kwargs["window_seconds"]
        assert window_used == 7 * 24 * 3600

    def test_default_window_is_24h(self, client, app):
        """Sem window param → 86400s."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_site = self._mock_site_repo(tenant_id, site_id)
        mock_hb = self._mock_hb_repo()

        with (
            patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site),
            patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb),
        ):
            client.get(
                f"/api/v1/edge/sites/{site_id}/heartbeat-summary",
                headers={"Authorization": f"Bearer {token}"},
            )

        call_args = mock_hb.summary_for_site.call_args
        window_used = call_args.args[2] if call_args.args else call_args.kwargs["window_seconds"]
        assert window_used == 24 * 3600

    def test_response_shape_and_derived_status(self, client, app):
        """Shape completo da resposta e derived_status corretos."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_site = self._mock_site_repo(tenant_id, site_id)
        mock_hb = self._mock_hb_repo()

        with (
            patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site),
            patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb),
        ):
            res = client.get(
                f"/api/v1/edge/sites/{site_id}/heartbeat-summary?window=1h",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        summary = data["data"]
        for field in (
            "site_id", "window_seconds", "heartbeat_count",
            "avg_inference_fps", "max_inference_fps",
            "avg_inference_latency_ms", "uptime_pct",
            "last_status", "last_received_at", "derived_status",
        ):
            assert field in summary, f"Campo '{field}' ausente da resposta"

        assert summary["derived_status"] == "healthy"
        assert summary["heartbeat_count"] == 5
        assert summary["window_seconds"] == 3600

    def test_empty_window_derived_status_offline(self, client, app):
        """Janela vazia → derived_status=offline, zeros/null, HTTP 200."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_site = self._mock_site_repo(tenant_id, site_id)
        mock_hb = self._mock_hb_repo({
            "heartbeat_count": 0,
            "avg_inference_fps": None,
            "max_inference_fps": None,
            "avg_inference_latency_ms": None,
            "uptime_pct": None,
            "last_received_at": None,
            "last_status": None,
        })

        with (
            patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site),
            patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb),
        ):
            res = client.get(
                f"/api/v1/edge/sites/{site_id}/heartbeat-summary",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["heartbeat_count"] == 0
        assert data["avg_inference_fps"] is None
        assert data["uptime_pct"] is None
        assert data["derived_status"] == "offline"
