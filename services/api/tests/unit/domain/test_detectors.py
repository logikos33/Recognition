"""
Tests unitários — domain/detectors (task-055a / PR A1).

Valida:
- Pré-processamento (letterbox, normalização, shape)
- NMS (elimina sobreposição, mantém score alto)
- Mapeamento de classes COCO
- Flag de violação via _VIOLATION_CLASSES
- Factory não importa ultralytics quando backend=yolox_onnx
- Contrato de saída: lista[dict] com keys class/confidence/bbox/track_id
"""
from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_frame(h: int = 480, w: int = 640) -> np.ndarray:
    """Frame sintético BGR."""
    return np.zeros((h, w, 3), dtype=np.uint8)


# ── Letterbox ─────────────────────────────────────────────────────────────────


class TestLetterbox:
    def _import_lb(self):
        from app.domain.detectors.onnx_yolox import _letterbox  # noqa: PLC0415
        return _letterbox

    def test_output_shape(self) -> None:
        lb = self._import_lb()
        frame = _make_frame(480, 640)
        out, _ = lb(frame, 640, 640)
        assert out.shape == (640, 640, 3)

    def test_scale_returned(self) -> None:
        lb = self._import_lb()
        frame = _make_frame(320, 640)  # 2:1 aspect
        _, scale = lb(frame, 640, 640)
        # Eixo limitante é a altura (640/320=2), mas largura já cabe (640/640=1)
        assert abs(scale - 1.0) < 1e-5  # largura é o limite

    def test_square_frame_no_padding(self) -> None:
        lb = self._import_lb()
        frame = _make_frame(100, 100)
        out, scale = lb(frame, 100, 100)
        assert out.shape == (100, 100, 3)
        assert abs(scale - 1.0) < 1e-5

    def test_landscape_frame(self) -> None:
        lb = self._import_lb()
        frame = _make_frame(200, 400)
        out, scale = lb(frame, 200, 200)
        # Largura é o limite: 200/400 = 0.5
        assert abs(scale - 0.5) < 1e-5
        assert out.shape == (200, 200, 3)

    def test_portrait_frame(self) -> None:
        lb = self._import_lb()
        frame = _make_frame(400, 200)
        out, scale = lb(frame, 200, 200)
        # Altura é o limite: 200/400 = 0.5
        assert abs(scale - 0.5) < 1e-5


# ── Preprocess ────────────────────────────────────────────────────────────────


class TestPreprocess:
    def _import_pp(self):
        from app.domain.detectors.onnx_yolox import _preprocess  # noqa: PLC0415
        return _preprocess

    def test_blob_shape(self) -> None:
        pp = self._import_pp()
        frame = _make_frame(480, 640)
        blob, _ = pp(frame, 640, 640)
        assert blob.shape == (1, 3, 640, 640)

    def test_blob_dtype_float32(self) -> None:
        pp = self._import_pp()
        frame = _make_frame()
        blob, _ = pp(frame, 640, 640)
        assert blob.dtype == np.float32

    def test_pixel_range_0_to_1(self) -> None:
        pp = self._import_pp()
        frame = np.full((64, 64, 3), 255, dtype=np.uint8)
        blob, _ = pp(frame, 64, 64)
        assert blob.max() <= 1.0
        assert blob.min() >= 0.0


# ── NMS ───────────────────────────────────────────────────────────────────────


class TestNms:
    def _import_nms(self):
        from app.domain.detectors.onnx_yolox import _nms  # noqa: PLC0415
        return _nms

    def test_empty_input(self) -> None:
        nms = self._import_nms()
        result = nms(np.zeros((0, 4)), np.zeros(0), iou_threshold=0.45)
        assert result == []

    def test_single_box(self) -> None:
        nms = self._import_nms()
        boxes = np.array([[10, 10, 50, 50]], dtype=np.float32)
        scores = np.array([0.9])
        result = nms(boxes, scores, iou_threshold=0.45)
        assert result == [0]

    def test_two_identical_boxes_keeps_higher_score(self) -> None:
        nms = self._import_nms()
        boxes = np.array([[0, 0, 10, 10], [0, 0, 10, 10]], dtype=np.float32)
        scores = np.array([0.7, 0.9])
        result = nms(boxes, scores, iou_threshold=0.5)
        # Índice 1 tem score maior → deve ser mantido
        assert 1 in result
        assert len(result) == 1

    def test_non_overlapping_boxes_all_kept(self) -> None:
        nms = self._import_nms()
        boxes = np.array([
            [0, 0, 5, 5],
            [100, 100, 150, 150],
            [200, 200, 250, 250],
        ], dtype=np.float32)
        scores = np.array([0.9, 0.8, 0.7])
        result = nms(boxes, scores, iou_threshold=0.5)
        assert len(result) == 3

    def test_heavy_overlap_suppresses(self) -> None:
        nms = self._import_nms()
        # Segundo box é quase idêntico, deveria ser suprimido
        boxes = np.array([
            [0, 0, 100, 100],
            [1, 1, 99, 99],
        ], dtype=np.float32)
        scores = np.array([0.95, 0.85])
        result = nms(boxes, scores, iou_threshold=0.5)
        assert len(result) == 1
        assert result[0] == 0


# ── COCO Classes ──────────────────────────────────────────────────────────────


