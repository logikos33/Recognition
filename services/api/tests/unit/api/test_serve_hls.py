"""
Regression tests for serve_hls GR-6a lazy-start (task-059 bugfix).

Root bug: send_from_directory raises werkzeug.exceptions.NotFound (HTTP exception),
NOT FileNotFoundError. The original except FileNotFoundError: block never fired,
so lazy-start was silently skipped and the endpoint always returned plain 404.

Fix: replaced try/except with os.path.isfile() check before send_from_directory.
"""
import logging
from unittest.mock import MagicMock, patch

VALID_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
HLS_URL = f"/api/cameras/{VALID_UUID}/stream/stream.m3u8"

# LocalStreamManager and send_from_directory are imported lazily INSIDE serve_hls,
# so they must be patched at their source module paths.
_PATCH_LSM = "app.api.v1.cameras.local_stream_manager.LocalStreamManager"
_PATCH_SEND = "flask.send_from_directory"
_PATCH_POOL = "app.infrastructure.database.connection.DatabasePool.get_instance"
_PATCH_SVC  = "app.domain.services.camera_service.CameraService"
_PATCH_REPO = "app.infrastructure.database.repositories.camera_repository.CameraRepository"


def _make_mgr(is_running: bool = False, start_status: str = "started") -> MagicMock:
    mgr = MagicMock()
    mgr.is_running.return_value = is_running
    mgr.start.return_value = {"status": start_status}
    mgr.status.return_value = {"running": True, "stderr_tail": None}
    return mgr


_PATCH_BINARY_REDIS = "app.api.v1.cameras.stream_handlers._get_binary_redis"
_PATCH_TEXT_REDIS = "app.api.v1.cameras.stream_handlers._get_redis"


