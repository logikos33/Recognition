"""
Unit — GET /api/cameras/<id>/health-context (WS10).

Telemetria real do site da câmera para o aviso health-aware de FPS.
Tenant-scoped, acessível a operator (não exige admin).
Sem site_id ou sem heartbeat → 200 com has_telemetry=false.
Câmera de outro tenant → 404 (C-01).
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.cameras.health_context_handler as handler

TENANT = "11111111-1111-1111-1111-111111111111"
CAMERA_ID = "44444444-4444-4444-4444-444444444444"
SITE_ID = "55555555-5555-5555-5555-555555555555"


def _auth(app, role: str = "operator", tenant_id: str = TENANT) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": tenant_id,
                "tenant_schema": "tenant_test",
                "role": role,
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _camera(site_id: str | None = SITE_ID) -> dict:
    return {
        "id": CAMERA_ID,
        "tenant_id": TENANT,
        "name": "Cam Doca",
        "site_id": site_id,
        "fps_target": 5,
    }


def _heartbeat(**overrides) -> dict:
    row = {
        "id": 1,
        "received_at": datetime.now(timezone.utc),
        "status": "healthy",
        "cpu_pct": Decimal("41.20"),
        "gpu_pct": Decimal("72.50"),
        "gpu_mem_pct": Decimal("63.00"),
        "inference_fps": Decimal("24.80"),
        "inference_latency_ms": Decimal("120.00"),
        "cameras_online": 7,
        "cameras_total": 8,
        "queue_depth": 3,
        "gpu_temp_c": None,
        "decode_pct": None,
        "edge_version": "1.2.0",
    }
    row.update(overrides)
    return row


@pytest.fixture()
def repos(monkeypatch):
    camera_repo = MagicMock()
    hb_repo = MagicMock()
    camera_repo.get_by_id_and_tenant.return_value = _camera()
    camera_repo.sum_fps_demand.return_value = {
        "fps_demand_total": 45,
        "cameras_active_count": 6,
    }
    hb_repo.get_last_heartbeat_for_site.return_value = _heartbeat()
    monkeypatch.setattr(handler, "_get_camera_repo", lambda: camera_repo)
    monkeypatch.setattr(handler, "_get_heartbeat_repo", lambda: hb_repo)
    return camera_repo, hb_repo


class TestHealthContext:

    def test_no_auth_returns_401(self, client, repos):
        resp = client.get(f"/api/cameras/{CAMERA_ID}/health-context")
        assert resp.status_code == 401

    def test_operator_can_access(self, app, client, repos):
        """Acessível com role operator — não exige admin (diferente de /edge/sites/health)."""
        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/health-context",
            headers=_auth(app, role="operator"),
        )
        assert resp.status_code == 200

    def test_returns_real_metrics(self, app, client, repos):
        camera_repo, hb_repo = repos
        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/health-context",
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["has_telemetry"] is True
        assert data["site_id"] == SITE_ID
        assert data["derived_status"] == "healthy"
        assert data["metrics"]["gpu_pct"] == 72.5
        assert data["metrics"]["inference_fps"] == 24.8
        assert data["metrics"]["queue_depth"] == 3
        assert data["metrics"]["gpu_temp_c"] is None  # UI mostra '—'
        assert data["fps_demand_total"] == 45
        assert data["cameras_active_count"] == 6
        # Queries tenant-scoped (C-01)
        camera_repo.get_by_id_and_tenant.assert_called_once_with(CAMERA_ID, TENANT)
        hb_repo.get_last_heartbeat_for_site.assert_called_once_with(SITE_ID, TENANT)
        camera_repo.sum_fps_demand.assert_called_once_with(SITE_ID, TENANT)

    def test_camera_without_site_returns_no_telemetry(self, app, client, repos):
        camera_repo, _ = repos
        camera_repo.get_by_id_and_tenant.return_value = _camera(site_id=None)
        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/health-context",
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["has_telemetry"] is False
        assert data["metrics"] is None

    def test_site_without_heartbeat_returns_no_telemetry(self, app, client, repos):
        _, hb_repo = repos
        hb_repo.get_last_heartbeat_for_site.return_value = None
        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/health-context",
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["has_telemetry"] is False
        assert data["site_id"] == SITE_ID
        # Demanda de FPS ainda é real mesmo sem heartbeat
        assert data["fps_demand_total"] == 45

    def test_stale_heartbeat_derives_offline(self, app, client, repos):
        _, hb_repo = repos
        hb_repo.get_last_heartbeat_for_site.return_value = _heartbeat(
            received_at=datetime(2020, 1, 1, tzinfo=timezone.utc)
        )
        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/health-context",
            headers=_auth(app),
        )
        assert resp.get_json()["data"]["derived_status"] == "offline"

    def test_cross_tenant_returns_404(self, app, client, repos):
        camera_repo, _ = repos
        camera_repo.get_by_id_and_tenant.return_value = None
        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/health-context",
            headers=_auth(app, tenant_id="22222222-2222-2222-2222-222222222222"),
        )
        assert resp.status_code == 404

    def test_v1_alias_works(self, app, client, repos):
        resp = client.get(
            f"/api/v1/cameras/{CAMERA_ID}/health-context",
            headers=_auth(app),
        )
        assert resp.status_code == 200
