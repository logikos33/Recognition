"""Tests: ocr_service.py — OcrService, _try_paddle_ocr, _try_pyzbar, singleton."""
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# read_piece_number — both dependencies unavailable
# ---------------------------------------------------------------------------

class TestReadPieceNumberNoDependencies:

    def test_no_deps_returns_none_piece_number(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()
        result = svc.read_piece_number(b"fake-frame")
        assert result["piece_number"] is None

    def test_no_deps_returns_zero_confidence(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()
        result = svc.read_piece_number(b"fake-frame")
        assert result["confidence"] == 0.0

    def test_no_deps_returns_none_method(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()
        result = svc.read_piece_number(b"fake-frame")
        assert result["method"] is None

    def test_no_deps_does_not_raise(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()
        svc.read_piece_number(b"")


# ---------------------------------------------------------------------------
# _try_paddle_ocr
# ---------------------------------------------------------------------------

class TestTryPaddleOcr:

    def test_paddle_not_installed_returns_none(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()
        # cv2 not installed → ImportError → None
        result = svc._try_paddle_ocr(b"fake")
        assert result is None

    def test_with_mocked_paddle_matching_pattern(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()

        mock_cv2 = MagicMock()
        mock_np = MagicMock()
        mock_np.frombuffer.return_value = MagicMock()
        mock_cv2.imdecode.return_value = MagicMock()
        mock_cv2.IMREAD_COLOR = 1

        mock_paddle_mod = MagicMock()
        mock_ocr_instance = MagicMock()
        # Return a line with text "12345" and confidence 0.92
        mock_ocr_instance.ocr.return_value = [[[None, ("12345", 0.92)]]]
        mock_paddle_mod.PaddleOCR.return_value = mock_ocr_instance

        with patch.dict(sys.modules, {
            "cv2": mock_cv2,
            "numpy": mock_np,
            "paddleocr": mock_paddle_mod,
        }):
            result = svc._try_paddle_ocr(b"fake")

        assert result is not None
        assert result["piece_number"] == "12345"
        assert result["confidence"] == 0.92
        assert result["method"] == "ocr"

    def test_with_mocked_paddle_no_match_returns_none(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()

        mock_cv2 = MagicMock()
        mock_np = MagicMock()
        mock_cv2.IMREAD_COLOR = 1

        mock_paddle_mod = MagicMock()
        mock_ocr_instance = MagicMock()
        # Return text that doesn't match the 4-6 digit pattern
        mock_ocr_instance.ocr.return_value = [[[None, ("NO-MATCH", 0.95)]]]
        mock_paddle_mod.PaddleOCR.return_value = mock_ocr_instance

        with patch.dict(sys.modules, {
            "cv2": mock_cv2,
            "numpy": mock_np,
            "paddleocr": mock_paddle_mod,
        }):
            result = svc._try_paddle_ocr(b"fake")

        assert result is None

    def test_with_mocked_paddle_empty_result_returns_none(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()

        mock_cv2 = MagicMock()
        mock_np = MagicMock()
        mock_cv2.IMREAD_COLOR = 1

        mock_paddle_mod = MagicMock()
        mock_ocr_instance = MagicMock()
        mock_ocr_instance.ocr.return_value = []  # empty
        mock_paddle_mod.PaddleOCR.return_value = mock_ocr_instance

        with patch.dict(sys.modules, {
            "cv2": mock_cv2,
            "numpy": mock_np,
            "paddleocr": mock_paddle_mod,
        }):
            result = svc._try_paddle_ocr(b"fake")

        assert result is None

    def test_general_exception_returns_none(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()

        mock_cv2 = MagicMock()
        mock_np = MagicMock()
        mock_cv2.imdecode.side_effect = RuntimeError("GPU error")
        mock_cv2.IMREAD_COLOR = 1

        mock_paddle_mod = MagicMock()

        with patch.dict(sys.modules, {
            "cv2": mock_cv2,
            "numpy": mock_np,
            "paddleocr": mock_paddle_mod,
        }):
            result = svc._try_paddle_ocr(b"fake")

        assert result is None


# ---------------------------------------------------------------------------
# _try_pyzbar
# ---------------------------------------------------------------------------

class TestTryPyzbar:

    def test_pyzbar_not_installed_returns_none(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()
        result = svc._try_pyzbar(b"fake")
        assert result is None

    def test_with_mocked_pyzbar_matching_barcode(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()

        mock_cv2 = MagicMock()
        mock_np = MagicMock()
        mock_cv2.IMREAD_COLOR = 1

        mock_bc = MagicMock()
        mock_bc.data.decode.return_value = "98765"

        mock_pyzbar_mod = MagicMock()
        mock_pyzbar_sub = MagicMock()
        mock_pyzbar_sub.decode.return_value = [mock_bc]
        mock_pyzbar_mod.pyzbar = mock_pyzbar_sub

        with patch.dict(sys.modules, {
            "cv2": mock_cv2,
            "numpy": mock_np,
            "pyzbar": mock_pyzbar_mod,
        }):
            result = svc._try_pyzbar(b"fake")

        assert result is not None
        assert result["piece_number"] == "98765"
        assert result["confidence"] == 1.0
        assert result["method"] == "barcode"

    def test_with_mocked_pyzbar_no_barcodes_returns_none(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()

        mock_cv2 = MagicMock()
        mock_np = MagicMock()
        mock_cv2.IMREAD_COLOR = 1

        mock_pyzbar_mod = MagicMock()
        mock_pyzbar_sub = MagicMock()
        mock_pyzbar_sub.decode.return_value = []
        mock_pyzbar_mod.pyzbar = mock_pyzbar_sub

        with patch.dict(sys.modules, {
            "cv2": mock_cv2,
            "numpy": mock_np,
            "pyzbar": mock_pyzbar_mod,
        }):
            result = svc._try_pyzbar(b"fake")

        assert result is None

    def test_general_exception_returns_none(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()

        mock_cv2 = MagicMock()
        mock_np = MagicMock()
        mock_cv2.imdecode.side_effect = RuntimeError("camera error")
        mock_cv2.IMREAD_COLOR = 1

        mock_pyzbar_mod = MagicMock()
        mock_pyzbar_sub = MagicMock()
        mock_pyzbar_mod.pyzbar = mock_pyzbar_sub

        with patch.dict(sys.modules, {
            "cv2": mock_cv2,
            "numpy": mock_np,
            "pyzbar": mock_pyzbar_mod,
        }):
            result = svc._try_pyzbar(b"fake")

        assert result is None


# ---------------------------------------------------------------------------
# read_piece_number — fallback chain with mocks
# ---------------------------------------------------------------------------

class TestReadPieceNumberFallbackChain:

    def test_paddle_low_confidence_falls_back_to_pyzbar(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()

        with patch.object(svc, "_try_paddle_ocr", return_value={"piece_number": "12345",
                                                                  "confidence": 0.5,
                                                                  "method": "ocr"}), \
             patch.object(svc, "_try_pyzbar", return_value={"piece_number": "67890",
                                                              "confidence": 1.0,
                                                              "method": "barcode"}):
            result = svc.read_piece_number(b"fake")

        # paddle low confidence → falls through → pyzbar result
        assert result["method"] == "barcode"
        assert result["piece_number"] == "67890"

    def test_paddle_high_confidence_returns_paddle_result(self):
        from app.api.v1.quality.ocr_service import OcrService, OCR_MIN_CONFIDENCE
        svc = OcrService()

        with patch.object(svc, "_try_paddle_ocr", return_value={"piece_number": "12345",
                                                                  "confidence": OCR_MIN_CONFIDENCE + 0.01,
                                                                  "method": "ocr"}), \
             patch.object(svc, "_try_pyzbar") as mock_pyzbar:
            result = svc.read_piece_number(b"fake")

        mock_pyzbar.assert_not_called()
        assert result["method"] == "ocr"

    def test_both_fail_returns_none_result(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()

        with patch.object(svc, "_try_paddle_ocr", return_value=None), \
             patch.object(svc, "_try_pyzbar", return_value=None):
            result = svc.read_piece_number(b"fake")

        assert result == {"piece_number": None, "confidence": 0.0, "method": None}

    def test_paddle_none_but_pyzbar_succeeds(self):
        from app.api.v1.quality.ocr_service import OcrService
        svc = OcrService()

        with patch.object(svc, "_try_paddle_ocr", return_value=None), \
             patch.object(svc, "_try_pyzbar", return_value={"piece_number": "11111",
                                                              "confidence": 1.0,
                                                              "method": "barcode"}):
            result = svc.read_piece_number(b"fake")

        assert result["method"] == "barcode"


# ---------------------------------------------------------------------------
# get_ocr_service — singleton
# ---------------------------------------------------------------------------

class TestGetOcrService:

    def test_returns_ocr_service_instance(self):
        import app.api.v1.quality.ocr_service as mod
        mod._ocr_service = None
        from app.api.v1.quality.ocr_service import OcrService, get_ocr_service
        result = get_ocr_service()
        assert isinstance(result, OcrService)

    def test_returns_same_instance_on_repeated_calls(self):
        import app.api.v1.quality.ocr_service as mod
        mod._ocr_service = None
        from app.api.v1.quality.ocr_service import get_ocr_service
        a = get_ocr_service()
        b = get_ocr_service()
        assert a is b

    def test_singleton_can_be_reset(self):
        import app.api.v1.quality.ocr_service as mod
        mod._ocr_service = None
        from app.api.v1.quality.ocr_service import get_ocr_service
        a = get_ocr_service()
        mod._ocr_service = None
        b = get_ocr_service()
        assert a is not b
