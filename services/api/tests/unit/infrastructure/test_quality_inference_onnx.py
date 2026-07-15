"""
Tests: tasks/quality_inference.py — port para detector ONNX (task-079,
ADR-0043 AGPL-zero, ADR-0044 detector plugável).

Cobre:
- Módulo não importa `ultralytics` em nenhum ponto (fail-antes/passa-depois:
  este venv de CI não tem ultralytics instalado — ver TestNoUltralyticsImport).
- _is_nok_class: semântica OK/NOK por NOME de classe (QUALITY_CLASSES,
  category="ok"/"nok") — substitui o índice inteiro que o ultralytics
  expunha via box.cls[0]. Fail-closed: classe fora do vocabulário do módulo
  (ex.: fallback COCO do detector singleton sem modelo custom) é NOK.
- quality_inference_loop: resolve o detector via
  tasks.inference._get_detector_for_camera (cascata WS-A6, mesmo mecanismo
  do EPI) em vez de `YOLO(...)`; grava defect_class como STRING (nome da
  classe) na tabela quality_inspections (coluna é VARCHAR, não int).
- run_quality_gate_inspection: idem, com voting por maioria e conversão de
  bbox [x,y,w,h] (contrato Detector) -> [x1,y1,x2,y2] (photo_service).
"""
from __future__ import annotations

import inspect
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# Mesmo guard usado em test_inference_model_resolution.py /
# test_inference_auto_capture.py — evita stub de celery_app poluído por
# outro arquivo de teste (padrão pré-existente de test_versioning_helpers.py).
_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_QUALITY_INFERENCE_KEY = "app.infrastructure.queue.tasks.quality_inference"
_INFERENCE_KEY = "app.infrastructure.queue.tasks.inference"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_QUALITY_INFERENCE_KEY, _INFERENCE_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.infrastructure.queue.tasks import quality_inference as qi_mod  # noqa: E402

_CAMERA_ID = str(uuid4())
_TENANT_SCHEMA = "tenant_rvb"

_GET_DETECTOR_FOR_CAMERA = (
    "app.infrastructure.queue.tasks.inference._get_detector_for_camera"
)


# ── Sem ultralytics no caminho servido ─────────────────────────────────────


