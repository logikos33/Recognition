"""Tests: photo_service.py — PhotoService methods with mocked cv2/numpy."""
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_cv2():
    mock_cv2 = MagicMock()
    mock_cv2.IMWRITE_JPEG_QUALITY = 1
    mock_cv2.IMREAD_COLOR = 1
    mock_cv2.FONT_HERSHEY_SIMPLEX = 0
    mock_cv2.rectangle = MagicMock()
    mock_cv2.putText = MagicMock()
    mock_cv2.imwrite = MagicMock(return_value=True)
    mock_cv2.imdecode.return_value = MagicMock()
    return mock_cv2


def _make_numpy():
    mock_np = MagicMock()
    mock_np.frombuffer.return_value = MagicMock()
    mock_np.uint8 = MagicMock()
    return mock_np


# ---------------------------------------------------------------------------
# save_analysis_photo — cv2 unavailable → returns ("", "")
# ---------------------------------------------------------------------------

class TestSaveAnalysisPhotoNoCv2:

    def test_no_cv2_returns_empty_tuple(self):
        from app.api.v1.quality.photo_service import PhotoService
        svc = PhotoService()
        # cv2 not installed in api venv — ImportError caught → ("", "")
        result = svc.save_analysis_photo(b"fake", [], "cam-001")
        assert result == ("", "")

    def test_no_cv2_does_not_raise(self):
        from app.api.v1.quality.photo_service import PhotoService
        svc = PhotoService()
        svc.save_analysis_photo(b"fake", [{"bbox": [0, 0, 10, 10], "class": "ok", "confidence": 0.9, "is_defect": False}], "cam-001")


# ---------------------------------------------------------------------------
# save_raw_photo — cv2 unavailable → returns ("", "")
# ---------------------------------------------------------------------------

class TestSaveRawPhotoNoCv2:

    def test_no_cv2_returns_empty_tuple(self):
        from app.api.v1.quality.photo_service import PhotoService
        svc = PhotoService()
        result = svc.save_raw_photo(b"fake", "cam-001")
        assert result == ("", "")

    def test_no_cv2_does_not_raise(self):
        from app.api.v1.quality.photo_service import PhotoService
        svc = PhotoService()
        svc.save_raw_photo(b"", "cam-001")


# ---------------------------------------------------------------------------
# save_quality_photo — cv2 unavailable → returns ("", "")
# ---------------------------------------------------------------------------

class TestSaveQualityPhotoNoCv2:

    def test_no_cv2_returns_empty_tuple(self):
        from app.api.v1.quality.photo_service import PhotoService
        svc = PhotoService()
        result = svc.save_quality_photo(b"fake", "cam-001", "PC-123", "OP-456")
        assert result == ("", "")

    def test_optional_work_order_defaults_to_empty(self):
        from app.api.v1.quality.photo_service import PhotoService
        svc = PhotoService()
        result = svc.save_quality_photo(b"fake", "cam-001", "PC-123")
        assert result == ("", "")


# ---------------------------------------------------------------------------
# save_analysis_photo — with mocked cv2 (covers the drawing path)
# ---------------------------------------------------------------------------

class TestSaveAnalysisPhotoWithCv2:

    def test_with_mocked_cv2_returns_path(self, tmp_path):
        mock_cv2 = _make_cv2()
        mock_np = _make_numpy()
        import app.api.v1.quality.photo_service as svc_mod

        with patch.dict(sys.modules, {"cv2": mock_cv2, "numpy": mock_np}), \
             patch.object(svc_mod, "PHOTOS_DIR", tmp_path), \
             patch("app.infrastructure.storage.r2_storage.R2Storage", MagicMock()):
            svc = svc_mod.PhotoService()
            result = svc.save_analysis_photo(b"fake", [], "abcdef12")

        assert result[0] != ""
        assert result[0].endswith(".jpg")

    def test_defect_box_drawn_red(self, tmp_path):
        mock_cv2 = _make_cv2()
        mock_np = _make_numpy()
        import app.api.v1.quality.photo_service as svc_mod

        detection = {"bbox": [10, 20, 100, 200], "class": "no_helmet", "confidence": 0.95, "is_defect": True}

        with patch.dict(sys.modules, {"cv2": mock_cv2, "numpy": mock_np}), \
             patch.object(svc_mod, "PHOTOS_DIR", tmp_path), \
             patch("app.infrastructure.storage.r2_storage.R2Storage", MagicMock()):
            svc = svc_mod.PhotoService()
            svc.save_analysis_photo(b"fake", [detection], "abcdef12")

        # Red box: (0, 0, 255)
        rect_calls = mock_cv2.rectangle.call_args_list
        assert any(str((0, 0, 255)) in str(c) for c in rect_calls)

    def test_non_defect_box_drawn_green(self, tmp_path):
        mock_cv2 = _make_cv2()
        mock_np = _make_numpy()
        import app.api.v1.quality.photo_service as svc_mod

        detection = {"bbox": [10, 20, 100, 200], "class": "helmet", "confidence": 0.95, "is_defect": False}

        with patch.dict(sys.modules, {"cv2": mock_cv2, "numpy": mock_np}), \
             patch.object(svc_mod, "PHOTOS_DIR", tmp_path), \
             patch("app.infrastructure.storage.r2_storage.R2Storage", MagicMock()):
            svc = svc_mod.PhotoService()
            svc.save_analysis_photo(b"fake", [detection], "abcdef12")

        rect_calls = mock_cv2.rectangle.call_args_list
        assert any(str((0, 255, 0)) in str(c) for c in rect_calls)


