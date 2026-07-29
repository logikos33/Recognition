"""
Unit — POST /api/v1/edge/frames (Onda 2, shadow mode on-site).

Edge (na LAN do NVR, ADR-0020) sobe um frame extraído localmente pro pool de
anotação — mesmo destino que nvr_extraction.py produz (storage +
training_frames source='nvr'), só troca quem inicia o upload.
"""
import io
from unittest.mock import MagicMock

import app.api.v1.edge.routes as edge_routes
import app.core.device_auth as device_auth

TENANT = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT = "99999999-9999-9999-9999-999999999999"
SITE_ID = "55555555-5555-5555-5555-555555555555"
DEVICE_ID = "pandora-rvb-agent"
CAMERA_ID = "44444444-4444-4444-4444-444444444444"
RECORDER_ID = "33333333-3333-3333-3333-333333333333"

FRAMES_WRITE = "frames:write"
CONFIG_READ = "config:read"


def _authed(*scopes: str):
    granted = list(scopes) or [FRAMES_WRITE]
    return lambda req: (TENANT, SITE_ID, DEVICE_ID, granted)


def _tiny_jpeg_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (16, 12), color=(10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def _setup_repos(monkeypatch, *, camera_found=True, recorder_found=True, frame_row=None):
    camera_repo = MagicMock()
    camera_repo.get_by_id_and_tenant.return_value = {"id": CAMERA_ID} if camera_found else None
    recorder_repo = MagicMock()
    recorder_repo.get_by_id.return_value = {"id": RECORDER_ID} if recorder_found else None
    frame_repo = MagicMock()
    frame_repo.create.return_value = frame_row or {"id": "frame-pk-1"}

    monkeypatch.setattr(edge_routes, "_get_camera_repo", lambda: camera_repo)
    monkeypatch.setattr(edge_routes, "_get_recorder_repo", lambda: recorder_repo)
    monkeypatch.setattr(edge_routes, "_get_frame_repo", lambda: frame_repo)

    storage = MagicMock()
    import app.infrastructure.storage.local_storage as local_storage_mod
    monkeypatch.setattr(local_storage_mod, "get_storage", lambda *a, **k: storage)

    return camera_repo, recorder_repo, frame_repo, storage


def _post_frame(client, *, file_bytes=None, filename="frame.jpg", **form_overrides):
    data = {
        "camera_id": CAMERA_ID,
        "recorder_id": RECORDER_ID,
        **form_overrides,
    }
    if file_bytes is not None:
        data["file"] = (io.BytesIO(file_bytes), filename)
    return client.post(
        "/api/v1/edge/frames",
        data=data,
        headers={"Authorization": "Bearer d"},
        content_type="multipart/form-data",
    )


def test_no_token_returns_401(client):
    resp = client.post("/api/v1/edge/frames")
    assert resp.status_code == 401


def test_wrong_scope_returns_403(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(CONFIG_READ))
    resp = _post_frame(client, file_bytes=_tiny_jpeg_bytes())
    assert resp.status_code == 403


def test_missing_file_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    resp = _post_frame(client, file_bytes=None)
    assert resp.status_code == 422


def test_bad_extension_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    resp = _post_frame(client, file_bytes=_tiny_jpeg_bytes(), filename="frame.png")
    assert resp.status_code == 422


def test_empty_file_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    resp = _post_frame(client, file_bytes=b"")
    assert resp.status_code == 422


def test_oversized_file_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    oversized = b"\xff" * (10 * 1024 * 1024 + 1)
    resp = _post_frame(client, file_bytes=oversized)
    assert resp.status_code == 422


def test_invalid_image_bytes_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    resp = _post_frame(client, file_bytes=b"not a real jpeg, just garbage bytes")
    assert resp.status_code == 422


def test_missing_camera_id_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    resp = _post_frame(client, file_bytes=_tiny_jpeg_bytes(), camera_id="")
    assert resp.status_code == 422


def test_malformed_uuid_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    resp = _post_frame(client, file_bytes=_tiny_jpeg_bytes(), recorder_id="not-a-uuid")
    assert resp.status_code == 422


def test_bad_captured_at_returns_422(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    resp = _post_frame(client, file_bytes=_tiny_jpeg_bytes(), captured_at="not-a-date")
    assert resp.status_code == 422


def test_camera_not_found_returns_404(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    _setup_repos(monkeypatch, camera_found=False)
    resp = _post_frame(client, file_bytes=_tiny_jpeg_bytes())
    assert resp.status_code == 404


def test_recorder_not_found_returns_404(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    _setup_repos(monkeypatch, recorder_found=False)
    resp = _post_frame(client, file_bytes=_tiny_jpeg_bytes())
    assert resp.status_code == 404


def test_camera_lookup_is_scoped_to_device_tenant(client, monkeypatch):
    """C-01: cross-tenant camera_id must 404, never leak existence — proven by
    asserting the lookup is scoped to the DEVICE's own tenant (from
    g.device_ctx/enrollment), not something the payload could override."""
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    camera_repo, recorder_repo, _, _ = _setup_repos(monkeypatch)
    _post_frame(client, file_bytes=_tiny_jpeg_bytes())
    camera_repo.get_by_id_and_tenant.assert_called_once_with(CAMERA_ID, TENANT)
    recorder_repo.get_by_id.assert_called_once()
    assert str(recorder_repo.get_by_id.call_args.args[1]) == TENANT


def test_successful_upload_returns_201_with_frame_id(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    _setup_repos(monkeypatch, frame_row={"id": "frame-abc"})
    resp = _post_frame(client, file_bytes=_tiny_jpeg_bytes())
    assert resp.status_code == 201
    body = resp.get_json()["data"]
    assert body["frame_id"] == "frame-abc"
    assert "r2_key" in body


def test_successful_upload_stores_via_r2_key_convention(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    _, _, _, storage = _setup_repos(monkeypatch)
    resp = _post_frame(client, file_bytes=_tiny_jpeg_bytes())
    assert resp.status_code == 201
    args, kwargs = storage.upload_bytes.call_args
    r2_key = args[0]
    assert r2_key.startswith(f"training-images/{TENANT}/nvr/{RECORDER_ID}/")
    assert r2_key.endswith(".jpg")
    assert args[2] == "image/jpeg"


def test_successful_upload_creates_frame_with_source_nvr(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    _, _, frame_repo, _ = _setup_repos(monkeypatch)
    _post_frame(client, file_bytes=_tiny_jpeg_bytes())
    _, kwargs = frame_repo.create.call_args
    assert str(kwargs["source"]) == "nvr"
    assert str(kwargs["camera_id"]) == CAMERA_ID
    assert str(kwargs["recorder_id"]) == RECORDER_ID
    assert kwargs["tenant_id"] == TENANT
    assert kwargs["width"] == 16
    assert kwargs["height"] == 12


def test_module_code_defaults_to_epi(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    _, _, frame_repo, _ = _setup_repos(monkeypatch)
    _post_frame(client, file_bytes=_tiny_jpeg_bytes())
    _, kwargs = frame_repo.create.call_args
    assert kwargs["module_code"] == "epi"


def test_module_code_can_be_overridden(client, monkeypatch):
    monkeypatch.setattr(device_auth, "authenticate_device", _authed(FRAMES_WRITE))
    _, _, frame_repo, _ = _setup_repos(monkeypatch)
    _post_frame(client, file_bytes=_tiny_jpeg_bytes(), module_code="quality")
    _, kwargs = frame_repo.create.call_args
    assert kwargs["module_code"] == "quality"


def test_route_registered(app):
    rules = {str(r) for r in app.url_map.iter_rules()}
    assert "/api/v1/edge/frames" in rules
