"""Tests for task-016: GET /api/v1/edge/overview — fleet aggregated counts.

Eval cases (spec):
  1. seed conhecido (N sites, M devices, K offline) → contagens corretas
  2. tenant vazio → todos os campos zerados
  3. isolamento: repos chamados exclusivamente com tenant_id do JWT (C-01)
  4. dados do tenant_a não aparecem para tenant_b (cross-tenant seed)
  5. limiar de offline consistente com task-005 (_OFFLINE_THRESHOLD_SECONDS)
  6. role insuficiente → 403; sem JWT → 401; superadmin → 200
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from tests.security._helpers_tenant import make_two_tenant_contexts


def _make_jwt(app, tenant_id, role="admin"):
    from uuid import uuid4 as _uuid4
    from flask_jwt_extended import create_access_token
    uid = str(_uuid4())
    with app.app_context():
        return create_access_token(
            identity=uid,
            additional_claims={"tenant_id": str(tenant_id), "role": role},
        )


def _make_mocks(
    *,
    sites_total=0,
    active=0,
    inactive=0,
    maintenance=0,
    provisioning=0,
    devices_total=0,
    devices_online=0,
    devices_revoked=0,
    sites_offline=0,
):
    mock_site_repo = MagicMock()
    mock_site_repo.get_site_counts.return_value = {
        "sites_total": sites_total,
        "active": active,
        "inactive": inactive,
        "maintenance": maintenance,
        "provisioning": provisioning,
    }
    mock_site_repo.get_device_counts.return_value = {
        "total": devices_total,
        "online": devices_online,
        "revoked": devices_revoked,
    }
    mock_hb_repo = MagicMock()
    mock_hb_repo.count_sites_offline.return_value = sites_offline
    return mock_site_repo, mock_hb_repo


class TestFleetOverview:

    def test_correct_counts_with_known_seed(self, client, app):
        """5 sites (3 active+1 inactive+1 maintenance), 10 devices (6 online, 2 revoked), 2 offline."""
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)
        mock_site_repo, mock_hb_repo = _make_mocks(
            sites_total=5, active=3, inactive=1, maintenance=1, provisioning=0,
            devices_total=10, devices_online=6, devices_revoked=2,
            sites_offline=2,
        )

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo), \
             patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo):
            res = client.get(
                "/api/v1/edge/overview",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["sites_total"] == 5
        assert data["sites_por_status"] == {
            "active": 3, "inactive": 1, "maintenance": 1, "provisioning": 0,
        }
        assert data["devices_total"] == 10
        assert data["devices_online"] == 6
        assert data["devices_revoked"] == 2
        assert data["sites_offline"] == 2

    def test_empty_tenant_returns_zeros(self, client, app):
        """Tenant sem sites nem devices → todas as contagens são 0."""
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)
        mock_site_repo, mock_hb_repo = _make_mocks()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo), \
             patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo):
            res = client.get(
                "/api/v1/edge/overview",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["sites_total"] == 0
        assert data["sites_por_status"] == {
            "active": 0, "inactive": 0, "maintenance": 0, "provisioning": 0,
        }
        assert data["devices_total"] == 0
        assert data["devices_online"] == 0
        assert data["devices_revoked"] == 0
        assert data["sites_offline"] == 0

    def test_tenant_isolation_repos_called_with_jwt_tenant_id(self, client, app):
        """C-01: repos chamados exclusivamente com tenant_id do JWT."""
        ctx_a, ctx_b = make_two_tenant_contexts(app)
        mock_site_repo, mock_hb_repo = _make_mocks(
            sites_total=3, active=3, devices_total=5, devices_online=2, sites_offline=1,
        )

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo), \
             patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo):
            client.get(
                "/api/v1/edge/overview",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        mock_site_repo.get_site_counts.assert_called_once_with(str(ctx_b.tenant_id))
        device_call_args = mock_site_repo.get_device_counts.call_args[0]
        assert device_call_args[0] == str(ctx_b.tenant_id)
        hb_call_args = mock_hb_repo.count_sites_offline.call_args[0]
        assert hb_call_args[0] == str(ctx_b.tenant_id)

    def test_tenant_b_cannot_see_tenant_a_data(self, client, app):
        """C-01: dados do tenant_a não aparecem na resposta de tenant_b."""
        ctx_a, ctx_b = make_two_tenant_contexts(app)

        def _site_counts(tid):
            if tid == str(ctx_a.tenant_id):
                return {"sites_total": 4, "active": 4, "inactive": 0, "maintenance": 0, "provisioning": 0}
            return {"sites_total": 0, "active": 0, "inactive": 0, "maintenance": 0, "provisioning": 0}

        def _device_counts(tid, threshold):
            if tid == str(ctx_a.tenant_id):
                return {"total": 8, "online": 5, "revoked": 1}
            return {"total": 0, "online": 0, "revoked": 0}

        def _offline(tid, threshold):
            return 2 if tid == str(ctx_a.tenant_id) else 0

        mock_site_repo = MagicMock()
        mock_site_repo.get_site_counts.side_effect = _site_counts
        mock_site_repo.get_device_counts.side_effect = _device_counts
        mock_hb_repo = MagicMock()
        mock_hb_repo.count_sites_offline.side_effect = _offline

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo), \
             patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo):
            res_b = client.get(
                "/api/v1/edge/overview",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert res_b.status_code == 200
        data = res_b.get_json()["data"]
        assert data["sites_total"] == 0
        assert data["devices_total"] == 0
        assert data["sites_offline"] == 0

    def test_offline_threshold_consistent_with_task005(self, client, app):
        """Limiar de offline passado a count_sites_offline = _OFFLINE_THRESHOLD_SECONDS (task-005)."""
        from app.api.v1.edge import routes as edge_routes

        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)
        mock_site_repo, mock_hb_repo = _make_mocks()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo), \
             patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo):
            client.get(
                "/api/v1/edge/overview",
                headers={"Authorization": f"Bearer {token}"},
            )

        mock_hb_repo.count_sites_offline.assert_called_once()
        _, threshold_used = mock_hb_repo.count_sites_offline.call_args[0]
        assert threshold_used == edge_routes._OFFLINE_THRESHOLD_SECONDS

    def test_no_jwt_returns_401(self, client):
        res = client.get("/api/v1/edge/overview")
        assert res.status_code == 401

    def test_operator_role_returns_403(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="operator")
        mock_site_repo, mock_hb_repo = _make_mocks()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo), \
             patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo):
            res = client.get(
                "/api/v1/edge/overview",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 403
        mock_site_repo.get_site_counts.assert_not_called()
        mock_hb_repo.count_sites_offline.assert_not_called()

    def test_viewer_role_returns_403(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="viewer")
        mock_site_repo, mock_hb_repo = _make_mocks()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo), \
             patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo):
            res = client.get(
                "/api/v1/edge/overview",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 403

    def test_superadmin_role_allowed(self, client, app):
        """superadmin tem acesso ao overview."""
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="superadmin")
        mock_site_repo, mock_hb_repo = _make_mocks(sites_total=1, active=1)

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo), \
             patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo):
            res = client.get(
                "/api/v1/edge/overview",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        assert res.get_json()["data"]["sites_total"] == 1

    def test_response_shape_has_all_required_keys(self, client, app):
        """Resposta contém todas as chaves esperadas pela spec."""
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)
        mock_site_repo, mock_hb_repo = _make_mocks()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo), \
             patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo):
            res = client.get(
                "/api/v1/edge/overview",
                headers={"Authorization": f"Bearer {token}"},
            )

        data = res.get_json()["data"]
        assert "sites_total" in data
        assert "sites_por_status" in data
        assert set(data["sites_por_status"].keys()) == {"active", "inactive", "maintenance", "provisioning"}
        assert "devices_total" in data
        assert "devices_online" in data
        assert "devices_revoked" in data
        assert "sites_offline" in data
