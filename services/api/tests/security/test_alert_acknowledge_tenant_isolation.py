"""
Regressão — POST /api/alerts/<id>/acknowledge cross-tenant (C-01: 404, nunca 200).

Achado (a) do mapa de migração, grupo ALERTAS: AlertRepository.acknowledge
fazia `UPDATE alerts ... WHERE id = %s` SEM tenant_id — qualquer JWT
reconhecia alerta de outro tenant e recebia a linha (violations/evidence_key)
com 200.

FALHA antes do fix / PASSA depois: a rota passa get_tenant_id() até o
repository e o UPDATE inclui `AND tenant_id = %s`. O "banco" abaixo é um
cursor falso que só devolve a linha se o SQL filtrar pelo tenant dono do
alerta — exatamente o que o Postgres faria com a cláusula certa.
(_FakeAlertDb é reusado por test_camera_alerts_tenant_isolation.py.)
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import app.api.v1.alerts.routes as alerts_routes
from app.infrastructure.database.repositories.alert_repository import AlertRepository

from ._helpers_tenant import make_two_tenant_contexts

ALERT_ID = uuid4()
CAMERA_ID = uuid4()


class _FakeAlertDb:
    """Pool falso: a linha do alerta pertence a `owner_tenant`.

    Emula o Postgres: SQL sem filtro de tenant_id devolve a linha (é o bug);
    SQL com filtro só devolve se o tenant do alerta estiver nos params.
    """

    def __init__(self, owner_tenant: str) -> None:
        self.owner_tenant = owner_tenant
        self.row = {
            "id": ALERT_ID,
            "camera_id": CAMERA_ID,
            "tenant_id": owner_tenant,
            "violations": [{"class": "no_helmet"}],
            "evidence_key": "evidence/secret.jpg",
            "acknowledged": True,
        }
        self.cursor = MagicMock()
        self.cursor.execute.side_effect = self._execute
        self.calls: list[tuple[str, tuple]] = []
        conn = MagicMock()
        conn.cursor.return_value = self.cursor
        self._conn = conn

    def _execute(self, sql: str, params=()) -> None:
        self.calls.append((sql, tuple(params)))
        visible = "tenant_id" not in sql.lower() or self.owner_tenant in [str(p) for p in params]
        self.cursor.fetchone.return_value = dict(self.row) if visible else None
        self.cursor.fetchall.return_value = [dict(self.row)] if visible else []

    @contextmanager
    def get_connection(self):  # type: ignore[no-untyped-def]
        yield self._conn


@pytest.fixture()
def tenants(app):
    return make_two_tenant_contexts(app)


def _hdr(ctx) -> dict[str, str]:
    return {"Authorization": f"Bearer {ctx.jwt_token}"}


class TestAcknowledgeAlertTenantIsolation:
    """(a) POST /api/alerts/<id>/acknowledge escopado pelo tenant do JWT."""

    @pytest.fixture()
    def db(self, tenants, monkeypatch):
        ctx_a, _ = tenants
        fake = _FakeAlertDb(str(ctx_a.tenant_id))
        monkeypatch.setattr(alerts_routes, "_get_repo", lambda: AlertRepository(fake))
        return fake

    def test_tenant_b_cannot_acknowledge_tenant_a_alert(self, client, tenants, db):
        _, ctx_b = tenants
        resp = client.post(f"/api/alerts/{ALERT_ID}/acknowledge", headers=_hdr(ctx_b))
        assert resp.status_code == 404, (
            f"IDOR: tenant B reconheceu alerta de A (got {resp.status_code}: {resp.get_json()})"
        )
        assert "evidence/secret.jpg" not in resp.get_data(as_text=True)

    def test_update_sql_filters_by_jwt_tenant(self, client, tenants, db):
        _, ctx_b = tenants
        client.post(f"/api/alerts/{ALERT_ID}/acknowledge", headers=_hdr(ctx_b))
        assert db.calls, "UPDATE deveria ter sido executado"
        sql, params = db.calls[0]
        assert "update alerts" in sql.lower()
        assert "tenant_id" in sql.lower(), "UPDATE sem filtro de tenant_id"
        assert str(ctx_b.tenant_id) in [str(p) for p in params]

    def test_owner_tenant_acknowledges_with_200(self, client, tenants, db):
        ctx_a, _ = tenants
        resp = client.post(f"/api/alerts/{ALERT_ID}/acknowledge", headers=_hdr(ctx_a))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["alert"]["acknowledged"] is True