class TestNoUltralyticsImport:
    def test_module_source_has_no_ultralytics_import(self):
        # Via AST (não substring) — o módulo MENCIONA "ultralytics" em
        # comentários/docstrings explicando a migração; o que importa é que
        # nenhum nó Import/ImportFrom real referencie o pacote.
        import ast
        tree = ast.parse(inspect.getsource(qi_mod))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(a.name.startswith("ultralytics") for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith("ultralytics")

    def test_ultralytics_de_fato_nao_esta_instalado_neste_venv(self):
        """Confirma a premissa do teste falha-antes/passa-depois: antes desta
        mudança, `quality_inference_loop`/`run_quality_gate_inspection`
        faziam `from ultralytics import YOLO` e ImportError-avam neste
        exato venv de CI (sem ultralytics — pacote AGPL, fora de
        requirements/*.txt de produção). Depois da mudança (ONNX), os testes
        abaixo executam o fluxo inteiro com sucesso neste mesmo venv."""
        with pytest.raises(ModuleNotFoundError):
            import ultralytics  # noqa: F401


# ── Semântica OK/NOK por nome de classe ─────────────────────────────────────


class TestIsNokClass:
    def test_produto_ok_e_ok(self):
        assert qi_mod._is_nok_class("produto_ok") is False

    def test_classes_de_defeito_do_vocabulario_sao_nok(self):
        assert qi_mod._is_nok_class("produto_nok") is True
        assert qi_mod._is_nok_class("defeito_visual") is True
        assert qi_mod._is_nok_class("defeito_dimensional") is True

    def test_classe_fora_do_vocabulario_fail_closed_para_nok(self):
        # Fallback COCO do detector singleton env (câmera sem modelo
        # custom) — nunca deve resultar em falso-OK.
        assert qi_mod._is_nok_class("person") is True
        assert qi_mod._is_nok_class("bicycle") is True


# ── quality_inference_loop usa o detector ONNX via cascata WS-A6 ───────────


def _camera_cfg(**overrides) -> dict:
    cfg = {
        "rtsp_url": "rtsp://user:pass@203.0.113.10:554/stream",
        "model_quality_id": None,
        "active_module": "quality",
        "is_setup_mode": False,
        "production_order": None,
        "product_type": None,
    }
    cfg.update(overrides)
    return cfg


class _FakeRedis:
    """Redis fake: libera N iterações do `while True` via `exists`."""

    def __init__(self, active_calls: int = 1):
        self._exists_calls = 0
        self._active_calls = active_calls
        self.published: list[tuple[str, str]] = []
        self.data: dict[str, str] = {}

    def setex(self, key, _ttl, val):
        self.data[key] = val

    def exists(self, key):
        self._exists_calls += 1
        return self._exists_calls <= self._active_calls

    def get(self, key):
        return self.data.get(key)

    def set(self, key, val):
        self.data[key] = val

    def publish(self, channel, payload):
        self.published.append((channel, payload))


class _FakeCap:
    def __init__(self, frame):
        self._frame = frame
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        return True, self._frame

    def release(self):
        self.released = True


def _fake_frame():
    import numpy as np
    return np.zeros((4, 4, 3), dtype="uint8")


class TestQualityInferenceLoopOnnxDetector:
    def test_resolve_detector_via_camera_cascade_and_saves_class_name(self):
        detector = MagicMock(name="detector")
        detector.is_ready = True
        detector.predict.return_value = [
            {
                "class": "defeito_visual",
                "confidence": 0.91,
                "bbox": [1, 2, 3, 4],
                "track_id": None,
            },
        ]

        fake_redis = _FakeRedis(active_calls=1)
        saved: dict = {}

        def _fake_save_inspection(**kwargs):
            saved.update(kwargs)
            return "insp-1"

        with patch.object(
            qi_mod, "_get_camera_config", return_value=_camera_cfg()
        ), patch.object(
            qi_mod, "_get_redis", return_value=fake_redis
        ), patch.object(
            qi_mod, "_save_inspection", side_effect=_fake_save_inspection
        ), patch.object(
            qi_mod, "_get_rolling_nok_rate", return_value=0.0
        ), patch.object(
            qi_mod, "_check_cep_alert"
        ), patch(
            "app.core.validators.RTSPUrlValidator.validate"
        ), patch(
            _GET_DETECTOR_FOR_CAMERA, return_value=detector
        ) as mock_get_detector, patch(
            "cv2.VideoCapture", return_value=_FakeCap(_fake_frame())
        ):
            # Nota: upload de evidência (R2Storage.get_instance()) é um
            # caminho pré-existente fora do escopo desta task — o
            # try/except em volta dele já degrada com warning se falhar,
            # então não precisa de mock aqui para o teste passar.
            result = qi_mod.quality_inference_loop.apply(
                args=(_CAMERA_ID, _TENANT_SCHEMA)
            ).get()

        assert result is None  # loop termina sem retorno explícito
        mock_get_detector.assert_called_once_with(_CAMERA_ID)
        detector.predict.assert_called_once()
        assert saved["result"] == "nok"
        assert saved["defect_class"] == "defeito_visual"
        assert isinstance(saved["defect_class"], str)  # não mais índice int

    def test_produto_ok_resulta_em_result_ok(self):
        detector = MagicMock(name="detector")
        detector.is_ready = True
        detector.predict.return_value = [
            {"class": "produto_ok", "confidence": 0.95, "bbox": [0, 0, 1, 1], "track_id": None},
        ]

        fake_redis = _FakeRedis(active_calls=1)
        saved: dict = {}

        def _fake_save_inspection(**kwargs):
            saved.update(kwargs)
            return "insp-2"

        with patch.object(
            qi_mod, "_get_camera_config", return_value=_camera_cfg()
        ), patch.object(
            qi_mod, "_get_redis", return_value=fake_redis
        ), patch.object(
            qi_mod, "_save_inspection", side_effect=_fake_save_inspection
        ), patch.object(
            qi_mod, "_get_rolling_nok_rate", return_value=0.0
        ), patch.object(
            qi_mod, "_check_cep_alert"
        ), patch(
            "app.core.validators.RTSPUrlValidator.validate"
        ), patch(
            _GET_DETECTOR_FOR_CAMERA, return_value=detector
        ), patch(
            "cv2.VideoCapture", return_value=_FakeCap(_fake_frame())
        ):
            qi_mod.quality_inference_loop.apply(args=(_CAMERA_ID, _TENANT_SCHEMA)).get()

        assert saved["result"] == "ok"
        assert saved["defect_class"] == "produto_ok"

    def test_deteccao_abaixo_do_limiar_quality_min_confidence_e_ignorada(self):
        detector = MagicMock(name="detector")
        detector.is_ready = True
        detector.predict.return_value = [
            {"class": "defeito_visual", "confidence": 0.10, "bbox": [0, 0, 1, 1], "track_id": None},
        ]

        fake_redis = _FakeRedis(active_calls=1)

        with patch.object(
            qi_mod, "_get_camera_config", return_value=_camera_cfg()
        ), patch.object(
            qi_mod, "_get_redis", return_value=fake_redis
        ), patch.object(
            qi_mod, "_save_inspection"
        ) as mock_save, patch(
            "app.core.validators.RTSPUrlValidator.validate"
        ), patch(
            _GET_DETECTOR_FOR_CAMERA, return_value=detector
        ), patch(
            "cv2.VideoCapture", return_value=_FakeCap(_fake_frame())
        ):
            qi_mod.quality_inference_loop.apply(args=(_CAMERA_ID, _TENANT_SCHEMA)).get()

        # confidence 0.10 < QUALITY_MIN_CONFIDENCE (default 0.60) — reaplicado
        # pelo código mesmo que o detector já filtre no limiar interno dele.
        mock_save.assert_not_called()


# ── run_quality_gate_inspection usa o detector ONNX via cascata WS-A6 ──────


class TestRunQualityGateInspectionOnnxDetector:
    def _base_patches(self, detector, config=None):
        config = config or _camera_cfg()
        return (
            patch.object(qi_mod, "_get_camera_config", return_value=config),
            patch("cv2.VideoCapture", return_value=_FakeCap(_fake_frame())),
            patch(_GET_DETECTOR_FOR_CAMERA, return_value=detector),
            patch.object(qi_mod, "_get_redis", return_value=_FakeRedis()),
        )

    def test_maioria_ok_aprova_peca_sem_chamar_photo_service(self):
        detector = MagicMock(name="detector")
        detector.is_ready = True
        # Todos os frames OK (nenhuma detecção de defeito).
        detector.predict.return_value = []

        p1, p2, p3, p4 = self._base_patches(detector)
        with p1, p2, p3, p4, patch(
            "app.api.v1.quality.photo_service.get_photo_service"
        ) as mock_photo:
            result = qi_mod.run_quality_gate_inspection.apply(
                args=("piece-1", "v1", _CAMERA_ID, _TENANT_SCHEMA)
            ).get()

        assert result["status"] == "completed"
        assert result["result"] == "ok"
        mock_photo.assert_not_called()

    def test_maioria_nok_reprova_peca_e_converte_bbox_xywh_para_xyxy(self):
        detector = MagicMock(name="detector")
        detector.is_ready = True
        detector.predict.return_value = [
            {
                "class": "defeito_dimensional",
                "confidence": 0.88,
                "bbox": [10, 20, 30, 40],  # [x, y, w, h]
                "track_id": None,
            },
        ]

        photo_svc = MagicMock()
        photo_svc.save_analysis_photo.return_value = ("path.jpg", "r2/key.jpg")

        p1, p2, p3, p4 = self._base_patches(detector)
        with p1, p2, p3, p4, patch(
            "app.api.v1.quality.photo_service.get_photo_service", return_value=photo_svc
        ):
            result = qi_mod.run_quality_gate_inspection.apply(
                args=("piece-2", "v1", _CAMERA_ID, _TENANT_SCHEMA)
            ).get()

        assert result["status"] == "completed"
        assert result["result"] == "nok"
        photo_svc.save_analysis_photo.assert_called_once()
        _bytes, detections, _camera_id = photo_svc.save_analysis_photo.call_args[0]
        assert detections[0]["class"] == "defeito_dimensional"
        # [x, y, w, h] -> [x1, y1, x2, y2] = [10, 20, 40, 60]
        assert detections[0]["bbox"] == [10, 20, 40, 60]

    def test_detector_nao_pronto_retorna_erro_explicito_sem_inspecionar(self):
        detector = MagicMock(name="detector")
        detector.is_ready = False

        p1, p2, p3, p4 = self._base_patches(detector)
        with p1, p2, p3, p4:
            result = qi_mod.run_quality_gate_inspection.apply(
                args=("piece-3", "v1", _CAMERA_ID, _TENANT_SCHEMA)
            ).get()

        assert result["status"] == "error"
        assert result["reason"] == "model_load_failed"
        detector.predict.assert_not_called()
