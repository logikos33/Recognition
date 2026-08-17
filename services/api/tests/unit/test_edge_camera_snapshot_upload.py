"""
Unit — POST /api/v1/edge/cameras/<camera_id>/snapshot (Bloco A: miniatura de
triagem). Device auth (escopo snapshot:write), multipart `file`, sobe pro R2
e atualiza o cache Redis (camera_snapshot_state) que
GET /api/cameras/<id>/snapshot lê.
"""
import io
from unittest.mock import MagicMock

import app.api.v1.edge.routes as edge_routes
import app.core.device_auth as device_auth

TENANT = "11111111-1111-1111-1111-111111111111"
SITE_ID = "55555555-5555-5555-5555-555555555555"
DEVICE_ID = "pandora-rvb-agent"
CAMERA_ID = "44444444-4444-4444-4444-444444444444"

SNAPSHOT_WRITE = "snapshot:write"
FRAMES_WRITE = "frames:write"


def _authed(*scopes: str):
    granted = list(scopes) or [SNAPSHOT_WRITE]
    return lambda req: (TENANT, SITE_ID, DEVICE_ID, granted)


def _tiny_jpeg_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (16, 12), color=(10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def _setup(monkeypatch, *, camera_found=True):
    camera_repo = MagicMock()
    camera_repo.get_by_id_and_tenant.return_value = {"id": CAMERA_ID} if camera_found else None
    monkeypatch.setattr(edge_routes, "_get_camera_repo", lambda: camera_repo)

    storage = MagicMock()
    import app.infrastructure.storage.local_storage as local_storage_mod
    monkeypatch.setattr(local_storage_mod, "get_storage", lambda *a, **k: storage)

    redis_client = MagicMock()
    monkeypatch.setattr(edge_routes, "_get_redis", lambda: redis_client)

    return camera_repo, storage, redis_client


def _post_snapshot(client, *, file_bytes=None, filename="snapshot.jpg"):
    data = {}
    if file_bytes is not None:
        data["file"] = (io.BytesIO(file_bytes), filename)
    return client.post(
        f"/api/v1/edge/cameras/{CAMERA_ID}/snapshot",
        data=data,
        headers={"Authorization": "Bearer d"},
        content_type="multipart/form-data",
    )


def test_no_token_returns_401(client):
    resp = client.post(f"/api/v1/edge/cameras/{CAMERA_ID}/snapshot")
    assert resp.status_code == 401


def test_wrong_scope_returns_403(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    resp = _post_snapshot(client, file_bytes=_tiny_jpeg_bytes())
    assert resp.status_code == 403


def test_missing_file_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(SNAPSHOT_WRITE))
    _setup(monkeypatch)
    resp = _post_snapshot(client, file_bytes=None)
    assert resp.status_code == 422


def test_empty_file_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(SNAPSHOT_WRITE))
    _setup(monkeypatch)
    resp = _post_snapshot(client, file_bytes=b"")
    assert resp.status_code == 422


def test_invalid_image_bytes_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(SNAPSHOT_WRITE))
    _setup(monkeypatch)
    resp = _post_snapshot(client, file_bytes=b"not a real jpeg")
    assert resp.status_code == 422


def test_oversized_file_returns_413(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(SNAPSHOT_WRITE))
    _setup(monkeypatch)
    oversized = b"\xff" * (5 * 1024 * 1024 + 1)  # _MAX_SNAPSHOT_BYTES + 1
    resp = _post_snapshot(client, file_bytes=oversized)
    assert resp.status_code == 413


def test_camera_not_found_returns_404(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(SNAPSHOT_WRITE))
    _setup(monkeypatch, camera_found=False)
    resp = _post_snapshot(client, file_bytes=_tiny_jpeg_bytes())
    assert resp.status_code == 404


def test_camera_lookup_is_scoped_to_device_tenant(client, monkeypatch):
    """C-01: cross-tenant camera_id must 404 — lookup uses the DEVICE's own
    tenant (from g.device_ctx/enrollment), never something the path could
    override."""
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(SNAPSHOT_WRITE))
    camera_repo, _, _ = _setup(monkeypatch)
    _post_snapshot(client, file_bytes=_tiny_jpeg_bytes())
    camera_repo.get_by_id_and_tenant.assert_called_once_with(CAMERA_ID, TENANT)


def test_successful_upload_returns_201_with_r2_key(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(SNAPSHOT_WRITE))
    _setup(monkeypatch)
    resp = _post_snapshot(client, file_bytes=_tiny_jpeg_bytes())
    assert resp.status_code == 201
    body = resp.get_json()["data"]
    assert body["r2_key"].startswith(f"snapshots/{TENANT}/{CAMERA_ID}/")
    assert body["r2_key"].endswith(".jpg")


def test_successful_upload_calls_storage_with_correct_content_type(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(SNAPSHOT_WRITE))
    _, storage, _ = _setup(monkeypatch)
    _post_snapshot(client, file_bytes=_tiny_jpeg_bytes())
    args, _ = storage.upload_bytes.call_args
    assert args[2] == "image/jpeg"


def test_successful_upload_writes_ready_state_to_redis_cache(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(SNAPSHOT_WRITE))
    _, storage, redis_client = _setup(monkeypatch)

    resp = _post_snapshot(client, file_bytes=_tiny_jpeg_bytes())

    assert resp.status_code == 201
    redis_client.setex.assert_called_once()
    key, ttl, raw_value = redis_client.setex.call_args[0]
    assert key == f"epi:camera_snapshot:{TENANT}:{CAMERA_ID}"
    import json
    state = json.loads(raw_value)
    assert state["status"] == "ready"
    assert state["r2_key"] == resp.get_json()["data"]["r2_key"]


def test_cache_write_failure_does_not_fail_the_upload(client, monkeypatch):
    """Best-effort: o objeto já subiu pro R2 — uma falha no Redis não pode
    reverter o 201 (GET simplesmente vê 'none' até a próxima captura)."""
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(SNAPSHOT_WRITE))
    _, storage, redis_client = _setup(monkeypatch)
    redis_client.setex.side_effect = ConnectionError("redis down")

    resp = _post_snapshot(client, file_bytes=_tiny_jpeg_bytes())

    assert resp.status_code == 201
    storage.upload_bytes.assert_called_once()


def test_storage_failure_returns_502(client, monkeypatch):
    from app.core.exceptions import StorageError

    monkeypatch.setattr(device_auth, "authenticate_device", _authed(SNAPSHOT_WRITE))
    _, storage, _ = _setup(monkeypatch)
    storage.upload_bytes.side_effect = StorageError("Access Denied")

    resp = _post_snapshot(client, file_bytes=_tiny_jpeg_bytes())

    assert resp.status_code == 502


def test_route_registered(app):
    rules = {str(r) for r in app.url_map.iter_rules()}
    assert "/api/v1/edge/cameras/<camera_id>/snapshot" in rules
