"""
Mutirão 1.4 — guarda edge no start_stream.

PR #250 blindou SÓ o serve_hls contra disparar FFmpeg local quando a câmera
é alimentada pelo edge (câmera atrás de NVR numa LAN isolada — ADR-0020):
start_stream ainda ia direto ao LocalStreamManager.start(), disparando um
FFmpeg condenado (RTSP inalcançável da nuvem) por câmera na abertura da
grade — 25 câmeras, 25 processos mortos.

Fix: start_stream reutiliza a MESMA detecção de edge-fed do serve_hls
(`_is_edge_fed_camera`, extraída em stream_handlers.py) antes de despachar o
LocalStreamManager. Testes abaixo cobrem os três ramos de dispatch:
gateway online / edge-fed / local (cloud_only e câmera comum).
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

VALID_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

_MOD = "app.api.v1.cameras.stream_handlers"
_PATCH_LSM = "app.api.v1.cameras.local_stream_manager.LocalStreamManager"


def _make_token(app, role="operator", tenant_id=None, user_id=None):
    uid = user_id or uuid4()
    tid = tenant_id or str(uuid4())
    with app.app_context():
        token = create_access_token(
            identity=str(uid),
            additional_claims={
                "role": role,
                "tenant_id": tid,
                "tenant_schema": "public",
            },
        )
    return token, uid, tid


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _mock_camera_service():
    svc = MagicMock()
    svc.build_stream_url.return_value = "rtsp://user:pass@192.168.1.50:554/stream1"
    return svc


class TestStartStreamEdgeGuard:
    """Ramo local (gateway offline) — o único afetado pelo mutirão 1.4."""

    def test_edge_fed_camera_skips_local_ffmpeg(self, client, app):
        """Câmera edge-fed: NÃO chama LocalStreamManager.start() e responde
        sucesso com uma hls_url utilizável (é só isso que o frontend lê —
        cameraService.start() só usa res.hls_url)."""
        token, _uid, _tid = _make_token(app)
        redis_text = MagicMock()

        with (
            patch(f"{_MOD}._get_camera_service", return_value=_mock_camera_service()),
            patch(f"{_MOD}._is_admin", return_value=False),
            patch(f"{_MOD}._get_redis", return_value=redis_text),
            patch(f"{_MOD}._is_gateway_online", return_value=False),
            patch(f"{_MOD}._is_edge_fed_camera", return_value=True) as mock_edge_fed,
            patch(_PATCH_LSM) as mock_lsm_cls,
        ):
            resp = client.post(
                f"/api/cameras/{VALID_UUID}/stream/start", headers=_headers(token)
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["dispatch_mode"] == "edge"
        assert body["data"]["hls_url"]  # o único campo de que o player depende
        mock_edge_fed.assert_called_once_with(VALID_UUID)
        mock_lsm_cls.get_instance.assert_not_called()

    def test_non_edge_camera_still_starts_local_ffmpeg(self, client, app):
        """cloud_only / câmera comum: comportamento antigo intacto — FFmpeg
        local ainda dispara quando a câmera NÃO é servida pelo edge."""
        token, _uid, _tid = _make_token(app)
        redis_text = MagicMock()
        mgr = MagicMock()
        mgr.start.return_value = {"status": "started"}

        with (
            patch(f"{_MOD}._get_camera_service", return_value=_mock_camera_service()),
            patch(f"{_MOD}._is_admin", return_value=False),
            patch(f"{_MOD}._get_redis", return_value=redis_text),
            patch(f"{_MOD}._is_gateway_online", return_value=False),
            patch(f"{_MOD}._is_edge_fed_camera", return_value=False),
            patch(_PATCH_LSM + ".get_instance", return_value=mgr),
        ):
            resp = client.post(
                f"/api/cameras/{VALID_UUID}/stream/start", headers=_headers(token)
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["dispatch_mode"] == "local"
        mgr.start.assert_called_once()
        assert mgr.start.call_args.kwargs["camera_id"] == VALID_UUID

    def test_gateway_online_dispatch_unaffected_by_edge_guard(self, client, app):
        """Quando o gateway está online, o dispatch é via pub/sub — esse ramo
        é anterior ao guard de edge e não deve nem consultá-lo."""
        token, _uid, _tid = _make_token(app)
        redis_text = MagicMock()

        with (
            patch(f"{_MOD}._get_camera_service", return_value=_mock_camera_service()),
            patch(f"{_MOD}._is_admin", return_value=False),
            patch(f"{_MOD}._get_redis", return_value=redis_text),
            patch(f"{_MOD}._is_gateway_online", return_value=True),
            patch(f"{_MOD}._is_edge_fed_camera") as mock_edge_fed,
            patch(_PATCH_LSM) as mock_lsm_cls,
        ):
            resp = client.post(
                f"/api/cameras/{VALID_UUID}/stream/start", headers=_headers(token)
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["dispatch_mode"] == "gateway"
        mock_edge_fed.assert_not_called()
        mock_lsm_cls.get_instance.assert_not_called()
        redis_text.publish.assert_called_once()
