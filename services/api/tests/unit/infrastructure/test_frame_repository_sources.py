"""
Tests: FrameRepository — frames multi-fonte (migration 094, ajuste #3).

Cobre: create() com video_id opcional + novos campos, defaults
retrocompatíveis e create_bulk com dicts (fix do bug de executemany).
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from app.constants import FrameSource
from app.infrastructure.database.repositories.frame_repository import FrameRepository


def _pool_with_cursor(mock_cursor):
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


def _repo(mock_cursor=None):
    cur = mock_cursor or MagicMock()
    return FrameRepository(_pool_with_cursor(cur)), cur


class TestCreateLegacyCompat:
    """Callers legados (video_id, frame_number, filename, ts) seguem funcionando."""

    def test_legacy_call_defaults(self):
        vid = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "frame_number": 0}
        repo, cur = _repo(cur)
        result = repo.create(vid, 0, "frames/u/v/frame_0000.jpg", 1.5)
        assert result["frame_number"] == 0

        params = cur.execute.call_args[0][1]
        assert params["video_id"] == str(vid)
        assert params["frame_number"] == 0
        assert params["filename"] == "frames/u/v/frame_0000.jpg"
        assert params["timestamp_seconds"] == 1.5
        assert params["source"] == "video"     # default
        assert params["r2_key"] == "frames/u/v/frame_0000.jpg"  # = filename
        assert params["tenant_id"] is None     # cai no COALESCE (user/video)
        assert params["module_code"] is None   # COALESCE → 'epi'

    def test_sql_contains_new_columns(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create(uuid4(), 0, "f.jpg")
        query = cur.execute.call_args[0][0]
        for column in ("source", "r2_key", "camera_id", "recorder_id",
                       "width", "height", "model_confidence", "captured_at",
                       "tenant_id", "module_code"):
            assert column in query


class TestCreateMultiSource:
    def test_upload_frame_without_video(self):
        """Frames de upload não têm vídeo pai (video_id NULL — 094)."""
        cur = MagicMock()
        cur.fetchone.return_value = {"id": str(uuid4()), "source": "upload"}
        repo, cur = _repo(cur)
        tenant = uuid4()
        result = repo.create(
            None, 0, "training-images/t/upload/x.jpg",
            source=FrameSource.UPLOAD,
            width=1920,
            height=1080,
            tenant_id=tenant,
            module_code="epi",
        )
        assert result["source"] == "upload"
        params = cur.execute.call_args[0][1]
        assert params["video_id"] is None
        assert params["source"] == "upload"
        assert params["width"] == 1920
        assert params["height"] == 1080
        assert params["tenant_id"] == str(tenant)
        assert params["module_code"] == "epi"

    def test_auto_capture_frame(self):
        """Auto-captura grava camera_id, model_confidence e captured_at."""
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        cam = uuid4()
        captured = datetime(2026, 7, 1, tzinfo=timezone.utc)
        repo.create(
            None, 0, "evidence/cam/x.jpg",
            source=FrameSource.AUTO,
            r2_key="evidence/cam/x.jpg",
            camera_id=cam,
            model_confidence=0.42,
            captured_at=captured,
        )
        params = cur.execute.call_args[0][1]
        assert params["source"] == "auto"
        assert params["camera_id"] == str(cam)
        assert params["model_confidence"] == 0.42
        assert params["captured_at"] == captured

    def test_nvr_frame_with_recorder(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        rec = uuid4()
        repo.create(
            None, 3, "training-images/t/nvr/r/x.jpg",
            source=FrameSource.NVR,
            recorder_id=rec,
        )
        params = cur.execute.call_args[0][1]
        assert params["source"] == "nvr"
        assert params["recorder_id"] == str(rec)


class TestCreateBulk:
    def test_bulk_passes_dicts(self):
        """Fix do bug latente: lista de dicts (não tuplas) para executemany."""
        cur = MagicMock()
        cur.rowcount = 2
        repo, cur = _repo(cur)
        vid = uuid4()
        count = repo.create_bulk([
            {"video_id": vid, "frame_number": 0, "filename": "a.jpg"},
            {"video_id": vid, "frame_number": 1, "filename": "b.jpg",
             "source": FrameSource.UPLOAD, "width": 640, "height": 480},
        ])
        assert count == 2
        params_list = cur.executemany.call_args[0][1]
        assert all(isinstance(p, dict) for p in params_list)
        assert params_list[0]["source"] == "video"
        assert params_list[1]["source"] == "upload"
        assert params_list[1]["width"] == 640

    def test_bulk_defaults_r2_key_to_filename(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.create_bulk([{"frame_number": 0, "filename": "frames/a.jpg"}])
        params_list = cur.executemany.call_args[0][1]
        assert params_list[0]["r2_key"] == "frames/a.jpg"
        assert params_list[0]["video_id"] is None

    def test_bulk_named_placeholders_in_sql(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.create_bulk([{"frame_number": 0, "filename": "a.jpg"}])
        query = cur.executemany.call_args[0][0]
        assert "%(video_id)s" in query
        assert "%(tenant_id)s" in query
        assert "%(module_code)s" in query


class TestTenantFallback:
    """Achado da revisão: frames nasciam com tenant_id NULL (invisíveis às
    queries tenant-scoped de auto-training/active-learning). O INSERT usa
    COALESCE(explícito, tenant do user_id, tenant do dono do vídeo)."""

    def _sql_and_params(self, cur):
        return cur.execute.call_args[0]

    def test_sql_has_tenant_coalesce_chain(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create(uuid4(), 0, "frames/u/v/frame_0000.jpg", 1.0)
        sql, _ = self._sql_and_params(cur)
        assert "COALESCE(%(tenant_id)s::uuid" in sql
        assert "SELECT tenant_id FROM users WHERE id = %(user_id)s::uuid" in sql
        assert "JOIN users u ON u.id = v.user_id" in sql

    def test_extraction_caller_passes_user_id(self):
        """extraction.py resolve o tenant via user_id — o param chega ao SQL."""
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        user = uuid4()
        repo.create(uuid4(), 0, "frames/u/v/frame_0000.jpg", 1.0, user_id=user)
        _, params = self._sql_and_params(cur)
        assert params["user_id"] == str(user)
        assert params["tenant_id"] is None  # derivado no banco, não no app

    def test_bulk_sql_has_tenant_coalesce_chain(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.create_bulk([
            {"video_id": uuid4(), "frame_number": 0, "filename": "a.jpg",
             "user_id": uuid4()},
        ])
        sql = cur.executemany.call_args[0][0]
        rows = cur.executemany.call_args[0][1]
        assert "COALESCE(%(tenant_id)s::uuid" in sql
        assert rows[0]["user_id"] is not None
