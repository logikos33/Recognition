"""Testes — GET /api/v1/admin/introspection (mutirão item 1.2).

Cobre:
  - Role-gate: 401 sem token, 403 para role fora de admin/superadmin
  - 200 com payload completo (todos os campos esperados presentes)
  - requests_served incrementa por requisição (before_app_request)
  - storage_backend deriva de type(get_storage()).__name__
  - live_view: Redis indisponível → degrada (campos None + degraded=true),
    mas a rota ainda responde 200
  - live_view: Redis disponível → agrega segments_buffered/bytes_buffered/
    streams_active via SCAN (nunca KEYS)
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

_MOD = "app.api.v1.admin.introspection_routes"


def _auth_header(app, role: str = "admin") -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": "00000000-0000-0000-0000-000000000001",
                "tenant_schema": "public",
                "role": role,
            },
        )
    return {"Authorization": f"Bearer {token}"}


class TestAuthorization:
    def test_no_token_returns_401(self, client):
        resp = client.get("/api/v1/admin/introspection")
        assert resp.status_code == 401

    def test_operator_role_returns_403(self, app, client):
        resp = client.get(
            "/api/v1/admin/introspection",
            headers=_auth_header(app, role="operator"),
        )
        assert resp.status_code == 403

    def test_admin_role_passes_gate(self, app, client):
        with patch(f"{_MOD}._live_view_snapshot", return_value={"degraded": False}):
            resp = client.get(
                "/api/v1/admin/introspection",
                headers=_auth_header(app, role="admin"),
            )
        assert resp.status_code == 200

    def test_superadmin_role_passes_gate(self, app, client):
        with patch(f"{_MOD}._live_view_snapshot", return_value={"degraded": False}):
            resp = client.get(
                "/api/v1/admin/introspection",
                headers=_auth_header(app, role="superadmin"),
            )
        assert resp.status_code == 200


class TestPayloadShape:
    def test_full_payload_present(self, app, client):
        with patch(
            f"{_MOD}._live_view_snapshot",
            return_value={
                "segments_buffered": 0,
                "bytes_buffered": 0,
                "avg_segment_bytes": 0,
                "streams_active": 0,
                "degraded": False,
            },
        ):
            resp = client.get(
                "/api/v1/admin/introspection",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        data = resp.get_json()["data"]

        assert "ru_maxrss" in data
        assert isinstance(data["ru_maxrss"], int)
        assert isinstance(data["ru_maxrss_mb"], float)
        assert data["ru_maxrss_mb"] > 0
        assert "rss_current_mb" in data  # None fora do Linux, mas a chave existe
        assert data["uptime_seconds"] >= 0
        assert isinstance(data["requests_served"], int)
        assert data["requests_served"] >= 1
        assert data["storage_backend"] in ("r2", "local", "desconhecido")
        assert data["worker_class"] in ("gevent", "sync/desconhecido")
        assert "service_type" in data
        assert data["live_view"]["degraded"] is False

    def test_requests_served_increments_across_calls(self, app, client):
        with patch(f"{_MOD}._live_view_snapshot", return_value={"degraded": False}):
            first = client.get(
                "/api/v1/admin/introspection", headers=_auth_header(app)
            ).get_json()["data"]["requests_served"]
            second = client.get(
                "/api/v1/admin/introspection", headers=_auth_header(app)
            ).get_json()["data"]["requests_served"]
        assert second > first


class TestStorageBackend:
    def test_storage_backend_r2(self, app, client):
        fake_r2 = MagicMock()
        fake_r2.__class__.__name__ = "R2Storage"
        with patch(f"{_MOD}._live_view_snapshot", return_value={"degraded": False}), \
             patch("app.infrastructure.storage.local_storage.get_storage", return_value=fake_r2):
            resp = client.get(
                "/api/v1/admin/introspection", headers=_auth_header(app)
            )
        assert resp.get_json()["data"]["storage_backend"] == "r2"

    def test_storage_backend_local(self, app, client, tmp_path):
        from app.infrastructure.storage.local_storage import LocalStorage

        with patch(f"{_MOD}._live_view_snapshot", return_value={"degraded": False}), \
             patch(
                 "app.infrastructure.storage.local_storage.get_storage",
                 return_value=LocalStorage(base_dir=str(tmp_path / "introspection-test")),
             ):
            resp = client.get(
                "/api/v1/admin/introspection", headers=_auth_header(app)
            )
        assert resp.get_json()["data"]["storage_backend"] == "local"

    def test_storage_backend_degrades_to_desconhecido_on_error(self, app, client):
        with patch(f"{_MOD}._live_view_snapshot", return_value={"degraded": False}), \
             patch(
                 "app.infrastructure.storage.local_storage.get_storage",
                 side_effect=Exception("credenciais parciais"),
             ):
            resp = client.get(
                "/api/v1/admin/introspection", headers=_auth_header(app)
            )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["storage_backend"] == "desconhecido"


class TestLiveView:
    def test_redis_down_returns_degraded_but_200(self, app, client):
        with patch(f"{_MOD}._get_redis", side_effect=Exception("redis down")):
            resp = client.get(
                "/api/v1/admin/introspection", headers=_auth_header(app)
            )
        assert resp.status_code == 200
        live_view = resp.get_json()["data"]["live_view"]
        assert live_view["degraded"] is True
        assert live_view["segments_buffered"] is None
        assert live_view["bytes_buffered"] is None
        assert live_view["streams_active"] is None

    def test_redis_up_aggregates_segments_and_streams(self, app, client):
        fake_redis = MagicMock()

        def _scan(cursor, match=None, count=100):
            if match == "epi:edge_hls:*":
                if cursor == 0:
                    return 1, ["epi:edge_hls:cam1:stream.m3u8", "epi:edge_hls:cam1:seg1.ts"]
                return 0, []
            if match == "epi:stream:*:active":
                return 0, ["epi:stream:cam1:active"]
            return 0, []

        fake_redis.scan = MagicMock(side_effect=_scan)
        fake_redis.strlen = MagicMock(return_value=500)

        with patch(f"{_MOD}._get_redis", return_value=fake_redis):
            resp = client.get(
                "/api/v1/admin/introspection", headers=_auth_header(app)
            )
        assert resp.status_code == 200
        live_view = resp.get_json()["data"]["live_view"]
        assert live_view["degraded"] is False
        assert live_view["segments_buffered"] == 2
        assert live_view["bytes_buffered"] == 1000
        assert live_view["avg_segment_bytes"] == 500
        assert live_view["streams_active"] == 1