class TestServeHlsEdgePush:
    """LV-1: câmera atrás de NVR — edge empurra segmento pra Redis, serve_hls
    lê de lá ANTES de tentar gateway/LocalStreamManager (RTSP inalcançável
    da nuvem pra essa câmera)."""

    def test_playlist_served_from_edge_buffer_bypasses_local_stream_manager(self, client):
        redis_bin = MagicMock()
        redis_bin.get.return_value = b"#EXTM3U\n#EXT-X-VERSION:3\n"
        redis_text = MagicMock()

        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch(_PATCH_TEXT_REDIS, return_value=redis_text),
            patch(_PATCH_LSM) as mock_lsm_cls,
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 200
        assert resp.data == b"#EXTM3U\n#EXT-X-VERSION:3\n"
        assert resp.headers.get("Content-Type") == "application/vnd.apple.mpegurl"
        redis_bin.get.assert_called_once_with(f"epi:edge_hls:{VALID_UUID}:stream.m3u8")
        redis_text.setex.assert_called_once()  # renews epi:stream:{id}:active
        mock_lsm_cls.get_instance.assert_not_called()

    def test_ts_segment_served_with_video_content_type(self, client):
        redis_bin = MagicMock()
        redis_bin.get.return_value = b"\x47\x00binary-ts-bytes"

        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch(_PATCH_TEXT_REDIS, return_value=MagicMock()),
        ):
            resp = client.get(f"/api/cameras/{VALID_UUID}/stream/segment3.ts")

        assert resp.status_code == 200
        assert resp.data == b"\x47\x00binary-ts-bytes"
        assert resp.headers.get("Content-Type") == "video/mp2t"

    def test_no_edge_buffer_falls_through_to_local_disk_check(self, client):
        """Nada no Redis (edge não está empurrando essa câmera) — comportamento
        idêntico ao caminho pré-LV-1, sem regressão."""
        redis_bin = MagicMock()
        redis_bin.get.return_value = None

        with (
            patch(_PATCH_BINARY_REDIS, return_value=redis_bin),
            patch("os.path.isfile", return_value=True),
            patch(_PATCH_SEND, return_value=__import__("flask").Response("ok", 200)),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 200

    def test_redis_error_falls_through_gracefully(self, client):
        """Redis indisponível — não derruba a rota, só ignora o caminho edge."""
        with (
            patch(_PATCH_BINARY_REDIS, side_effect=ConnectionError("redis down")),
            patch("os.path.isfile", return_value=True),
            patch(_PATCH_SEND, return_value=__import__("flask").Response("ok", 200)),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 200


class TestServeHlsLazyStart:
    """GR-6a: first .m3u8 request when FFmpeg is not running."""

    def test_rtsp_camera_returns_425_and_retry_after(self, client):
        """
        Falha-antes / passa-depois:
        Before fix: except FileNotFoundError never caught werkzeug.exceptions.NotFound
                    → lazy-start skipped → plain 404.
        After fix:  os.path.isfile() returns False → lazy-start runs → 425.
        """
        mgr = _make_mgr(is_running=False, start_status="started")
        mock_pool = MagicMock()
        mock_svc = MagicMock()
        mock_svc.build_stream_url_for_lazy_start.return_value = (
            "rtsp://user:pass@192.168.1.100:554/stream1"
        )

        with (
            patch("os.path.isfile", return_value=False),
            patch(_PATCH_LSM + ".get_instance", return_value=mgr),
            patch(_PATCH_POOL, return_value=mock_pool),
            patch(_PATCH_SVC, return_value=mock_svc),
            patch(_PATCH_REPO, return_value=MagicMock()),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 425, (
            f"Expected 425 (lazy-start fired), got {resp.status_code}. "
            "Root cause: os.path.isfile check missing → lazy-start block unreachable."
        )
        assert resp.headers.get("Retry-After") == "2"

    def test_already_running_returns_425(self, client):
        """Stream already running in this worker but segments not yet on disk → 425."""
        mgr = _make_mgr(is_running=True)

        with (
            patch("os.path.isfile", return_value=False),
            patch(_PATCH_LSM + ".get_instance", return_value=mgr),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 425
        assert resp.headers.get("Retry-After") == "2"


class TestServeHlsFileExists:
    """When the HLS segment file is already on disk, serve it directly."""

    def test_segments_exist_returns_200(self, client):
        """os.path.isfile() → True: send_from_directory is called, lazy-start is skipped."""
        from flask import Response as _Resp

        with (
            patch("os.path.isfile", return_value=True),
            patch(_PATCH_SEND, return_value=_Resp("ok", 200)),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 200


class TestServeHlsNoRtsp:
    """Camera without a valid RTSP URL → 404 with clear message."""

    def test_no_rtsp_camera_returns_404_with_message(self, client):
        """
        build_stream_url_for_lazy_start raises → lazy-start fails →
        404 returned with a non-empty error message (not a silent opaque 404).
        """
        from app.core.exceptions import NotFoundError

        mgr = _make_mgr(is_running=False)
        mock_pool = MagicMock()
        mock_svc = MagicMock()
        mock_svc.build_stream_url_for_lazy_start.side_effect = NotFoundError(
            "Câmera", VALID_UUID
        )

        with (
            patch("os.path.isfile", return_value=False),
            patch(_PATCH_LSM + ".get_instance", return_value=mgr),
            patch(_PATCH_POOL, return_value=mock_pool),
            patch(_PATCH_SVC, return_value=mock_svc),
            patch(_PATCH_REPO, return_value=MagicMock()),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 404
        body = resp.get_json()
        assert body is not None
        assert body.get("success") is False
        assert body.get("error")  # non-empty message

    def test_pool_none_returns_404_and_logs_warning(self, client, caplog):
        """
        DatabasePool.get_instance() returns None → warning logged with
        reason=db_pool_not_initialized, and 404 returned (not a silent 404).
        """
        mgr = _make_mgr(is_running=False)

        with (
            patch("os.path.isfile", return_value=False),
            patch(_PATCH_LSM + ".get_instance", return_value=mgr),
            patch(_PATCH_POOL, return_value=None),
            caplog.at_level(logging.WARNING),
        ):
            resp = client.get(HLS_URL)

        assert resp.status_code == 404
        assert any("db_pool_not_initialized" in r.message for r in caplog.records)
