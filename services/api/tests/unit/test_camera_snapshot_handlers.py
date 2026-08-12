"""
Unit — GET/POST /api/cameras/<id>/snapshot(/refresh) (Bloco A: miniatura de
triagem, CameraTriagePage).

Cobre: cache fresco vira no-op no refresh, idempotência (não duplica
edge_command pendente), cross-tenant -> 404 (C-01), câmera sem site -> 422,
e leitura do estado (none/pending/ready/failed) com URL presignada.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from flask_jwt_extended import create_access_token

import app.api.v1.cameras.snapshot_handlers as snap_handlers

TENANT = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT = "99999999-9999-9999-9999-999999999999"
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


def _camera(site_id=SITE_ID, channel=7):
    return {
        "id": CAMERA_ID,
        "tenant_id": TENANT,
        "site_id": site_id,
        "channel": channel,
    }


class _FakeRedis:
    """Minimal in-memory stand-in for the text redis client used by
    camera_snapshot_state — real .get()/.setex() semantics, no server."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key):
        return self._store.get(key)

    def setex(self, key, ttl, value):
        self._store[key] = value

    def seed_state(self, tenant_id, camera_id, state: dict) -> None:
        from app.domain.services.camera_snapshot_state import _key
        self._store[_key(tenant_id, camera_id)] = json.dumps(state)


_UNSET = object()  # sentinel: distingue "camera não informada" de "camera=None" (not-found)


def _setup(monkeypatch, camera=_UNSET, redis_client=None, command_repo=None):
    camera_repo = MagicMock()
    camera_repo.get_by_id_and_tenant.return_value = _camera() if camera is _UNSET else camera
    monkeypatch.setattr(snap_handlers, "_get_camera_repo", lambda: camera_repo)

    redis_client = redis_client if redis_client is not None else _FakeRedis()
    monkeypatch.setattr(snap_handlers, "_get_redis", lambda: redis_client)

    if command_repo is None:
        command_repo = MagicMock()
        command_repo.create.return_value = {"id": str(uuid.uuid4()), "status": "pending"}
        command_repo.list_by_site.return_value = []
    monkeypatch.setattr(snap_handlers, "_get_edge_command_repo", lambda: command_repo)

    return camera_repo, redis_client, command_repo


# ── GET /snapshot ────────────────────────────────────────────────────────────

class TestGetCameraSnapshot:
    def test_camera_not_found_returns_404(self, app, client, monkeypatch):
        _setup(monkeypatch, camera=None)
        resp = client.get(f"/api/cameras/{CAMERA_ID}/snapshot", headers=_auth(app))
        assert resp.status_code == 404

    def test_malformed_uuid_returns_422(self, app, client, monkeypatch):
        _setup(monkeypatch)
        resp = client.get("/api/cameras/not-a-uuid/snapshot", headers=_auth(app))
        assert resp.status_code == 422

    def test_never_captured_returns_status_none(self, app, client, monkeypatch):
        _setup(monkeypatch)
        resp = client.get(f"/api/cameras/{CAMERA_ID}/snapshot", headers=_auth(app))
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["status"] == "none"
        assert data["url"] is None

    def test_ready_returns_presigned_url(self, app, client, monkeypatch):
        _, redis_client, _ = _setup(monkeypatch)
        redis_client.seed_state(TENANT, CAMERA_ID, {
            "status": "ready", "r2_key": f"snapshots/{TENANT}/{CAMERA_ID}/123.jpg",
            "captured_at": datetime.now(timezone.utc).isoformat(), "error_reason": None,
        })
        import app.infrastructure.storage.local_storage as local_storage_mod
        from tests.conftest import MockStorageStrategy
        monkeypatch.setattr(local_storage_mod, "get_storage", lambda *a, **k: MockStorageStrategy())

        resp = client.get(f"/api/cameras/{CAMERA_ID}/snapshot", headers=_auth(app))

        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["status"] == "ready"
        assert data["url"].startswith("https://mock-r2.test/download/")

    def test_failed_returns_error_reason(self, app, client, monkeypatch):
        _, redis_client, _ = _setup(monkeypatch)
        redis_client.seed_state(TENANT, CAMERA_ID, {
            "status": "failed", "r2_key": None, "captured_at": None,
            "error_reason": "Canal sem sinal",
        })
        resp = client.get(f"/api/cameras/{CAMERA_ID}/snapshot", headers=_auth(app))
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["status"] == "failed"
        assert data["error_reason"] == "Canal sem sinal"
        assert data["url"] is None

    def test_cross_tenant_returns_404_not_403(self, app, client, monkeypatch):
        """C-01: câmera de outro tenant nunca vaza existência."""
        camera_repo = MagicMock()
        camera_repo.get_by_id_and_tenant.return_value = None  # repo já filtra por tenant
        monkeypatch.setattr(snap_handlers, "_get_camera_repo", lambda: camera_repo)
        monkeypatch.setattr(snap_handlers, "_get_redis", lambda: _FakeRedis())

        resp = client.get(f"/api/cameras/{CAMERA_ID}/snapshot", headers=_auth(app))

        assert resp.status_code == 404
        camera_repo.get_by_id_and_tenant.assert_called_once_with(CAMERA_ID, TENANT)


