"""
Unit — GET /api/v1/edge/config/poll (WS10).

Canal pull cloud→edge consumido pelo ConfigPoller do edge-sync-agent.
Contrato: body de PRIMEIRO NÍVEL {"cameras": [...]} (sem envelope success/data)
— o ConfigPoller aplica chaves top-level de forma parcial.

Segurança:
  - 401 sem device token (invariante /edge — C-05);
  - escopo site/tenant vem do enrollment do device (C-01);
  - resposta NUNCA contém username/password_encrypted.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import UUID

import app.api.v1.edge.routes as edge_routes
import app.core.device_auth as device_auth
from app.infrastructure.database.repositories.camera_repository import CameraRepository

TENANT = "11111111-1111-1111-1111-111111111111"
SITE_ID = "55555555-5555-5555-5555-555555555555"
DEVICE_ID = "device-abc123"

# Escopos como STRING literal (o que require_device_scope compara). Não usar
# DeviceTokenScope aqui: outra suíte pode ter mockado recognition_shared.enums
# em sys.modules, e o membro do enum viraria um MagicMock (pollution conhecida
# do full-suite — mesma classe das falhas pré-existentes de quality_inference).
CONFIG_READ = "config:read"
HEARTBEAT_WRITE = "heartbeat:write"


def _authed(*scopes: str):
    """Fake authenticate_device: device válido com os escopos (string) dados."""
    granted = list(scopes) or [CONFIG_READ]
    return lambda req: (TENANT, SITE_ID, DEVICE_ID, granted)


def _camera_config_row() -> dict:
    return {
        "id": UUID("44444444-4444-4444-4444-444444444444"),
        "name": "Cam Doca",
        "host": "10.0.0.20",
        "port": 554,
        "channel": 1,
        "subtype": 0,
        "rtsp_substream_url": None,
        "rtsp_url_override": None,
        "fps_target": 10,
        "quality_preset": "medium",
        "is_active": True,
        "module_code": "epi",
    }


class TestEdgeConfigPoll:

    def test_no_token_returns_401(self, client):
        resp = client.get("/api/v1/edge/config/poll")
        assert resp.status_code == 401

    def test_malformed_token_returns_401(self, client):
        resp = client.get(
            "/api/v1/edge/config/poll",
            headers={"Authorization": "Bearer nao-e-um-jwt"},
        )
        assert resp.status_code == 401

    def test_returns_cameras_of_device_site_top_level(self, client, monkeypatch):
        """Body top-level {cameras} — formato que o ConfigPoller._apply consome."""
        camera_repo = MagicMock()
        camera_repo.list_for_site_config.return_value = [_camera_config_row()]
        monkeypatch.setattr(edge_routes, "_get_camera_repo", lambda: camera_repo)
        monkeypatch.setattr(device_auth, "authenticate_device", _authed(CONFIG_READ))

        resp = client.get(
            "/api/v1/edge/config/poll",
            headers={"Authorization": "Bearer device-token"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        # SEM envelope success/data — contrato do ConfigPoller (top-level keys)
        assert "cameras" in body
        assert "data" not in body
        assert len(body["cameras"]) == 1
        cam = body["cameras"][0]
        assert cam["fps_target"] == 10
        assert cam["quality_preset"] == "medium"
        # ADR-0058: `channel` é o mapa canal→câmera do gravador que o
        # edge-sync-agent (ConfigPoller) passa a cachear e preferir sobre
        # RECORDER_CHANNEL_MAP no .env — contrato travado aqui para não
        # regredir silenciosamente se _SELECT_COLS mudar.
        assert cam["channel"] == 1
        # Escopo site/tenant do enrollment (C-01)
        camera_repo.list_for_site_config.assert_called_once_with(SITE_ID, TENANT)

    def test_response_never_contains_credentials(self, client, monkeypatch):
        camera_repo = MagicMock()
        camera_repo.list_for_site_config.return_value = [_camera_config_row()]
        monkeypatch.setattr(edge_routes, "_get_camera_repo", lambda: camera_repo)
        monkeypatch.setattr(device_auth, "authenticate_device", _authed(CONFIG_READ))

        resp = client.get(
            "/api/v1/edge/config/poll",
            headers={"Authorization": "Bearer device-token"},
        )
        for cam in resp.get_json()["cameras"]:
            assert "username" not in cam
            assert "password" not in cam
            assert "password_encrypted" not in cam

    def test_device_not_authorized_returns_401(self, client, monkeypatch):
        monkeypatch.setattr(device_auth, "authenticate_device", lambda req: None)
        resp = client.get(
            "/api/v1/edge/config/poll",
            headers={"Authorization": "Bearer revogado"},
        )
        assert resp.status_code == 401

    def test_device_without_config_read_scope_returns_403(self, client, monkeypatch):
        """S1: device autenticado mas SEM config:read → 403 (menor privilégio)."""
        camera_repo = MagicMock()
        monkeypatch.setattr(edge_routes, "_get_camera_repo", lambda: camera_repo)
        # Token só com heartbeat:write não pode ler config
        monkeypatch.setattr(
            device_auth, "authenticate_device", _authed(HEARTBEAT_WRITE)
        )
        resp = client.get(
            "/api/v1/edge/config/poll",
            headers={"Authorization": "Bearer so-heartbeat"},
        )
        assert resp.status_code == 403
        camera_repo.list_for_site_config.assert_not_called()


class TestListForSiteConfigSql:
    """SELECT enxuto: NUNCA username/password na query enviada ao edge (C-05)."""

    @staticmethod
    def _repo_with_cursor():
        cur = MagicMock()
        cur.fetchall.return_value = []

        @contextmanager
        def _conn_ctx():
            conn = MagicMock()
            conn.cursor.return_value = cur
            yield conn

        pool = MagicMock()
        pool.get_connection.side_effect = _conn_ctx
        return CameraRepository(pool), cur

    def test_select_excludes_credentials(self):
        repo, cur = self._repo_with_cursor()
        repo.list_for_site_config(SITE_ID, TENANT)
        query = cur.execute.call_args[0][0].lower()
        assert "password" not in query
        assert "username" not in query
        assert "fps_target" in query
        assert "quality_preset" in query
        assert "tenant_id = %s" in query
        assert "site_id = %s" in query

    def test_params_are_site_and_tenant(self):
        repo, cur = self._repo_with_cursor()
        repo.list_for_site_config(SITE_ID, TENANT)
        assert cur.execute.call_args[0][1] == (SITE_ID, TENANT)


def test_config_poll_route_registered(app):
    """Rota registrada no blueprint /api/v1/edge (zero rota quebrada)."""
    rules = {str(r) for r in app.url_map.iter_rules()}
    assert "/api/v1/edge/config/poll" in rules


class TestConfigPollVersioning:
    """F1: config_version + ETag + 304 (If-None-Match)."""

    def _setup(self, monkeypatch, cameras):
        camera_repo = MagicMock()
        camera_repo.list_for_site_config.return_value = cameras
        monkeypatch.setattr(edge_routes, "_get_camera_repo", lambda: camera_repo)
        # Rota agora está atrás do decorator require_device_scope → mock em authenticate_device
        monkeypatch.setattr(device_auth, "authenticate_device", _authed(CONFIG_READ))

    def test_200_returns_etag_and_config_version(self, client, monkeypatch):
        self._setup(monkeypatch, [_camera_config_row()])
        resp = client.get(
            "/api/v1/edge/config/poll", headers={"Authorization": "Bearer d"}
        )
        assert resp.status_code == 200
        assert resp.headers.get("ETag")
        assert resp.get_json()["config_version"]

    def test_if_none_match_returns_304(self, client, monkeypatch):
        self._setup(monkeypatch, [_camera_config_row()])
        first = client.get(
            "/api/v1/edge/config/poll", headers={"Authorization": "Bearer d"}
        )
        etag = first.headers["ETag"]
        second = client.get(
            "/api/v1/edge/config/poll",
            headers={"Authorization": "Bearer d", "If-None-Match": etag},
        )
        assert second.status_code == 304
        assert second.headers["ETag"] == etag
        assert second.get_data(as_text=True) == ""

    def test_changed_config_changes_etag(self, client, monkeypatch):
        self._setup(monkeypatch, [_camera_config_row()])
        first = client.get(
            "/api/v1/edge/config/poll", headers={"Authorization": "Bearer d"}
        )
        etag1 = first.headers["ETag"]
        # Config muda (fps diferente) → ETag muda → não é 304
        changed = _camera_config_row()
        changed["fps_target"] = 30
        self._setup(monkeypatch, [changed])
        second = client.get(
            "/api/v1/edge/config/poll",
            headers={"Authorization": "Bearer d", "If-None-Match": etag1},
        )
        assert second.status_code == 200
        assert second.headers["ETag"] != etag1
