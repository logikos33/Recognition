"""
Unit — /api/v1/monitoring (observabilidade da frota edge, superadmin-only).

Gate C-01: sem token → 401; role não-superadmin → 404 (NÃO 403 — a rota não
"existe" para quem não é superadmin); superadmin → 200.

Repos mockados via monkeypatch das factories module-level (_get_repo,
_get_command_repo, _get_channel_repo) — mesmo padrão de
tests/unit/test_edge_admin_gates.py. O filtro SQL LIKE 'monitoring.%' de
get_monitoring_command é exercitado contra Postgres real em
tests/integration/test_monitoring_repository.py.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.monitoring.routes as mon_routes

TENANT = "11111111-1111-1111-1111-111111111111"
SITE_ID = "55555555-5555-5555-5555-555555555555"
SITE_ROW = {
    "id": SITE_ID,
    "tenant_id": TENANT,
    "name": "Site RVB",
    "description": None,
    "location": "Blumenau/SC",
    "deployment_mode": "edge",
    "status": "active",
    "tenant_name": "RVB",
    "tenant_slug": "rvb",
}


def _auth(app, role: str = "superadmin") -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": TENANT,
                "tenant_schema": "tenant_test",
                "role": role,
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _fast_and_clean(monkeypatch):
    """Espera zero no poll (teste não dorme) + dedup de auditoria limpo."""
    monkeypatch.setenv("MONITORING_WAIT_S", "0")
    monkeypatch.setenv("MONITORING_SNAPSHOT_WAIT_S", "0")
    mon_routes._audit_dedup.clear()
    yield
    mon_routes._audit_dedup.clear()


@pytest.fixture
def repo(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(mon_routes, "_get_repo", lambda: mock)
    return mock


@pytest.fixture
def cmd_repo(monkeypatch):
    mock = MagicMock()
    mock.create.return_value = {"id": str(uuid.uuid4()), "status": "pending"}
    monkeypatch.setattr(mon_routes, "_get_command_repo", lambda: mock)
    return mock


@pytest.fixture
def channel_repo(monkeypatch):
    mock = MagicMock()
    mock.get_target_ref.return_value = None
    monkeypatch.setattr(mon_routes, "_get_channel_repo", lambda: mock)
    return mock


@pytest.fixture
def audit(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(mon_routes, "log_audit", mock)
    return mock


def _audit_actions(audit_mock) -> list[str]:
    return [call.kwargs["action"] for call in audit_mock.call_args_list]


# --------------------------------------------------------------------------- gate


class TestSuperadminGate:
    def test_sem_token_401(self, client, repo):
        resp = client.get("/api/v1/monitoring/sites")
        assert resp.status_code == 401
        repo.list_sites_overview.assert_not_called()

    def test_admin_comum_404_nao_403(self, app, client, repo):
        """C-01: não-superadmin não pode nem saber que a rota existe."""
        resp = client.get("/api/v1/monitoring/sites", headers=_auth(app, "admin"))
        assert resp.status_code == 404
        repo.list_sites_overview.assert_not_called()

    def test_operator_404(self, app, client, repo):
        resp = client.get("/api/v1/monitoring/sites", headers=_auth(app, "operator"))
        assert resp.status_code == 404
        repo.list_sites_overview.assert_not_called()

    def test_superadmin_200(self, app, client, repo, channel_repo):
        repo.list_sites_overview.return_value = []
        resp = client.get("/api/v1/monitoring/sites", headers=_auth(app))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["sites"] == []


# --------------------------------------------------------------------------- /sites


class TestListSitesDivergence:
    def test_divergencia_por_device(self, app, client, repo, channel_repo):
        """divergent=True quando edge_version != target_ref; None sem dado."""
        repo.list_sites_overview.return_value = [{
            **SITE_ROW,
            "devices": [
                {"device_id": "dev-1", "channel": "stable", "edge_version": "v1.0.0"},
                {"device_id": "dev-2", "channel": "stable", "edge_version": None},
                {"device_id": "dev-3", "channel": None, "edge_version": "v1.2.0"},
                {"device_id": "dev-4", "channel": "stable", "edge_version": "v1.2.0"},
            ],
        }]
        channel_repo.get_target_ref.return_value = "v1.2.0"

        resp = client.get("/api/v1/monitoring/sites", headers=_auth(app))
        assert resp.status_code == 200
        devices = {
            d["device_id"]: d
            for d in resp.get_json()["data"]["sites"][0]["devices"]
        }
        assert devices["dev-1"]["target_ref"] == "v1.2.0"
        assert devices["dev-1"]["divergent"] is True
        # Sem edge_version (nunca mandou heartbeat) → sem veredito
        assert devices["dev-2"]["divergent"] is None
        # Sem canal → sem target → sem veredito
        assert devices["dev-3"]["target_ref"] is None
        assert devices["dev-3"]["divergent"] is None
        assert devices["dev-4"]["divergent"] is False
        # target_ref resolvido uma vez por canal (cache por request)
        channel_repo.get_target_ref.assert_called_once_with("stable")


# --------------------------------------------------------------------------- query


class TestQueryFlow:
    def test_device_respondeu_state_done(self, app, client, repo, cmd_repo, audit):
        repo.get_site_any_tenant.return_value = SITE_ROW
        repo.get_monitoring_command.return_value = {
            "id": str(uuid.uuid4()),
            "command_type": "monitoring.query",
            "status": "done",
            "result": {"cpu_pct": [10, 20]},
            "created_at": None,
            "completed_at": None,
        }
        resp = client.post(
            f"/api/v1/monitoring/sites/{SITE_ID}/query",
            json={"window": "2h"},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["state"] == "done"
        assert data["result"] == {"cpu_pct": [10, 20]}
        assert data["command_id"].startswith("mon-q-")

        kwargs = cmd_repo.create.call_args.kwargs
        assert kwargs["tenant_id"] == TENANT
        assert kwargs["site_id"] == SITE_ID
        assert kwargs["command_type"] == "monitoring.query"
        assert kwargs["payload"] == {"window": "2h"}

    def test_sem_resposta_state_pending(self, app, client, repo, cmd_repo, audit):
        """Box em idle faz poll a cada ~60s — pending na 1ª chamada é normal."""
        repo.get_site_any_tenant.return_value = SITE_ROW
        repo.get_monitoring_command.return_value = {
            "id": str(uuid.uuid4()),
            "command_type": "monitoring.query",
            "status": "pending",
            "result": None,
            "created_at": None,
            "completed_at": None,
        }
        resp = client.post(
            f"/api/v1/monitoring/sites/{SITE_ID}/query",
            json={"window": "24h", "layers": ["cpu"], "max_points": 500},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["state"] == "pending"
        assert data["command_id"].startswith("mon-q-")
        assert cmd_repo.create.call_args.kwargs["payload"] == {
            "window": "24h", "layers": ["cpu"], "max_points": 500,
        }

    def test_window_invalida_422(self, app, client, repo, cmd_repo, audit):
        repo.get_site_any_tenant.return_value = SITE_ROW
        resp = client.post(
            f"/api/v1/monitoring/sites/{SITE_ID}/query",
            json={"window": "1h"},
            headers=_auth(app),
        )
        assert resp.status_code == 422
        cmd_repo.create.assert_not_called()

    def test_max_points_invalido_422(self, app, client, repo, cmd_repo, audit):
        repo.get_site_any_tenant.return_value = SITE_ROW
        resp = client.post(
            f"/api/v1/monitoring/sites/{SITE_ID}/query",
            json={"window": "2h", "max_points": "muitos"},
            headers=_auth(app),
        )
        assert resp.status_code == 422
        cmd_repo.create.assert_not_called()

    def test_site_inexistente_404(self, app, client, repo, cmd_repo, audit):
        repo.get_site_any_tenant.return_value = None
        resp = client.post(
            f"/api/v1/monitoring/sites/{uuid.uuid4()}/query",
            json={"window": "2h"},
            headers=_auth(app),
        )
        assert resp.status_code == 404
        cmd_repo.create.assert_not_called()

    def test_site_id_malformado_404(self, app, client, repo, cmd_repo, audit):
        resp = client.post(
            "/api/v1/monitoring/sites/nao-e-uuid/query",
            json={"window": "2h"},
            headers=_auth(app),
        )
        assert resp.status_code == 404
        repo.get_site_any_tenant.assert_not_called()

    def test_audit_query_deduplicada(self, app, client, repo, cmd_repo, audit):
        """Mesmo (user, site, action) dentro do TTL de 15 min audita 1x só."""
        repo.get_site_any_tenant.return_value = SITE_ROW
        repo.get_monitoring_command.return_value = {"status": "done", "result": {}}
        headers = _auth(app)  # mesmo token → mesmo user_id nas duas chamadas
        for _ in range(2):
            resp = client.post(
                f"/api/v1/monitoring/sites/{SITE_ID}/query",
                json={"window": "2h"},
                headers=headers,
            )
            assert resp.status_code == 200
        assert _audit_actions(audit).count("edge_monitoring.query") == 1


# --------------------------------------------------------------------------- snapshot


class TestSnapshot:
    def test_snapshot_pending_e_audita(self, app, client, repo, cmd_repo, audit):
        repo.get_site_any_tenant.return_value = SITE_ROW
        repo.get_monitoring_command.return_value = {"status": "pending", "result": None}
        resp = client.post(
            f"/api/v1/monitoring/sites/{SITE_ID}/snapshot", headers=_auth(app)
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["state"] == "pending"
        assert data["command_id"].startswith("mon-s-")
        assert cmd_repo.create.call_args.kwargs["command_type"] == "monitoring.snapshot"
        assert cmd_repo.create.call_args.kwargs["payload"] == {}
        assert "edge_monitoring.snapshot" in _audit_actions(audit)


# --------------------------------------------------------------------------- commands


class TestGetCommand:
    def test_comando_monitoring_visivel(self, app, client, repo):
        repo.get_monitoring_command.return_value = {
            "id": str(uuid.uuid4()),
            "command_type": "monitoring.query",
            "status": "done",
            "result": {"ok": True},
            "created_at": None,
            "completed_at": None,
        }
        resp = client.get("/api/v1/monitoring/commands/mon-q-abc123", headers=_auth(app))
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["state"] == "done"
        assert data["result"] == {"ok": True}

    def test_comando_de_outro_tipo_404(self, app, client, repo):
        """Comando não-monitoring (ex.: update_camera_config) é invisível por
        aqui — o LIKE 'monitoring.%' no repo devolve None (SQL real exercitado
        em tests/integration/test_monitoring_repository.py)."""
        repo.get_monitoring_command.return_value = None
        resp = client.get("/api/v1/monitoring/commands/qualquer-id", headers=_auth(app))
        assert resp.status_code == 404

    def test_gate_admin_404(self, app, client, repo):
        resp = client.get(
            "/api/v1/monitoring/commands/mon-q-abc123", headers=_auth(app, "admin")
        )
        assert resp.status_code == 404
        repo.get_monitoring_command.assert_not_called()


# --------------------------------------------------------------------------- thresholds


class TestThresholds:
    def test_get_default_vazio(self, app, client, repo):
        repo.get_site_any_tenant.return_value = SITE_ROW
        repo.get_thresholds.return_value = None
        resp = client.get(
            f"/api/v1/monitoring/sites/{SITE_ID}/thresholds", headers=_auth(app)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["thresholds"] == {}

    def test_put_valor_string_422(self, app, client, repo, audit):
        repo.get_site_any_tenant.return_value = SITE_ROW
        resp = client.put(
            f"/api/v1/monitoring/sites/{SITE_ID}/thresholds",
            json={"thresholds": {"cpu_pct_max": "quente"}},
            headers=_auth(app),
        )
        assert resp.status_code == 422
        repo.upsert_thresholds.assert_not_called()
        audit.assert_not_called()

    def test_put_mais_de_64_chaves_422(self, app, client, repo, audit):
        repo.get_site_any_tenant.return_value = SITE_ROW
        demais = {f"k{i}": i for i in range(65)}
        resp = client.put(
            f"/api/v1/monitoring/sites/{SITE_ID}/thresholds",
            json={"thresholds": demais},
            headers=_auth(app),
        )
        assert resp.status_code == 422
        repo.upsert_thresholds.assert_not_called()

    def test_put_nao_objeto_422(self, app, client, repo, audit):
        repo.get_site_any_tenant.return_value = SITE_ROW
        resp = client.put(
            f"/api/v1/monitoring/sites/{SITE_ID}/thresholds",
            json={"thresholds": [1, 2, 3]},
            headers=_auth(app),
        )
        assert resp.status_code == 422
        repo.upsert_thresholds.assert_not_called()

    def test_roundtrip_put_get_com_audit(self, app, client, repo, audit):
        repo.get_site_any_tenant.return_value = SITE_ROW
        novos = {"cpu_pct_max": 90, "gpu_temp_c_max": 82.5, "alertas_ativos": True}
        repo.get_thresholds.return_value = None  # nunca configurado (old = {})
        repo.upsert_thresholds.return_value = {
            "site_id": SITE_ID,
            "tenant_id": TENANT,
            "thresholds": novos,
            "updated_by": None,
            "updated_at": None,
        }
        resp = client.put(
            f"/api/v1/monitoring/sites/{SITE_ID}/thresholds",
            json={"thresholds": novos},
            headers=_auth(app),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["thresholds"] == novos

        kwargs = repo.upsert_thresholds.call_args.kwargs
        assert kwargs["site_id"] == SITE_ID
        assert kwargs["tenant_id"] == TENANT
        assert kwargs["thresholds"] == novos

        # Auditado SEMPRE, com old/new
        assert _audit_actions(audit) == ["edge_monitoring.thresholds_updated"]
        audit_kwargs = audit.call_args.kwargs
        assert audit_kwargs["old_value"] == {}
        assert audit_kwargs["new_value"] == novos
        assert audit_kwargs["target_type"] == "edge_monitoring"
        assert audit_kwargs["target_id"] == SITE_ID

        # GET devolve o que o repo tem
        repo.get_thresholds.return_value = {
            "site_id": SITE_ID, "tenant_id": TENANT,
            "thresholds": novos, "updated_by": None, "updated_at": None,
        }
        resp = client.get(
            f"/api/v1/monitoring/sites/{SITE_ID}/thresholds", headers=_auth(app)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["thresholds"] == novos


# --------------------------------------------------------------------------- logtail


class TestLogtail:
    def test_cria_comando_e_sempre_audita(self, app, client, repo, cmd_repo, audit):
        repo.get_site_any_tenant.return_value = SITE_ROW
        repo.get_monitoring_command.return_value = {"status": "pending", "result": None}
        headers = _auth(app)
        for _ in range(2):  # logtail NUNCA deduplica auditoria
            resp = client.post(
                f"/api/v1/monitoring/sites/{SITE_ID}/logtail",
                json={"unit": "edge-sync-agent", "lines": 100},
                headers=headers,
            )
            assert resp.status_code == 200
            assert resp.get_json()["data"]["command_id"].startswith("mon-l-")

        kwargs = cmd_repo.create.call_args.kwargs
        assert kwargs["command_type"] == "monitoring.logtail"
        assert kwargs["payload"] == {"unit": "edge-sync-agent", "lines": 100}
        assert _audit_actions(audit).count("edge_monitoring.logtail") == 2
        assert audit.call_args.kwargs["new_value"] == {
            "unit": "edge-sync-agent", "lines": 100,
        }

    def test_sem_unit_422(self, app, client, repo, cmd_repo, audit):
        repo.get_site_any_tenant.return_value = SITE_ROW
        resp = client.post(
            f"/api/v1/monitoring/sites/{SITE_ID}/logtail",
            json={"lines": 100},
            headers=_auth(app),
        )
        assert resp.status_code == 422
        cmd_repo.create.assert_not_called()
        audit.assert_not_called()

    def test_lines_acima_do_teto_422(self, app, client, repo, cmd_repo, audit):
        repo.get_site_any_tenant.return_value = SITE_ROW
        resp = client.post(
            f"/api/v1/monitoring/sites/{SITE_ID}/logtail",
            json={"unit": "edge-sync-agent", "lines": 501},
            headers=_auth(app),
        )
        assert resp.status_code == 422
        cmd_repo.create.assert_not_called()


# --------------------------------------------------------------------------- detections


class TestDetections:
    def test_lag_e_chain(self, app, client, repo):
        repo.get_site_any_tenant.return_value = SITE_ROW
        occurred = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)
        received = occurred + timedelta(seconds=4.5)
        cam = str(uuid.uuid4())
        repo.last_detection_per_camera.return_value = [
            {
                "camera_id": cam,
                "last_occurred_at": occurred,
                "last_received_at": received,
                "detections_in_window": 12,
            },
            {   # evento sem occurred_at → lag None honesto
                "camera_id": None,
                "last_occurred_at": None,
                "last_received_at": received,
                "detections_in_window": 3,
            },
        ]
        resp = client.get(
            f"/api/v1/monitoring/sites/{SITE_ID}/detections?window_minutes=60",
            headers=_auth(app),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["window_minutes"] == 60
        first, second = data["cameras"]
        assert first["camera_id"] == cam
        assert first["detections_in_window"] == 12
        assert first["ingest_lag_s"] == pytest.approx(4.5)
        assert first["chain"] == {
            "detection_to_ingest_s": pytest.approx(4.5),
            "ingest_to_notification_s": None,
        }
        assert second["camera_id"] is None
        assert second["ingest_lag_s"] is None
        repo.last_detection_per_camera.assert_called_once_with(SITE_ID, 60)

    def test_window_minutes_invalido_422(self, app, client, repo):
        repo.get_site_any_tenant.return_value = SITE_ROW
        resp = client.get(
            f"/api/v1/monitoring/sites/{SITE_ID}/detections?window_minutes=abc",
            headers=_auth(app),
        )
        assert resp.status_code == 422
        resp = client.get(
            f"/api/v1/monitoring/sites/{SITE_ID}/detections?window_minutes=0",
            headers=_auth(app),
        )
        assert resp.status_code == 422
        repo.last_detection_per_camera.assert_not_called()
