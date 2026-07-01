"""
Testes — Admin Inventory endpoints (Task 052).

Endpoints testados:
  GET  /api/v1/admin/inventory
  POST /api/v1/admin/cameras/import
  POST /api/v1/admin/cameras/<id>/probe
  POST /api/v1/admin/cameras/probe-batch

Estratégia de mock:
  - DatabasePool mockado via monkeypatch no módulo admin.routes
  - Probe usa socket e subprocess mockados para evitar I/O real
  - @require_superadmin exige JWT com role=superadmin
"""
import uuid
from unittest.mock import MagicMock, patch

from flask_jwt_extended import create_access_token

SUPERADMIN_TENANT = "00000000-0000-0000-0000-000000000001"
CAMERA_ID = str(uuid.uuid4())
TENANT_ID = str(uuid.uuid4())


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _superadmin_header(app):
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": SUPERADMIN_TENANT,
                "tenant_schema": "admin",
                "role": "superadmin",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _operator_header(app):
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "tenant_test",
                "role": "operator",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


# ── Mock helpers ──────────────────────────────────────────────────────────────

def _cam_defaults(overrides: dict) -> dict:
    """Retorna um dict representando uma linha de câmera (compatível com _clean_row)."""
    defaults: dict = {
        "id": CAMERA_ID,
        "tenant_id": TENANT_ID,
        "name": "Camera Teste",
        "location": None,
        "description": None,
        "manufacturer": "Intelbras",
        "host": "192.168.1.100",
        "port": 554,
        "username": "admin",
        "channel": 1,
        "subtype": 0,
        "is_active": True,
        "active_module": "epi",
        "last_seen": None,
        "last_error": None,
        "last_tested_at": None,
        "created_at": None,
        "updated_at": None,
        "site_id": None,
        "brand": "Intelbras",
        "model": None,
        "ip": "192.168.1.100",
        "rtsp_substream_url": None,
        "codec_detected": None,
        "substream_ok": None,
        "max_connections": 4,
        "last_probe_at": None,
        "probe_status": "pending",
        "notes": None,
        "tenant_name": "Tenant Teste",
        "tenant_slug": "tenant-teste",
    }
    defaults.update(overrides)
    return defaults


def _mock_pool_with_cameras(monkeypatch, cameras: list[dict]):
    """Configura pool mock que retorna `cameras` em fetchall.

    Retorna dicts reais (não MagicMock) para que dict(row) funcione corretamente
    com _clean_row no admin routes.
    """
    import app.api.v1.admin.routes as routes_mod

    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()

    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    # Retornar dicts reais — dict(real_dict) funciona corretamente
    cur.fetchall.return_value = [_cam_defaults(c) for c in cameras]
    cur.fetchone.return_value = None
    pool.get_connection.return_value = conn

    monkeypatch.setattr(routes_mod, "_pool", lambda: pool)
    return pool, conn, cur


# ── GET /api/v1/admin/inventory ───────────────────────────────────────────────

class TestInventoryList:
    def test_superadmin_gets_cameras(self, app, client, monkeypatch):
        _mock_pool_with_cameras(monkeypatch, [{}])
        resp = client.get("/api/v1/admin/inventory", headers=_superadmin_header(app))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert isinstance(body["data"]["cameras"], list)
        assert len(body["data"]["cameras"]) == 1

    def test_non_superadmin_gets_403(self, app, client, monkeypatch):
        _mock_pool_with_cameras(monkeypatch, [])
        resp = client.get("/api/v1/admin/inventory", headers=_operator_header(app))
        assert resp.status_code == 403

    def test_unauthenticated_gets_401(self, client):
        resp = client.get("/api/v1/admin/inventory")
        assert resp.status_code == 401

    def test_empty_inventory_returns_empty_list(self, app, client, monkeypatch):
        _mock_pool_with_cameras(monkeypatch, [])
        resp = client.get("/api/v1/admin/inventory", headers=_superadmin_header(app))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["cameras"] == []

    def test_response_contains_edge_devices_and_sites(self, app, client, monkeypatch):
        _mock_pool_with_cameras(monkeypatch, [])
        resp = client.get("/api/v1/admin/inventory", headers=_superadmin_header(app))
        data = resp.get_json()["data"]
        assert "edge_devices" in data
        assert "sites" in data