# ---------------------------------------------------------------------------
# save_raw_photo — with mocked cv2
# ---------------------------------------------------------------------------

class TestSaveRawPhotoWithCv2:

    def test_with_mocked_cv2_returns_path(self, tmp_path):
        mock_cv2 = _make_cv2()
        mock_np = _make_numpy()
        import app.api.v1.quality.photo_service as svc_mod

        with patch.dict(sys.modules, {"cv2": mock_cv2, "numpy": mock_np}), \
             patch.object(svc_mod, "PHOTOS_DIR", tmp_path), \
             patch("app.infrastructure.storage.r2_storage.R2Storage", MagicMock()):
            svc = svc_mod.PhotoService()
            result = svc.save_raw_photo(b"fake", "abcdef12")

        assert result[0].endswith(".jpg")


# ---------------------------------------------------------------------------
# save_quality_photo — with mocked cv2
# ---------------------------------------------------------------------------

class TestSaveQualityPhotoWithCv2:

    def test_with_mocked_cv2_returns_path(self, tmp_path):
        mock_cv2 = _make_cv2()
        mock_np = _make_numpy()
        mock_img = MagicMock()
        mock_img.shape = (480, 640, 3)
        mock_cv2.imdecode.return_value = mock_img

        import app.api.v1.quality.photo_service as svc_mod

        with patch.dict(sys.modules, {"cv2": mock_cv2, "numpy": mock_np}), \
             patch.object(svc_mod, "PHOTOS_DIR", tmp_path), \
             patch("app.infrastructure.storage.r2_storage.R2Storage", MagicMock()):
            svc = svc_mod.PhotoService()
            result = svc.save_quality_photo(b"fake", "abcdef12", "PC-001", "OP-999")

        assert result[0].endswith(".jpg")
        assert "quality" in result[0]

    def test_jpeg_quality_95_passed(self, tmp_path):
        mock_cv2 = _make_cv2()
        mock_np = _make_numpy()
        mock_img = MagicMock()
        mock_img.shape = (480, 640, 3)
        mock_cv2.imdecode.return_value = mock_img

        import app.api.v1.quality.photo_service as svc_mod

        with patch.dict(sys.modules, {"cv2": mock_cv2, "numpy": mock_np}), \
             patch.object(svc_mod, "PHOTOS_DIR", tmp_path), \
             patch("app.infrastructure.storage.r2_storage.R2Storage", MagicMock()):
            svc = svc_mod.PhotoService()
            svc.save_quality_photo(b"fake", "abcdef12", "PC-001")

        # cv2.imwrite should have been called with quality=95 in the params list
        imwrite_calls = mock_cv2.imwrite.call_args_list
        assert any("95" in str(c) for c in imwrite_calls)


# ---------------------------------------------------------------------------
# _save_and_upload — R2 upload skipped when unavailable
# ---------------------------------------------------------------------------

class TestSaveAndUpload:

    def test_r2_upload_failure_returns_empty_r2_key(self, tmp_path):
        mock_cv2 = _make_cv2()
        mock_np = _make_numpy()
        import app.api.v1.quality.photo_service as svc_mod

        with patch.dict(sys.modules, {"cv2": mock_cv2, "numpy": mock_np}), \
             patch.object(svc_mod, "PHOTOS_DIR", tmp_path), \
             patch("app.infrastructure.storage.r2_storage.R2Storage",
                   side_effect=Exception("R2 unavailable")):
            svc = svc_mod.PhotoService()
            local_path, r2_key = svc._save_and_upload(MagicMock(), "abcdef12", "analysis")

        assert local_path.endswith(".jpg")
        assert r2_key == ""


# ---------------------------------------------------------------------------
# get_photo_service — singleton
# ---------------------------------------------------------------------------

class TestGetPhotoService:

    def test_returns_photo_service_instance(self):
        import app.api.v1.quality.photo_service as svc_mod
        svc_mod._photo_service = None
        from app.api.v1.quality.photo_service import PhotoService, get_photo_service
        result = get_photo_service()
        assert isinstance(result, PhotoService)

    def test_returns_same_instance_on_repeated_calls(self):
        import app.api.v1.quality.photo_service as svc_mod
        svc_mod._photo_service = None
        from app.api.v1.quality.photo_service import get_photo_service
        a = get_photo_service()
        b = get_photo_service()
        assert a is b
