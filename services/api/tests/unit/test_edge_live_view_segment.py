"""
Unit — POST /api/v1/edge/live-view/<camera_id>/segment (LV-1, live view via push do edge).

Câmera atrás de NVR numa LAN isolada (ADR-0020) — a nuvem nunca alcança a
câmera direto, então o edge roda o FFmpeg local e empurra os segmentos HLS
pra cá. serve_hls (cameras/stream_handlers.py) lê do mesmo buffer Redis.
"""
import io
from unittest.mock import MagicMock

import app.api.v1.edge.routes as edge_routes
import app.core.device_auth as device_auth

TENANT = "11111111-1111-1111-1111-111111111111"
SITE_ID = "55555555-5555-5555-5555-555555555555"
DEVICE_ID = "pandora-rvb-agent"
CAMERA_ID = "44444444-4444-4444-4444-444444444444"

STREAM_WRITE = "stream:write"
CONFIG_READ = "config:read"


def _authed(*scopes: str):
    granted = list(scopes) or [STREAM_WRITE]
    return lambda req: (TENANT, SITE_ID, DEVICE_ID, granted)


def _setup(monkeypatch, *, camera_found=True):
    camera_repo = MagicMock()
    camera_repo.get_by_id_and_tenant.return_value = {"id": CAMERA_ID} if camera_found else None
    monkeypatch.setattr(edge_routes, "_get_camera_repo", lambda: camera_repo)

    redis = MagicMock()
    monkeypatch.setattr(edge_routes, "_get_binary_redis", lambda: redis)
    return camera_repo, redis


def _post_segment(client, *, file_bytes=None, filename="stream.m3u8", **form_overrides):
    data = {**form_overrides}
    if filename is not None:
        data["filename"] = filename
    if file_bytes is not None:
        data["file"] = (io.BytesIO(file_bytes), filename or "segment.ts")
    return client.post(
        f"/api/v1/edge/live-view/{CAMERA_ID}/segment",
        data=data,
        headers={"Authorization": "Bearer d"},
        content_type="multipart/form-data",
    )


def test_no_token_returns_401(client):
    resp = client.post(f"/api/v1/edge/live-view/{CAMERA_ID}/segment")
    assert resp.status_code == 401


def test_wrong_scope_returns_403(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(CONFIG_READ))
    resp = _post_segment(client, file_bytes=b"data")
    assert resp.status_code == 403


def test_invalid_camera_id_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(STREAM_WRITE))
    resp = client.post(
        "/api/v1/edge/live-view/not-a-uuid/segment",
        data={"filename": "stream.m3u8", "file": (io.BytesIO(b"data"), "stream.m3u8")},
        headers={"Authorization": "Bearer d"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 422


def test_camera_not_found_returns_404(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(STREAM_WRITE))
    _setup(monkeypatch, camera_found=False)
    resp = _post_segment(client, file_bytes=b"data")
    assert resp.status_code == 404


def test_camera_lookup_scoped_to_device_tenant(client, monkeypatch):
    """C-01: cross-tenant camera_id must 404 — lookup scoped to the DEVICE's
    own tenant (from enrollment), never the payload."""
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(STREAM_WRITE))
    camera_repo, _ = _setup(monkeypatch)
    _post_segment(client, file_bytes=b"data")
    camera_repo.get_by_id_and_tenant.assert_called_once_with(CAMERA_ID, TENANT)


def test_missing_file_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(STREAM_WRITE))
    _setup(monkeypatch)
    resp = _post_segment(client, file_bytes=None)
    assert resp.status_code == 422


def test_empty_file_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(STREAM_WRITE))
    _setup(monkeypatch)
    resp = _post_segment(client, file_bytes=b"")
    assert resp.status_code == 422


def test_oversized_file_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(STREAM_WRITE))
    _setup(monkeypatch)
    oversized = b"\xff" * (5 * 1024 * 1024 + 1)
    resp = _post_segment(client, file_bytes=oversized)
    assert resp.status_code == 422


def test_missing_filename_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(STREAM_WRITE))
    _setup(monkeypatch)
    resp = client.post(
        f"/api/v1/edge/live-view/{CAMERA_ID}/segment",
        data={"file": (io.BytesIO(b"data"), "")},
        headers={"Authorization": "Bearer d"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 422


def test_path_traversal_filename_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(STREAM_WRITE))
    _setup(monkeypatch)
    resp = _post_segment(client, file_bytes=b"data", filename="../../etc/passwd")
    assert resp.status_code == 422


def test_successful_playlist_upload_returns_201(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(STREAM_WRITE))
    _, redis = _setup(monkeypatch)
    resp = _post_segment(client, file_bytes=b"#EXTM3U\n", filename="stream.m3u8")
    assert resp.status_code == 201
    assert resp.get_json()["data"]["stored"] is True
    redis.setex.assert_called_once()
    args, _ = redis.setex.call_args
    assert args[0] == f"epi:edge_hls:{CAMERA_ID}:stream.m3u8"
    assert args[2] == b"#EXTM3U\n"


def test_successful_segment_upload_stores_with_ttl(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(STREAM_WRITE))
    _, redis = _setup(monkeypatch)
    resp = _post_segment(client, file_bytes=b"\x47ts-bytes", filename="segment5.ts")
    assert resp.status_code == 201
    args, _ = redis.setex.call_args
    assert args[0] == f"epi:edge_hls:{CAMERA_ID}:segment5.ts"
    assert isinstance(args[1], int) and args[1] > 0
    assert args[2] == b"\x47ts-bytes"


def test_redis_error_returns_500(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(STREAM_WRITE))
    camera_repo = MagicMock()
    camera_repo.get_by_id_and_tenant.return_value = {"id": CAMERA_ID}
    monkeypatch.setattr(edge_routes, "_get_camera_repo", lambda: camera_repo)
    redis = MagicMock()
    redis.setex.side_effect = ConnectionError("redis down")
    monkeypatch.setattr(edge_routes, "_get_binary_redis", lambda: redis)

    resp = _post_segment(client, file_bytes=b"data")
    assert resp.status_code == 500


def test_route_registered(app):
    rules = {str(r) for r in app.url_map.iter_rules()}
    assert "/api/v1/edge/live-view/<camera_id>/segment" in rules