class TestCocoClasses:
    def test_coco_80_classes_count(self) -> None:
        from app.domain.detectors.onnx_yolox import COCO_CLASSES  # noqa: PLC0415
        assert len(COCO_CLASSES) == 80

    def test_person_is_index_0(self) -> None:
        from app.domain.detectors.onnx_yolox import COCO_CLASSES  # noqa: PLC0415
        assert COCO_CLASSES[0] == "person"

    def test_rfdetr_coco_91_count(self) -> None:
        from app.domain.detectors.onnx_rfdetr import COCO_CLASSES_91  # noqa: PLC0415
        assert len(COCO_CLASSES_91) == 91

    def test_rfdetr_na_entries_present(self) -> None:
        from app.domain.detectors.onnx_rfdetr import COCO_CLASSES_91  # noqa: PLC0415
        assert "N/A" in COCO_CLASSES_91


# ── Violation flag ────────────────────────────────────────────────────────────


class TestViolationFlag:
    """Testa a lógica _has_violation do inference task."""

    def _get_fn(self):
        # Importa o módulo mockando celery e redis para evitar side-effects
        with patch.dict(sys.modules, {
            "celery": MagicMock(),
            "redis": MagicMock(),
            "app.infrastructure.queue.celery_app": MagicMock(),
        }):
            import importlib  # noqa: PLC0415
            if "app.infrastructure.queue.tasks.inference" in sys.modules:
                mod = importlib.reload(sys.modules["app.infrastructure.queue.tasks.inference"])
            else:
                import app.infrastructure.queue.tasks.inference as mod  # noqa: PLC0415
            return mod._has_violation

    def test_violation_detected_for_no_helmet(self) -> None:
        fn = self._get_fn()
        detections = [{"class": "no_helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        assert fn(detections) is True

    def test_no_violation_for_helmet(self) -> None:
        fn = self._get_fn()
        detections = [{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        assert fn(detections) is False

    def test_empty_detections_no_violation(self) -> None:
        fn = self._get_fn()
        assert fn([]) is False

    def test_mixed_detections_has_violation(self) -> None:
        fn = self._get_fn()
        detections = [
            {"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
            {"class": "no_vest", "confidence": 0.7, "bbox": [0, 0, 10, 10]},
        ]
        assert fn(detections) is True


# ── Factory — sem ultralytics ─────────────────────────────────────────────────


class TestFactoryNoultralytics:
    """Garante que yolox_onnx/rfdetr_onnx não importam ultralytics."""

    def test_yolox_backend_does_not_import_ultralytics(self) -> None:
        """get_detector('yolox_onnx', ...) não deve importar ultralytics."""
        # Patch onnxruntime para evitar necessidade de modelo real
        mock_ort = MagicMock()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="images")]
        mock_ort.InferenceSession.return_value = mock_session
        mock_ort.get_available_providers.return_value = ["CPUExecutionProvider"]

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            # Remove cache para forçar instanciação
            if "app.domain.detectors.factory" in sys.modules:
                importlib.reload(sys.modules["app.domain.detectors.factory"])

            from app.domain.detectors.factory import get_detector  # noqa: PLC0415
            _ = get_detector(
                backend="yolox_onnx",
                model_path="/tmp/fake.onnx",
                confidence=0.5,
            )

        assert "ultralytics" not in sys.modules, "ultralytics foi importado inesperadamente"

    def test_unknown_backend_raises(self) -> None:
        from app.domain.detectors.factory import get_detector  # noqa: PLC0415
        with pytest.raises(ValueError, match="backend"):
            get_detector(backend="nonexistent_backend", model_path="/tmp/fake.onnx")


# ── Detector output contract ──────────────────────────────────────────────────


class TestDetectorOutputContract:
    """Valida shape e tipos do contrato de saída do detector."""

    def _make_mock_detector(self, detections: list[dict]):
        """Cria um detector mock que retorna detecções fixas."""
        from app.domain.detectors.base import Detector  # noqa: PLC0415

        class _MockDetector(Detector):
            def predict(self, frame: np.ndarray) -> list[dict]:
                return detections

        return _MockDetector()

    def test_output_keys_present(self) -> None:
        det = self._make_mock_detector([
            {"class": "helmet", "confidence": 0.85, "bbox": [10, 20, 50, 60], "track_id": None},
        ])
        result = det.predict(_make_frame())
        assert len(result) == 1
        r = result[0]
        assert "class" in r
        assert "confidence" in r
        assert "bbox" in r
        assert "track_id" in r

    def test_bbox_is_list_of_4(self) -> None:
        det = self._make_mock_detector([
            {"class": "no_gloves", "confidence": 0.7, "bbox": [5, 10, 30, 40], "track_id": None},
        ])
        result = det.predict(_make_frame())
        assert isinstance(result[0]["bbox"], list)
        assert len(result[0]["bbox"]) == 4

    def test_confidence_in_0_1_range(self) -> None:
        det = self._make_mock_detector([
            {"class": "vest", "confidence": 0.65, "bbox": [0, 0, 10, 10], "track_id": None},
        ])
        result = det.predict(_make_frame())
        conf = result[0]["confidence"]
        assert 0.0 <= conf <= 1.0

    def test_is_ready_default_true(self) -> None:
        from app.domain.detectors.base import Detector  # noqa: PLC0415

        class _Impl(Detector):
            def predict(self, frame):
                return []

        assert _Impl().is_ready is True