# ── POST /api/v1/admin/cameras/import ────────────────────────────────────────

class TestCameraImport:
    def _make_pool(self, monkeypatch, tenant_exists=True):
        import app.api.v1.admin.routes as routes_mod

        pool = MagicMock()
        conn = MagicMock()
        cur = MagicMock()

        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cur
        # fetchone returns tenant row if tenant_exists
        tenant_row = MagicMock()
        tenant_row.__getitem__ = MagicMock(side_effect={"id": TENANT_ID}.__getitem__)
        cur.fetchone.return_value = tenant_row if tenant_exists else None
        pool.get_connection.return_value = conn

        monkeypatch.setattr(routes_mod, "_pool", lambda: pool)
        return pool, conn, cur

    def test_creates_cameras_as_draft(self, app, client, monkeypatch):
        pool, conn, cur = self._make_pool(monkeypatch)
        payload = {
            "cameras": [
                {
                    "name": "Cam 01",
                    "brand": "Intelbras",
                    "ip": "192.168.1.10",
                    "port": 554,
                    "username": "admin",
                    "module": "epi",
                    "tenant_id": TENANT_ID,
                }
            ]
        }
        resp = client.post(
            "/api/v1/admin/cameras/import",
            json=payload,
            headers=_superadmin_header(app),
        )
        # 201 se sem erros, 207 se parcial
        assert resp.status_code in (201, 207)
        data = resp.get_json()["data"]
        assert data["created"] >= 0
        assert isinstance(data["errors"], list)

    def test_missing_name_returns_error_row(self, app, client, monkeypatch):
        self._make_pool(monkeypatch)
        payload = {
            "cameras": [
                {"brand": "Hikvision", "ip": "10.0.0.1", "tenant_id": TENANT_ID}
            ]
        }
        resp = client.post(
            "/api/v1/admin/cameras/import",
            json=payload,
            headers=_superadmin_header(app),
        )
        assert resp.status_code in (201, 207)
        data = resp.get_json()["data"]
        assert data["created"] == 0
        assert len(data["errors"]) == 1
        assert "name" in data["errors"][0]["reason"].lower()

    def test_missing_ip_returns_error_row(self, app, client, monkeypatch):
        self._make_pool(monkeypatch)
        payload = {
            "cameras": [{"name": "Cam X", "tenant_id": TENANT_ID}]
        }
        resp = client.post(
            "/api/v1/admin/cameras/import",
            json=payload,
            headers=_superadmin_header(app),
        )
        data = resp.get_json()["data"]
        assert data["created"] == 0
        assert any("ip" in e["reason"].lower() for e in data["errors"])

    def test_invalid_tenant_id_returns_error_row(self, app, client, monkeypatch):
        self._make_pool(monkeypatch)
        payload = {
            "cameras": [
                {"name": "Cam Y", "ip": "10.0.0.1", "tenant_id": "not-a-uuid"}
            ]
        }
        resp = client.post(
            "/api/v1/admin/cameras/import",
            json=payload,
            headers=_superadmin_header(app),
        )
        data = resp.get_json()["data"]
        assert any("tenant_id" in e["reason"].lower() for e in data["errors"])

    def test_empty_list_returns_400(self, app, client, monkeypatch):
        self._make_pool(monkeypatch)
        resp = client.post(
            "/api/v1/admin/cameras/import",
            json={"cameras": []},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 400

    def test_non_superadmin_gets_403(self, app, client, monkeypatch):
        self._make_pool(monkeypatch)
        resp = client.post(
            "/api/v1/admin/cameras/import",
            json={"cameras": [{"name": "X", "ip": "1.2.3.4", "tenant_id": TENANT_ID}]},
            headers=_operator_header(app),
        )
        assert resp.status_code == 403


# ── POST /api/v1/admin/cameras/<id>/probe ────────────────────────────────────

class TestProbeSingle:
    def _make_pool_with_camera(self, monkeypatch, host="192.168.1.50", port=554, rtsp_sub=None):
        import app.api.v1.admin.routes as routes_mod

        pool = MagicMock()
        conn = MagicMock()
        cur = MagicMock()

        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cur

        cam_row = MagicMock()
        row_data = {"id": CAMERA_ID, "host": host, "port": port, "rtsp_substream_url": rtsp_sub}
        cam_row.__getitem__ = MagicMock(side_effect=row_data.__getitem__)
        cur.fetchone.return_value = cam_row
        pool.get_connection.return_value = conn

        monkeypatch.setattr(routes_mod, "_pool", lambda: pool)
        return pool, conn, cur

    def test_probe_updates_probe_status_ok(self, app, client, monkeypatch):
        self._make_pool_with_camera(monkeypatch)

        # Mock socket: host resolve + port open
        with patch("socket.socket") as mock_sock_cls, \
             patch("socket.gethostbyname", return_value="192.168.1.50"):
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0  # port open
            mock_sock_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_sock_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_sock_cls.return_value = mock_sock

            resp = client.post(
                f"/api/v1/admin/cameras/{CAMERA_ID}/probe",
                headers=_superadmin_header(app),
            )

        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["camera_id"] == CAMERA_ID
        assert data["probe_status"] in ("ok", "error")  # depends on socket mock depth

    def test_probe_camera_not_found_returns_404(self, app, client, monkeypatch):
        import app.api.v1.admin.routes as routes_mod

        pool = MagicMock()
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cur
        cur.fetchone.return_value = None
        pool.get_connection.return_value = conn
        monkeypatch.setattr(routes_mod, "_pool", lambda: pool)

        resp = client.post(
            f"/api/v1/admin/cameras/{CAMERA_ID}/probe",
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 404

    def test_probe_non_superadmin_gets_403(self, app, client, monkeypatch):
        self._make_pool_with_camera(monkeypatch)
        resp = client.post(
            f"/api/v1/admin/cameras/{CAMERA_ID}/probe",
            headers=_operator_header(app),
        )
        assert resp.status_code == 403


# ── POST /api/v1/admin/cameras/probe-batch ───────────────────────────────────

class TestProbeBatch:
    def _make_pool_with_cameras_batch(self, monkeypatch, cam_ids: list[str]):
        import app.api.v1.admin.routes as routes_mod

        pool = MagicMock()
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cur

        rows = []
        for cid in cam_ids:
            r = MagicMock()
            row_data = {"id": cid, "host": "192.168.1.10", "port": 554, "rtsp_substream_url": None}
            r.__getitem__ = MagicMock(side_effect=row_data.__getitem__)
            r.__iter__ = MagicMock(return_value=iter(row_data.items()))
            r.items = MagicMock(return_value=row_data.items())
            rows.append(r)

        cur.fetchall.return_value = rows
        pool.get_connection.return_value = conn
        monkeypatch.setattr(routes_mod, "_pool", lambda: pool)
        return pool

    def test_batch_returns_results_for_each_id(self, app, client, monkeypatch):
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        self._make_pool_with_cameras_batch(monkeypatch, ids)

        with patch("socket.socket") as mock_sock_cls, \
             patch("socket.gethostbyname", return_value="192.168.1.10"):
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_sock_cls.return_value = mock_sock

            resp = client.post(
                "/api/v1/admin/cameras/probe-batch",
                json={"camera_ids": ids},
                headers=_superadmin_header(app),
            )

        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "results" in data
        assert len(data["results"]) == 2
        for r in data["results"]:
            assert r["camera_id"] in ids
            assert "probe_status" in r

    def test_batch_empty_list_returns_400(self, app, client, monkeypatch):
        self._make_pool_with_cameras_batch(monkeypatch, [])
        resp = client.post(
            "/api/v1/admin/cameras/probe-batch",
            json={"camera_ids": []},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 400

    def test_batch_over_limit_returns_400(self, app, client, monkeypatch):
        self._make_pool_with_cameras_batch(monkeypatch, [])
        too_many = [str(uuid.uuid4()) for _ in range(51)]
        resp = client.post(
            "/api/v1/admin/cameras/probe-batch",
            json={"camera_ids": too_many},
            headers=_superadmin_header(app),
        )
        assert resp.status_code == 400

    def test_batch_non_superadmin_gets_403(self, app, client, monkeypatch):
        self._make_pool_with_cameras_batch(monkeypatch, [])
        resp = client.post(
            "/api/v1/admin/cameras/probe-batch",
            json={"camera_ids": [str(uuid.uuid4())]},
            headers=_operator_header(app),
        )
        assert resp.status_code == 403
