"""Tests for task-005: GET /api/v1/edge/sites/health.

Eval cases (spec):
  1. site com heartbeat recente (received_at = agora, status healthy) → derived_status 'healthy'
  2. site com heartbeat antigo (received_at = agora - 10min) → derived_status 'offline'
  3. site sem nenhum heartbeat → derived_status 'offline'
  4. isolamento: seed 2 tenants; resposta do tenant_a NÃO inclui sites do tenant_b (C-01)
  5. métricas do último heartbeat retornadas corretamente
  6. sem JWT → 401; role insuficiente → 403
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from tests.security._helpers_tenant import (
    make_two_tenant_contexts,
)


def _make_jwt(app, tenant_id, role="admin", user_id=None):
    from uuid import uuid4 as _uuid4
    from flask_jwt_extended import create_access_token
    uid = str(user_id or _uuid4())
    with app.app_context():
        return create_access_token(
            identity=uid,
            additional_claims={"tenant_id": str(tenant_id), "role": role},
        )


def _recent_hb_row(site_id, tenant_id):
    """Simula linha com heartbeat recente e status healthy."""
    return {
        "site_id": str(site_id),
        "site_name": "Site Alpha",
        "deployment_mode": "edge",
        "received_at": datetime.now(timezone.utc) - timedelta(seconds=10),
        "heartbeat_status": "healthy",
        "inference_fps": 4.8,
        "cameras_online": 3,
        "cameras_total": 4,
        "cpu_pct": 22.5,
        "gpu_pct": 55.0,
        "queue_depth": 0,
        "edge_version": "0.9.1",
    }


def _stale_hb_row(site_id, tenant_id):
    """Simula linha com heartbeat antigo (10 minutos atrás)."""
    row = _recent_hb_row(site_id, tenant_id)
    row["received_at"] = datetime.now(timezone.utc) - timedelta(minutes=10)
    return row


def _no_hb_row(site_id, tenant_id):
    """Simula linha sem nenhum heartbeat (LEFT JOIN → NULL)."""
    return {
        "site_id": str(site_id),
        "site_name": "Site Bravo",
        "deployment_mode": "cloud",
        "received_at": None,
        "heartbeat_status": None,
        "inference_fps": None,
        "cameras_online": None,
        "cameras_total": None,
        "cpu_pct": None,
        "gpu_pct": None,
        "queue_depth": None,
        "edge_version": None,
    }


class TestSitesHealth:

    def test_recent_heartbeat_returns_derived_status_healthy(self, client, app):
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_last_heartbeat_per_site.return_value = [
            _recent_hb_row(site_id, tenant_id)
        ]

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            res = client.get(
                "/api/v1/edge/sites/health",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        sites = data["data"]["sites"]
        assert len(sites) == 1
        assert sites[0]["derived_status"] == "healthy"
        assert sites[0]["site_id"] == str(site_id)

    def test_stale_heartbeat_returns_derived_status_offline(self, client, app):
        """Heartbeat mais antigo que o threshold → derived_status 'offline'."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_last_heartbeat_per_site.return_value = [
            _stale_hb_row(site_id, tenant_id)
        ]

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            res = client.get(
                "/api/v1/edge/sites/health",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        sites = res.get_json()["data"]["sites"]
        assert sites[0]["derived_status"] == "offline"

    def test_no_heartbeat_returns_derived_status_offline(self, client, app):
        """Site sem nenhum heartbeat → derived_status 'offline'."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_last_heartbeat_per_site.return_value = [
            _no_hb_row(site_id, tenant_id)
        ]

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            res = client.get(
                "/api/v1/edge/sites/health",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        sites = res.get_json()["data"]["sites"]
        assert sites[0]["derived_status"] == "offline"
        assert sites[0]["last_heartbeat_at"] is None

    def test_metrics_returned_from_latest_heartbeat(self, client, app):
        """Métricas do último heartbeat retornadas corretamente (não de um antigo)."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        row = _recent_hb_row(site_id, tenant_id)
        row["inference_fps"] = 5.0
        row["cameras_online"] = 2
        row["cameras_total"] = 3
        row["cpu_pct"] = 30.0
        row["gpu_pct"] = 70.0
        row["queue_depth"] = 5
        row["edge_version"] = "1.2.3"

        mock_repo = MagicMock()
        mock_repo.get_last_heartbeat_per_site.return_value = [row]

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            res = client.get(
                "/api/v1/edge/sites/health",
                headers={"Authorization": f"Bearer {token}"},
            )

        site_data = res.get_json()["data"]["sites"][0]
        assert site_data["inference_fps"] == 5.0
        assert site_data["cameras_online"] == 2
        assert site_data["cameras_total"] == 3
        assert site_data["cpu_pct"] == 30.0
        assert site_data["gpu_pct"] == 70.0
        assert site_data["queue_depth"] == 5
        assert site_data["edge_version"] == "1.2.3"

    def test_tenant_isolation_tenant_b_cannot_see_tenant_a_sites(self, client, app):
        """C-01: tenant_b não vê sites nem heartbeats do tenant_a."""
        ctx_a, ctx_b = make_two_tenant_contexts(app)
        site_a = _recent_hb_row(ctx_a.site_id, ctx_a.tenant_id)
        site_a["site_id"] = str(ctx_a.site_id)

        def _mock_health(tid):
            return [site_a] if tid == str(ctx_a.tenant_id) else []

        mock_repo = MagicMock()
        mock_repo.get_last_heartbeat_per_site.side_effect = _mock_health

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            res_b = client.get(
                "/api/v1/edge/sites/health",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert res_b.status_code == 200
        sites = res_b.get_json()["data"]["sites"]
        assert sites == [], "tenant_b NÃO deve ver sites do tenant_a"
        # repo chamado com tenant_b, nunca tenant_a
        mock_repo.get_last_heartbeat_per_site.assert_called_once_with(str(ctx_b.tenant_id))

    def test_no_jwt_returns_401(self, client):
        res = client.get("/api/v1/edge/sites/health")
        assert res.status_code == 401

    def test_operator_role_returns_403(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="operator")
        mock_repo = MagicMock()
        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            res = client.get(
                "/api/v1/edge/sites/health",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 403
        mock_repo.get_last_heartbeat_per_site.assert_not_called()

    def test_repo_called_with_jwt_tenant_id(self, client, app):
        """Repo é chamado com tenant_id do JWT, nunca outro."""
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)
        mock_repo = MagicMock()
        mock_repo.get_last_heartbeat_per_site.return_value = []

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_repo):
            client.get(
                "/api/v1/edge/sites/health",
                headers={"Authorization": f"Bearer {token}"},
            )

        mock_repo.get_last_heartbeat_per_site.assert_called_once_with(str(tenant_id))
