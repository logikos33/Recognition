"""
Tests unitários — domain/detectors (task-055a / PR A1 — PORT de staging p/ PR-1).

Valida:
- Pré-processamento (letterbox, normalização, shape)
- NMS (elimina sobreposição, mantém score alto)
- Mapeamento de classes COCO
- Flag de violação via _VIOLATION_CLASSES
- Factory não importa ultralytics quando backend=yolox_onnx
- FRAMEWORK_TO_BACKEND: aliases de trained_models.framework aceitos na factory
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


def _mock_onnxruntime() -> MagicMock:
    """Mock de onnxruntime — evita carregar modelo real."""
    mock_ort = MagicMock()
    mock_session = MagicMock()
    mock_session.get_inputs.return_value = [MagicMock(name="images")]
    mock_ort.InferenceSession.return_value = mock_session
    mock_ort.get_available_providers.return_value = ["CPUExecutionProvider"]
    return mock_ort


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

    def test_pixel_range_is_0_to_255_not_normalized(self) -> None:
        """D-66: YOLOX stock NÃO normaliza a entrada — blob deve ficar em 0-255.

        Uma versão anterior dividia por 255 aqui, o que zera silenciosamente
        as confianças de qualquer checkpoint YOLOX stock (COCO pré-treinado
        ou treinado por este pipeline — ambos exportados via
        `yolox.tools.export_onnx` oficial, ver docs/REGISTRO_DE_DECISOES.md D-66).
        """
        pp = self._import_pp()
        frame = np.full((64, 64, 3), 255, dtype=np.uint8)
        blob, _ = pp(frame, 64, 64)
        assert blob.max() == pytest.approx(255.0)
        assert blob.min() >= 0.0

    def test_preserves_bgr_channel_order(self) -> None:
        """D-66: YOLOX stock NÃO troca BGR→RGB — canal 0 do blob é o canal 0 do frame.

        Frame sintético com canais desiguais (como se fosse BGR vindo de
        cv2/ffmpeg): canal 0 (B) = 200, canal 1 (G) = 50, canal 2 (R) = 10.
        Se o preproc trocasse pra RGB, o canal 0 do blob viraria 10 (R).
        """
        pp = self._import_pp()
        frame = np.zeros((32, 32, 3), dtype=np.uint8)
        frame[:, :, 0] = 200
        frame[:, :, 1] = 50
        frame[:, :, 2] = 10
        blob, _ = pp(frame, 32, 32)  # blob: [1, 3, H, W]
        assert blob[0, 0].max() == pytest.approx(200.0)
        assert blob[0, 1].max() == pytest.approx(50.0)
        assert blob[0, 2].max() == pytest.approx(10.0)

    def test_letterbox_pad_value_preserved_unnormalized(self) -> None:
        """Área de padding (114) não deve ser dividida por 255 nem trocada de canal."""
        pp = self._import_pp()
        frame = np.zeros((32, 64, 3), dtype=np.uint8)  # aspecto 1:2 força padding
        blob, _ = pp(frame, 64, 64)
        # canto inferior do blob cai na área de padding (114) após o letterbox
        assert blob[0, 0, -1, -1] == pytest.approx(114.0)


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
        # Importa uma CÓPIA fresh do módulo sob stubs de celery/redis.
        # NUNCA importlib.reload aqui: reload re-executa o módulo real EM
        # PLACE e deixaria as tasks decoradas por mocks para todos os testes
        # seguintes da sessão. patch.dict restaura o sys.modules original
        # (com o módulo real intacto) na saída do bloco.
        with patch.dict(sys.modules, {
            "celery": MagicMock(),
            "redis": MagicMock(),
            "app.infrastructure.queue.celery_app": MagicMock(),
        }):
            sys.modules.pop("app.infrastructure.queue.tasks.inference", None)
            mod = importlib.import_module("app.infrastructure.queue.tasks.inference")
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


class TestFactoryNoUltralytics:
    """Garante que yolox_onnx/rfdetr_onnx não importam ultralytics."""

    def test_yolox_backend_does_not_import_ultralytics(self) -> None:
        """get_detector('yolox_onnx', ...) não deve importar ultralytics."""
        ultralytics_already_loaded = "ultralytics" in sys.modules

        with patch.dict(sys.modules, {"onnxruntime": _mock_onnxruntime()}):
            # Import fresh (sem reload in-place — não mutar o módulo cacheado);
            # patch.dict devolve o factory original ao sair do bloco.
            sys.modules.pop("app.domain.detectors.factory", None)
            importlib.import_module("app.domain.detectors.factory")

            from app.domain.detectors.factory import get_detector  # noqa: PLC0415
            _ = get_detector(
                backend="yolox_onnx",
                model_path="/tmp/fake.onnx",  # noqa: S108
                confidence=0.5,
            )

        if not ultralytics_already_loaded:
            assert "ultralytics" not in sys.modules, "ultralytics foi importado inesperadamente"

    def test_unknown_backend_raises(self) -> None:
        from app.domain.detectors.factory import get_detector  # noqa: PLC0415
        with pytest.raises(ValueError, match="[Bb]ackend"):
            get_detector(backend="nonexistent_backend", model_path="/tmp/fake.onnx")  # noqa: S108


# ── FRAMEWORK_TO_BACKEND (aliases de trained_models.framework) ────────────────


class TestFrameworkToBackend:
    """trained_models.framework ('rfdetr'|'yolox') deve resolver p/ backend.

    'ultralytics' foi REMOVIDO do mapa (task-080/ADR-0043) — modelo legado no
    registry falha alto com ValueError dedicado, nunca carrega AGPL.
    """

    def test_mapping_contents(self) -> None:
        from app.domain.detectors.factory import (  # noqa: PLC0415
            BACKEND_RFDETR_ONNX,
            BACKEND_YOLOX_ONNX,
            FRAMEWORK_TO_BACKEND,
        )
        assert FRAMEWORK_TO_BACKEND == {
            "rfdetr": BACKEND_RFDETR_ONNX,
            "yolox": BACKEND_YOLOX_ONNX,
        }
        assert FRAMEWORK_TO_BACKEND["rfdetr"] == "rfdetr_onnx"
        assert FRAMEWORK_TO_BACKEND["yolox"] == "yolox_onnx"

    def test_ultralytics_backend_raises_dedicated_error(self) -> None:
        """Framework legado 'ultralytics' → ValueError explícito citando o ADR,
        sem tentar importar nada AGPL (fail-loud, ADR-0017/ADR-0043)."""
        from app.domain.detectors.factory import get_detector  # noqa: PLC0415

        ultralytics_already_loaded = "ultralytics" in sys.modules
        with pytest.raises(ValueError, match="ultralytics.*removido|removido.*ultralytics"):
            get_detector(backend="ultralytics", model_path="/tmp/fake.pt")  # noqa: S108
        if not ultralytics_already_loaded:
            assert "ultralytics" not in sys.modules

    def test_supported_backends_sao_apenas_onnx_apache(self) -> None:
        from app.domain.detectors.factory import SUPPORTED_BACKENDS  # noqa: PLC0415
        assert SUPPORTED_BACKENDS == ("yolox_onnx", "rfdetr_onnx")

    def test_get_detector_accepts_rfdetr_alias(self) -> None:
        """get_detector('rfdetr') não levanta ValueError — instancia RfDetrOnnxDetector."""
        with patch.dict(sys.modules, {"onnxruntime": _mock_onnxruntime()}):
            from app.domain.detectors.factory import get_detector  # noqa: PLC0415
            from app.domain.detectors.onnx_rfdetr import RfDetrOnnxDetector  # noqa: PLC0415

            detector = get_detector(backend="rfdetr", model_path="/tmp/fake.onnx")  # noqa: S108
        assert isinstance(detector, RfDetrOnnxDetector)

    def test_get_detector_accepts_yolox_alias(self) -> None:
        """get_detector('yolox') não levanta ValueError — instancia YoloxOnnxDetector."""
        with patch.dict(sys.modules, {"onnxruntime": _mock_onnxruntime()}):
            from app.domain.detectors.factory import get_detector  # noqa: PLC0415
            from app.domain.detectors.onnx_yolox import YoloxOnnxDetector  # noqa: PLC0415

            detector = get_detector(backend="yolox", model_path="/tmp/fake.onnx")  # noqa: S108
        assert isinstance(detector, YoloxOnnxDetector)

    def test_alias_is_case_insensitive(self) -> None:
        with patch.dict(sys.modules, {"onnxruntime": _mock_onnxruntime()}):
            from app.domain.detectors.factory import get_detector  # noqa: PLC0415
            from app.domain.detectors.onnx_rfdetr import RfDetrOnnxDetector  # noqa: PLC0415

            detector = get_detector(backend=" RFDETR ", model_path="/tmp/fake.onnx")  # noqa: S108
        assert isinstance(detector, RfDetrOnnxDetector)

    def test_unknown_framework_still_raises(self) -> None:
        from app.domain.detectors.factory import get_detector  # noqa: PLC0415
        with pytest.raises(ValueError, match="[Bb]ackend"):
            get_detector(backend="yolov8", model_path="/tmp/fake.onnx")  # noqa: S108


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


class TestRfDetrLadoDoModelo:
    """Issue #417 — o default deste backend é 640×640 e RF-DETR exporta 560×560.

    Blob 640 num modelo 560 faz `session.run` levantar shape mismatch, que
    `predict` engole devolvendo `[]`. Resultado: detector que não detecta nada,
    sem uma linha de erro por imagem, e uma avaliação inteira com tp=0 e fp=0.
    O lado passa a vir do próprio ONNX.
    """

    @staticmethod
    def _detector_com_shape(shape):
        from app.domain.detectors.onnx_rfdetr import RfDetrOnnxDetector  # noqa: PLC0415

        sessao = MagicMock()
        entrada = MagicMock()
        entrada.name, entrada.shape = "input", shape
        sessao.get_inputs.return_value = [entrada]
        sessao.get_outputs.return_value = [MagicMock(), MagicMock()]
        ort = MagicMock()
        ort.InferenceSession.return_value = sessao
        with patch.dict(sys.modules, {"onnxruntime": ort}):
            return RfDetrOnnxDetector(model_path="/tmp/x.onnx", input_size=(640, 640))

    def test_adota_o_lado_estatico_declarado_pelo_modelo(self) -> None:
        det = self._detector_com_shape([1, 3, 560, 560])
        assert (det._input_h, det._input_w) == (560, 560)

    def test_eixo_dinamico_mantem_o_pedido(self) -> None:
        det = self._detector_com_shape([1, 3, "height", "width"])
        assert (det._input_h, det._input_w) == (640, 640)

    def test_shape_inesperado_nao_quebra(self) -> None:
        det = self._detector_com_shape([1, 3])
        assert (det._input_h, det._input_w) == (640, 640)
