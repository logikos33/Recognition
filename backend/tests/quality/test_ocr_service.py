"""
Testes unitarios para OcrService.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.quality.ocr_service import OcrService


FAKE_FRAME = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # bytes minimos simulando JPEG


@pytest.fixture
def svc():
    return OcrService()


def test_pyzbar_reads_barcode(svc):
    """_try_pyzbar deve retornar piece_number quando pyzbar decodifica codigo de barras."""
    fake_barcode = MagicMock()
    fake_barcode.data = b"PC12345"

    # cv2 e numpy estao instalados — nao mockar.
    # Apenas mockar pyzbar que nao esta instalado.
    pyzbar_inner = MagicMock()
    pyzbar_inner.decode.return_value = [fake_barcode]

    with patch.dict("sys.modules", {
        "pyzbar": MagicMock(pyzbar=pyzbar_inner),
        "pyzbar.pyzbar": pyzbar_inner,
    }):
        result = svc._try_pyzbar(FAKE_FRAME)

    assert result is not None
    assert result["piece_number"] == "12345"
    assert result["method"] == "barcode"
    assert result["confidence"] == 1.0


def test_paddleocr_reads_text(svc):
    """_try_paddle_ocr deve retornar piece_number quando PaddleOCR detecta texto com padrao."""
    fake_ocr_result = [[
        [None, ("Peca 5678 ok", 0.95)],
    ]]

    mock_ocr_instance = MagicMock()
    mock_ocr_instance.ocr.return_value = fake_ocr_result
    mock_paddle_cls = MagicMock(return_value=mock_ocr_instance)

    with patch.dict("sys.modules", {
        "cv2": MagicMock(
            imdecode=MagicMock(return_value=MagicMock()),
            IMREAD_COLOR=1,
        ),
        "numpy": MagicMock(
            frombuffer=MagicMock(return_value=MagicMock()),
            uint8=8,
        ),
        "paddleocr": MagicMock(PaddleOCR=mock_paddle_cls),
    }):
        result = svc._try_paddle_ocr(FAKE_FRAME)

    assert result is not None
    assert result["piece_number"] == "5678"
    assert result["method"] == "ocr"


def test_returns_none_when_no_text(svc):
    """read_piece_number deve retornar piece_number=None quando nenhum metodo detecta numero."""
    with patch.object(svc, "_try_paddle_ocr", return_value=None), \
         patch.object(svc, "_try_pyzbar", return_value=None):
        result = svc.read_piece_number(FAKE_FRAME)

    assert result["piece_number"] is None
    assert result["confidence"] == 0.0
    assert result["method"] is None


def test_invalid_image_returns_none_gracefully(svc):
    """_try_pyzbar deve retornar None (sem levantar excecao) em caso de erro na imagem."""
    with patch.dict("sys.modules", {
        "cv2": MagicMock(
            imdecode=MagicMock(side_effect=Exception("invalid image")),
            IMREAD_COLOR=1,
        ),
        "numpy": MagicMock(
            frombuffer=MagicMock(return_value=MagicMock()),
            uint8=8,
        ),
        "pyzbar": MagicMock(),
        "pyzbar.pyzbar": MagicMock(decode=MagicMock(side_effect=Exception("decode error"))),
    }):
        result = svc._try_pyzbar(b"bad-bytes")

    assert result is None
