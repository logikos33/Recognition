"""
Regressão — GET /api/cameras/<id>/alerts cross-tenant (C-01).

Achado (c) do mapa de migração, grupo ALERTAS: training/job_handlers
::get_alerts_handler → InferenceService.get_alerts → AlertRepository
.get_by_camera listava public.alerts só por camera_id, sem tenant_id —
qualquer JWT listava os alertas (violations/evidence_key) de câmera de
outro tenant com 200.

FALHA antes do fix / PASSA depois: a rota passa get_tenant_id() até o
repository e o SELECT inclui `AND tenant_id = %s`; outro tenant recebe
lista vazia (mesma resposta de câmera sem alertas — não vaza existência).
"""
import pytest

import app.api.v1.training.job_handlers as job_handlers
from app.domain.services.inference_service import InferenceService
from app.infrastructure.database.repositories.alert_repository import AlertRepository

from ._helpers_tenant import make_two_tenant_contexts
from .test_alert_acknowledge_tenant_isolation import ALERT_ID, CAMERA_ID, _FakeAlertDb


@pytest.fixture()
def tenants(app):
    return make_two_tenant_contexts(app)


def _hdr(ctx) -> dict[str, str]:
    return {"Authorization": f"Bearer {ctx.jwt_token}"}


class TestCameraAlertsTenantIsolation:
    """(c) GET /api/cameras/<id>/alerts escopado pelo tenant do JWT."""

    @pytest.fixture()
    def db(self, tenants, monkeypatch):
        ctx_a, _ = tenants
        fake = _FakeAlertDb(str(ctx_a.tenant_id))
        monkeypatch.setattr(
            job_handlers, "get_inference_service",
            lambda: InferenceService(AlertRepository(fake)),
        )
        return fake

    def test_tenant_b_sees_no_alerts_of_tenant_a_camera(self, client, tenants, db):
        _, ctx_b = tenants
        resp = client.get(f"/api/cameras/{CAMERA_ID}/alerts", headers=_hdr(ctx_b))
        assert resp.status_code == 200
        assert resp.get_json()["data"] == [], (
            f"IDOR: tenant B listou alertas de A: {resp.get_json()}"
        )

    def test_select_sql_filters_by_jwt_tenant(self, client, tenants, db):
        _, ctx_b = tenants
        client.get(f"/api/cameras/{CAMERA_ID}/alerts", headers=_hdr(ctx_b))
        assert db.calls, "SELECT deveria ter sido executado"
        sql, params = db.calls[0]
        assert "tenant_id" in sql.lower(), "SELECT sem filtro de tenant_id"
        assert str(ctx_b.tenant_id) in [str(p) for p in params]
        assert str(CAMERA_ID) in [str(p) for p in params]

    def test_owner_tenant_lists_its_alerts(self, client, tenants, db):
        ctx_a, _ = tenants
        resp = client.get(f"/api/cameras/{CAMERA_ID}/alerts", headers=_hdr(ctx_a))
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(ALERT_ID)
