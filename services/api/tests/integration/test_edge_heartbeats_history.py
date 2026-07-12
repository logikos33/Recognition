"""Tests for task-009: GET /api/v1/edge/sites/<site_id>/heartbeats.

Eval cases (spec):
  1. site do tenant com N heartbeats → retorna em ordem received_at DESC, respeitando limit
  2. `before` filtra corretamente (cursor temporal)
  3. limit acima do máximo é clampado (não retorna 10000)
  4. isolamento: GET de site de OUTRO tenant → 404; resposta nunca inclui heartbeat de outro tenant
  5. sem JWT → 401
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

from tests.security._helpers_tenant import make_two_tenant_contexts


def _make_jwt(app, tenant_id, role="admin", user_id=None):
    uid = str(user_id or uuid4())
    with app.app_context():
        return create_access_token(
            identity=uid,
            additional_claims={"tenant_id": str(tenant_id), "role": role},
        )


def _hb_row(i: int = 0) -> dict:
    return {
        "id": 100 + i,
        "received_at": datetime.now(timezone.utc) - timedelta(seconds=i * 30),
        "status": "healthy",
        "inference_fps": 5.0,
        "cameras_online": 2,
        "cameras_total": 2,
        "cpu_pct": 20.0,
        "gpu_pct": 40.0,
        "queue_depth": 0,
        "edge_version": "0.9.0",
    }


class TestHeartbeatsHistory:

    def _mock_site_repo(self, tenant_id, site_id):
        repo = MagicMock()
        repo.get_site_by_id.return_value = {
            "id": str(site_id),
            "tenant_id": str(tenant_id),
            "name": "Site X",
            "deployment_mode": "edge",
            "status": "active",
        }
        return repo

    def test_returns_heartbeats_ordered_desc(self, client, app):
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)
        rows = [_hb_row(i) for i in range(3)]

        mock_hb_repo = MagicMock()
        mock_hb_repo.list_heartbeats.return_value = rows
        mock_site_repo = self._mock_site_repo(tenant_id, site_id)

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo), \
             patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo):
            res = client.get(
                f"/api/v1/edge/sites/{site_id}/heartbeats",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        heartbeats = data["data"]["heartbeats"]
        assert len(heartbeats) == 3

    def test_default_limit_100_passed_to_repo(self, client, app):
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_hb_repo = MagicMock()
        mock_hb_repo.list_heartbeats.return_value = []
        mock_site_repo = self._mock_site_repo(tenant_id, site_id)

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo), \
             patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo):
            client.get(
                f"/api/v1/edge/sites/{site_id}/heartbeats",
                headers={"Authorization": f"Bearer {token}"},
            )

        call_kwargs = mock_hb_repo.list_heartbeats.call_args
        limit_used = call_kwargs.kwargs.get("limit") or call_kwargs.args[2]
        assert limit_used == 100

    def test_limit_above_max_is_clamped_to_500(self, client, app):
        """limit=10000 deve ser clampado a 500 no repositório."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_hb_repo = MagicMock()
        mock_hb_repo.list_heartbeats.return_value = []
        mock_site_repo = self._mock_site_repo(tenant_id, site_id)

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo), \
             patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo):
            client.get(
                f"/api/v1/edge/sites/{site_id}/heartbeats?limit=10000",
                headers={"Authorization": f"Bearer {token}"},
            )

        # Repo recebe o valor clampado (≤ 500)
        call_kwargs = mock_hb_repo.list_heartbeats.call_args
        limit_used = call_kwargs.kwargs.get("limit") or call_kwargs.args[2]
        assert limit_used <= 500

    def test_before_cursor_passed_to_repo(self, client, app):
        """Parâmetro `before` é repassado ao repositório."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)
        cursor = "2026-06-01T12:00:00+00:00"

        mock_hb_repo = MagicMock()
        mock_hb_repo.list_heartbeats.return_value = []
        mock_site_repo = self._mock_site_repo(tenant_id, site_id)

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo), \
             patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo):
            client.get(
                f"/api/v1/edge/sites/{site_id}/heartbeats?before={cursor.replace('+', '%2B')}",
                headers={"Authorization": f"Bearer {token}"},
            )

        call_kwargs = mock_hb_repo.list_heartbeats.call_args
        before_used = call_kwargs.kwargs.get("before") or call_kwargs.args[3]
        assert before_used == cursor

    def test_cross_tenant_site_returns_404(self, client, app):
        """C-01: site de outro tenant → 404, nunca retorna heartbeats cross-tenant."""
        ctx_a, ctx_b = make_two_tenant_contexts(app)

        mock_hb_repo = MagicMock()
        mock_site_repo = MagicMock()
        # Site pertence a tenant_a, mas quem está requisitando é tenant_b
        mock_site_repo.get_site_by_id.return_value = None

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo), \
             patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo):
            res = client.get(
                f"/api/v1/edge/sites/{ctx_a.site_id}/heartbeats",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert res.status_code == 404
        mock_hb_repo.list_heartbeats.assert_not_called()

    def test_no_jwt_returns_401(self, client):
        res = client.get(f"/api/v1/edge/sites/{uuid4()}/heartbeats")
        assert res.status_code == 401

    def test_operator_role_returns_403(self, client, app):
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id, role="operator")

        mock_hb_repo = MagicMock()
        mock_site_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo), \
             patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo):
            res = client.get(
                f"/api/v1/edge/sites/{site_id}/heartbeats",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 403
        mock_hb_repo.list_heartbeats.assert_not_called()

    def test_heartbeat_fields_in_response(self, client, app):
        """Campos esperados presentes na resposta."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_hb_repo = MagicMock()
        mock_hb_repo.list_heartbeats.return_value = [_hb_row(0)]
        mock_site_repo = self._mock_site_repo(tenant_id, site_id)

        with patch("app.api.v1.edge.routes._get_repo", return_value=mock_hb_repo), \
             patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_site_repo):
            res = client.get(
                f"/api/v1/edge/sites/{site_id}/heartbeats",
                headers={"Authorization": f"Bearer {token}"},
            )

        hb = res.get_json()["data"]["heartbeats"][0]
        for field in ("id", "received_at", "status", "inference_fps",
                      "cameras_online", "cameras_total", "cpu_pct", "gpu_pct",
                      "queue_depth", "edge_version"):
            assert field in hb, f"Campo '{field}' ausente da resposta"
