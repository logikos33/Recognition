"""
Testes dos detectores ONNX do serviço de inferência — task-082.

Cobre:
- decode RF-DETR (raw logits+boxes e post-processed) com onnxruntime mockado;
- YoloxOnnxDetector intacto (decode existente);
- seleção de backend por arquitetura em get_detector() (aliases do registry);
- fail-loud para "ultralytics" (ADR-0043/task-080) e backend desconhecido;
- resolução de arquitetura (payload explícito > sidecar JSON > default).

onnxruntime é mockado via patch.dict(sys.modules) — mesmo padrão de
services/api/tests/unit/domain/test_detectors.py.
"""
from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from inference import detectors
from inference.detectors import (
    BACKEND_RFDETR_ONNX,
    BACKEND_YOLOX_ONNX,
    FRAMEWORK_TO_BACKEND,
    RfDetrOnnxDetector,
    YoloxOnnxDetector,
    get_detector,
    normalize_backend,
    resolve_backend_for_model,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_onnxruntime(n_outputs: int, run_outputs: list[np.ndarray]) -> MagicMock:
    """MagicMock de onnxruntime com sessão configurada."""
    mock_session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "images"
    mock_session.get_inputs.return_value = [mock_input]
    mock_session.get_outputs.return_value = [MagicMock() for _ in range(n_outputs)]
    mock_session.run.return_value = run_outputs

    mock_ort = MagicMock()
    mock_ort.InferenceSession.return_value = mock_session
    mock_ort.get_available_providers.return_value = ["CPUExecutionProvider"]
    return mock_ort


@pytest.fixture(autouse=True)
def _clear_detector_cache():
    """Cache singleton limpo entre testes."""
    detectors._detector_cache.clear()
    yield
    detectors._detector_cache.clear()


_FRAME = np.zeros((640, 640, 3), dtype=np.uint8)  # scale 1:1 com input 640


# ── RF-DETR: decode raw (logits + boxes) ─────────────────────────────────────

class TestRfDetrDecodeRaw:
    def _detector(self, class_names=("helmet", "no_helmet")):
        # Q=2 queries, C=2 classes.
        logits = np.full((1, 2, 2), -8.0, dtype=np.float32)
        logits[0, 0, 1] = 8.0   # query 0 → classe 1 com prob ~1
        # query 1: uniforme → prob 0.5 < confidence não; usar logits baixos iguais
        boxes = np.array(
            [[[0.5, 0.5, 0.2, 0.2],      # cx,cy,w,h norm → 256,256,128,128 px
              [0.1, 0.1, 0.05, 0.05]]],
            dtype=np.float32,
        )
        mock_ort = _mock_onnxruntime(2, [logits, boxes])
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            det = RfDetrOnnxDetector(
                "fake.onnx", class_names=class_names, confidence=0.6,
            )
        return det

    def test_output_mode_raw_detectado(self):
        det = self._detector()
        assert det._output_mode == "raw"
        assert det.is_ready

    def test_decode_bbox_e_classe(self):
        det = self._detector()
        results = det.predict(_FRAME)
        assert len(results) == 1
        r = results[0]
        assert r["class"] == "no_helmet"
        assert r["confidence"] > 0.99
        # cx=0.5*640=320, w=0.2*640=128 → x1=256, y1=256, w=128, h=128
        assert r["bbox"] == [256, 256, 128, 128]
        assert r["track_id"] is None

    def test_query_abaixo_da_confianca_filtrada(self):
        det = self._detector()
        results = det.predict(_FRAME)
        # query 1 tem prob uniforme (~0.5) < 0.6 → só 1 resultado
        assert len(results) == 1

    def test_classe_na_e_pulada(self):
        # classe vencedora mapeia para "N/A" (background DETR) → descartada
        det = self._detector(class_names=("helmet", "N/A"))
        assert det.predict(_FRAME) == []


# ── RF-DETR: decode post-processed (scores/labels/boxes) ─────────────────────

class TestRfDetrDecodePost:
    def _detector(self):
        scores = np.array([[0.9, 0.3]], dtype=np.float32)
        labels = np.array([[0, 1]], dtype=np.int64)
        boxes = np.array(
            [[[0.25, 0.25, 0.1, 0.1],
              [0.5, 0.5, 0.2, 0.2]]],
            dtype=np.float32,
        )
        mock_ort = _mock_onnxruntime(3, [scores, labels, boxes])
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            det = RfDetrOnnxDetector(
                "fake.onnx", class_names=("helmet", "no_helmet"), confidence=0.5,
            )
        return det

    def test_output_mode_post_detectado(self):
        det = self._detector()
        assert det._output_mode == "post"

    def test_decode_post(self):
        results = self._detector().predict(_FRAME)
        assert len(results) == 1
        r = results[0]
        assert r["class"] == "helmet"
        assert r["confidence"] == 0.9
        # cx=0.25*640=160, w=0.1*640=64 → x1=128, y1=128, w=64, h=64
        assert r["bbox"] == [128, 128, 64, 64]

    def test_frame_escalado(self):
        # frame 1280x1280 → scale 2x
        det = self._detector()
        frame = np.zeros((1280, 1280, 3), dtype=np.uint8)
        results = det.predict(frame)
        assert results[0]["bbox"] == [256, 256, 128, 128]


class TestRfDetrRobustez:
    def test_load_falho_nao_explode_predict(self):
        mock_ort = MagicMock()
        mock_ort.InferenceSession.side_effect = RuntimeError("arquivo corrompido")
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            det = RfDetrOnnxDetector("missing.onnx")
        assert not det.is_ready
        assert det.predict(_FRAME) == []


# ── YOLOX intacto ─────────────────────────────────────────────────────────────

class TestYoloxIntacto:
    def test_decode_yolox_segue_funcionando(self):
        # 1 predição decodificada [N=1, 85]: cx=320 cy=320 w=100 h=100,
        # obj e classe 0 com logit alto (sigmoid ~1).
        raw = np.full((1, 1, 85), -12.0, dtype=np.float32)
        raw[0, 0, :4] = [320.0, 320.0, 100.0, 100.0]
        raw[0, 0, 4] = 12.0   # objectness
        raw[0, 0, 5] = 12.0   # classe 0 → "person"
        mock_ort = _mock_onnxruntime(1, [raw])
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            det = YoloxOnnxDetector("fake.onnx", confidence=0.5)
        results = det.predict(_FRAME)
        assert len(results) == 1
        assert results[0]["class"] == "person"
        assert results[0]["bbox"] == [270, 270, 100, 100]

    def test_contrato_de_saida(self):
        raw = np.full((1, 1, 85), -12.0, dtype=np.float32)
        raw[0, 0, :4] = [320.0, 320.0, 100.0, 100.0]
        raw[0, 0, 4] = 12.0
        raw[0, 0, 5] = 12.0
        mock_ort = _mock_onnxruntime(1, [raw])
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            det = YoloxOnnxDetector("fake.onnx")
        r = det.predict(_FRAME)[0]
        assert set(r.keys()) == {"class", "confidence", "bbox", "track_id"}


# ── Seleção por arquitetura (get_detector) ────────────────────────────────────

class TestSelecaoBackend:
    def test_default_e_yolox(self):
        mock_ort = _mock_onnxruntime(1, [])
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            det = get_detector("model.onnx")
        assert isinstance(det, YoloxOnnxDetector)

    def test_backend_rfdetr(self):
        mock_ort = _mock_onnxruntime(2, [])
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            det = get_detector("model.onnx", backend=BACKEND_RFDETR_ONNX)
        assert isinstance(det, RfDetrOnnxDetector)

    def test_aliases_do_registry(self):
        # mesma semântica de FRAMEWORK_TO_BACKEND da factory do monolito
        assert FRAMEWORK_TO_BACKEND["rfdetr"] == BACKEND_RFDETR_ONNX
        assert FRAMEWORK_TO_BACKEND["yolox"] == BACKEND_YOLOX_ONNX
        mock_ort = _mock_onnxruntime(2, [])
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            det = get_detector("model.onnx", backend="rfdetr")
        assert isinstance(det, RfDetrOnnxDetector)

    def test_cache_separado_por_backend(self):
        mock_ort = _mock_onnxruntime(2, [])
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            a = get_detector("model.onnx", backend="yolox")
            b = get_detector("model.onnx", backend="rfdetr")
            a2 = get_detector("model.onnx", backend="yolox")
        assert a is a2
        assert a is not b

    def test_ultralytics_fail_loud(self):
        with pytest.raises(ValueError, match="ultralytics.*removido"):
            get_detector("model.pt", backend="ultralytics")

    def test_backend_desconhecido_fail_loud(self):
        with pytest.raises(ValueError, match="não reconhecido"):
            get_detector("model.onnx", backend="detectron2")


# ── Resolução de arquitetura (payload > sidecar > default) ───────────────────

class TestResolveBackendForModel:
    def test_explicito_vence(self, tmp_path):
        model = tmp_path / "m.onnx"
        model.write_bytes(b"x")
        (tmp_path / "m.json").write_text(json.dumps({"framework": "yolox"}))
        assert (
            resolve_backend_for_model(str(model), explicit="rfdetr")
            == BACKEND_RFDETR_ONNX
        )

    def test_sidecar_json(self, tmp_path):
        model = tmp_path / "m.onnx"
        model.write_bytes(b"x")
        (tmp_path / "m.json").write_text(json.dumps({"framework": "rfdetr"}))
        assert resolve_backend_for_model(str(model)) == BACKEND_RFDETR_ONNX

    def test_default_sem_sidecar(self, tmp_path):
        model = tmp_path / "m.onnx"
        model.write_bytes(b"x")
        assert resolve_backend_for_model(str(model)) == BACKEND_YOLOX_ONNX
        assert (
            resolve_backend_for_model(str(model), default="rfdetr_onnx")
            == BACKEND_RFDETR_ONNX
        )

    def test_sidecar_ultralytics_fail_loud(self, tmp_path):
        model = tmp_path / "m.onnx"
        model.write_bytes(b"x")
        (tmp_path / "m.json").write_text(json.dumps({"framework": "ultralytics"}))
        with pytest.raises(ValueError, match="ultralytics.*removido"):
            resolve_backend_for_model(str(model))

    def test_sidecar_corrompido_fail_loud(self, tmp_path):
        model = tmp_path / "m.onnx"
        model.write_bytes(b"x")
        (tmp_path / "m.json").write_text("{not json")
        with pytest.raises(ValueError, match="Sidecar"):
            resolve_backend_for_model(str(model))

    def test_explicito_ultralytics_fail_loud(self, tmp_path):
        model = tmp_path / "m.onnx"
        model.write_bytes(b"x")
        with pytest.raises(ValueError, match="ultralytics"):
            resolve_backend_for_model(str(model), explicit="ultralytics")


class TestNormalizeBackend:
    def test_normaliza_espacos_e_caixa(self):
        assert normalize_backend("  RFDETR ") == BACKEND_RFDETR_ONNX
        assert normalize_backend("Yolox_Onnx") == BACKEND_YOLOX_ONNX
