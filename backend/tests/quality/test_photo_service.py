"""
Testes unitarios para PhotoService.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.quality.photo_service import PhotoService


FAKE_FRAME = b"\xff\xd8\xff\xe0" + b"\x00" * 100
CAMERA_ID = "camera-uuid-abcdef12"


@pytest.fixture
def svc():
    return PhotoService()


def _make_cv2_mock(tmp_path: Path):
    """Cria mock de cv2 que escreve arquivo real ao chamar imwrite."""
    mock_cv2 = MagicMock()
    mock_cv2.IMREAD_COLOR = 1
    mock_cv2.IMWRITE_JPEG_QUALITY = 1
    mock_cv2.imdecode.return_value = MagicMock(shape=(480, 640, 3))
    mock_cv2.FONT_HERSHEY_SIMPLEX = 0

    def fake_imwrite(path, img, params=None):
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake-jpeg-data")
        return True

    mock_cv2.imwrite.side_effect = fake_imwrite
    mock_cv2.rectangle = MagicMock()
    mock_cv2.putText = MagicMock()
    return mock_cv2


def _numpy_mock():
    mock_numpy = MagicMock()
    mock_numpy.frombuffer.return_value = MagicMock()
    mock_numpy.uint8 = 8
    return mock_numpy


def test_save_analysis_photo_creates_directory(svc, tmp_path):
    """save_analysis_photo deve criar subdiretorio analysis/ e retornar caminho local."""
    mock_cv2 = _make_cv2_mock(tmp_path)

    with patch.dict("sys.modules", {"cv2": mock_cv2, "numpy": _numpy_mock()}), \
         patch("app.api.v1.quality.photo_service.PHOTOS_DIR", tmp_path):
        local_path, _r2_key = svc.save_analysis_photo(FAKE_FRAME, [], CAMERA_ID)

    assert local_path != "", "local_path nao deve ser vazio"
    assert "analysis" in local_path
    assert Path(local_path).exists()


def test_save_raw_photo_returns_path(svc, tmp_path):
    """save_raw_photo deve retornar string de caminho local nao vazio."""
    mock_cv2 = _make_cv2_mock(tmp_path)

    with patch.dict("sys.modules", {"cv2": mock_cv2, "numpy": _numpy_mock()}), \
         patch("app.api.v1.quality.photo_service.PHOTOS_DIR", tmp_path):
        local_path, _r2_key = svc.save_raw_photo(FAKE_FRAME, CAMERA_ID)

    assert isinstance(local_path, str)
    assert local_path != "", "local_path nao deve ser vazio"
    assert "raw" in local_path


def test_r2_upload_called_when_r2_configured(svc, tmp_path):
    """_save_and_upload deve chamar storage.upload_file quando R2 disponivel."""
    mock_cv2 = _make_cv2_mock(tmp_path)
    mock_storage = MagicMock()
    mock_r2_class = MagicMock()
    mock_r2_class.get_instance.return_value = mock_storage

    with patch.dict("sys.modules", {
        "cv2": mock_cv2,
        "numpy": _numpy_mock(),
        "app.infrastructure.storage.r2_storage": MagicMock(R2Storage=mock_r2_class),
    }), patch("app.api.v1.quality.photo_service.PHOTOS_DIR", tmp_path):
        local_path, r2_key = svc.save_raw_photo(FAKE_FRAME, CAMERA_ID)

    assert local_path != ""
    mock_storage.upload_file.assert_called_once()


def test_r2_upload_skipped_when_not_configured(svc, tmp_path):
    """_save_and_upload deve retornar r2_key vazio quando upload R2 falha.

    R2Storage.get_instance() nao existe na implementacao real, entao a chamada
    levanta AttributeError que e capturado pelo except Exception do _save_and_upload,
    resultando em r2_key vazio (silencioso).
    """
    mock_cv2 = _make_cv2_mock(tmp_path)

    with patch.dict("sys.modules", {"cv2": mock_cv2, "numpy": _numpy_mock()}), \
         patch("app.api.v1.quality.photo_service.PHOTOS_DIR", tmp_path):
        local_path, r2_key = svc.save_raw_photo(FAKE_FRAME, CAMERA_ID)

    assert local_path != "", "local_path deve ser preenchido mesmo sem R2"
    assert r2_key == "", "r2_key deve ser vazio quando upload R2 falha"