# ── POST /snapshot/refresh ──────────────────────────────────────────────────

class TestRefreshCameraSnapshot:
    def test_camera_not_found_returns_404(self, app, client, monkeypatch):
        _setup(monkeypatch, camera=None)
        resp = client.post(f"/api/cameras/{CAMERA_ID}/snapshot/refresh", headers=_auth(app))
        assert resp.status_code == 404

    def test_camera_without_site_returns_422(self, app, client, monkeypatch):
        _setup(monkeypatch, camera=_camera(site_id=None))
        resp = client.post(f"/api/cameras/{CAMERA_ID}/snapshot/refresh", headers=_auth(app))
        assert resp.status_code == 422

    def test_dispatches_capture_snapshot_command(self, app, client, monkeypatch):
        _, _, command_repo = _setup(monkeypatch)

        resp = client.post(f"/api/cameras/{CAMERA_ID}/snapshot/refresh", headers=_auth(app))

        assert resp.status_code == 202
        data = resp.get_json()["data"]
        assert data == {"status": "pending", "queued": True}
        kwargs = command_repo.create.call_args.kwargs
        assert kwargs["tenant_id"] == TENANT
        assert kwargs["site_id"] == SITE_ID
        assert kwargs["command_type"] == "capture_snapshot"
        assert kwargs["payload"] == {"camera_id": CAMERA_ID, "channel": 7}
        assert kwargs["command_id"].startswith(f"snap:{CAMERA_ID}:")

    def test_dispatch_writes_pending_state_so_get_reflects_it(self, app, client, monkeypatch):
        """Bug real corrigido: sem marcar 'pending' no cache, GET continuava
        reportando o resultado da captura ANTERIOR até o edge responder — o
        polling do frontend parava cedo demais achando que já tinha um
        resultado novo."""
        _setup(monkeypatch)

        resp = client.post(f"/api/cameras/{CAMERA_ID}/snapshot/refresh", headers=_auth(app))
        assert resp.status_code == 202

        get_resp = client.get(f"/api/cameras/{CAMERA_ID}/snapshot", headers=_auth(app))
        assert get_resp.status_code == 200
        assert get_resp.get_json()["data"]["status"] == "pending"

    def test_dispatch_over_stale_ready_keeps_old_image_visible_as_pending(
        self, app, client, monkeypatch,
    ):
        """Enquanto a nova captura está em andamento, GET ainda devolve a
        URL da imagem antiga (com status='pending') — a miniatura não
        precisa sumir da tela só porque uma atualização está rolando."""
        _, redis_client, _ = _setup(monkeypatch)
        stale = datetime.now(timezone.utc) - timedelta(minutes=30)
        redis_client.seed_state(TENANT, CAMERA_ID, {
            "status": "ready", "r2_key": "snapshots/old.jpg",
            "captured_at": stale.isoformat(), "error_reason": None,
        })
        import app.infrastructure.storage.local_storage as local_storage_mod
        from tests.conftest import MockStorageStrategy
        monkeypatch.setattr(local_storage_mod, "get_storage", lambda *a, **k: MockStorageStrategy())

        resp = client.post(f"/api/cameras/{CAMERA_ID}/snapshot/refresh", headers=_auth(app))
        assert resp.status_code == 202

        get_resp = client.get(f"/api/cameras/{CAMERA_ID}/snapshot", headers=_auth(app))
        data = get_resp.get_json()["data"]
        assert data["status"] == "pending"
        assert data["url"] is not None
        assert "old.jpg" in data["url"]

    def test_fresh_cache_is_a_no_op(self, app, client, monkeypatch):
        """Cache com < 10 min -> refresh nunca bate no gravador."""
        _, redis_client, command_repo = _setup(monkeypatch)
        redis_client.seed_state(TENANT, CAMERA_ID, {
            "status": "ready", "r2_key": "snapshots/x.jpg",
            "captured_at": datetime.now(timezone.utc).isoformat(), "error_reason": None,
        })

        resp = client.post(f"/api/cameras/{CAMERA_ID}/snapshot/refresh", headers=_auth(app))

        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["status"] == "ready"
        assert data["queued"] is False
        assert data["reason"] == "fresh"
        command_repo.create.assert_not_called()

    def test_stale_cache_dispatches_new_capture(self, app, client, monkeypatch):
        """Cache com status ready mas capturado há > 10 min -> dispara de novo."""
        _, redis_client, command_repo = _setup(monkeypatch)
        stale = datetime.now(timezone.utc) - timedelta(minutes=30)
        redis_client.seed_state(TENANT, CAMERA_ID, {
            "status": "ready", "r2_key": "snapshots/x.jpg",
            "captured_at": stale.isoformat(), "error_reason": None,
        })

        resp = client.post(f"/api/cameras/{CAMERA_ID}/snapshot/refresh", headers=_auth(app))

        assert resp.status_code == 202
        command_repo.create.assert_called_once()

    def test_already_pending_does_not_duplicate_command(self, app, client, monkeypatch):
        command_repo = MagicMock()
        command_repo.list_by_site.return_value = [
            {
                "command_type": "capture_snapshot",
                "payload": {"camera_id": CAMERA_ID, "channel": 7},
                "status": "pending",
            }
        ]
        _, _, command_repo = _setup(monkeypatch, command_repo=command_repo)

        resp = client.post(f"/api/cameras/{CAMERA_ID}/snapshot/refresh", headers=_auth(app))

        assert resp.status_code == 202
        data = resp.get_json()["data"]
        assert data == {"status": "pending", "queued": False, "reason": "already_pending"}
        command_repo.create.assert_not_called()

    def test_pending_capture_for_a_different_camera_does_not_block(self, app, client, monkeypatch):
        command_repo = MagicMock()
        command_repo.list_by_site.return_value = [
            {
                "command_type": "capture_snapshot",
                "payload": {"camera_id": "other-camera", "channel": 1},
                "status": "pending",
            }
        ]
        _, _, command_repo = _setup(monkeypatch, command_repo=command_repo)

        resp = client.post(f"/api/cameras/{CAMERA_ID}/snapshot/refresh", headers=_auth(app))

        assert resp.status_code == 202
        command_repo.create.assert_called_once()

    def test_dispatch_failure_returns_500(self, app, client, monkeypatch):
        command_repo = MagicMock()
        command_repo.list_by_site.return_value = []
        command_repo.create.side_effect = RuntimeError("db down")
        _setup(monkeypatch, command_repo=command_repo)

        resp = client.post(f"/api/cameras/{CAMERA_ID}/snapshot/refresh", headers=_auth(app))

        assert resp.status_code == 500

    def test_cross_tenant_returns_404(self, app, client, monkeypatch):
        camera_repo = MagicMock()
        camera_repo.get_by_id_and_tenant.return_value = None
        monkeypatch.setattr(snap_handlers, "_get_camera_repo", lambda: camera_repo)

        resp = client.post(f"/api/cameras/{CAMERA_ID}/snapshot/refresh", headers=_auth(app))

        assert resp.status_code == 404


def test_routes_registered(app):
    rules = {str(r) for r in app.url_map.iter_rules()}
    assert "/api/cameras/<camera_id>/snapshot" in rules
    assert "/api/cameras/<camera_id>/snapshot/refresh" in rules
