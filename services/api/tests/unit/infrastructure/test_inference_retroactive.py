"""
Tests: tasks/inference.py — retroactive_inference (Nível 1: inferência sobre
frames JÁ ARMAZENADOS, sem tocar no box).

Cobre:
- REUSO do caminho ao vivo: detector por câmera (_get_detector_for_camera),
  escopo (_no_escopo_da_camera), calibração/polaridade (_has_violation) e
  escrita (_save_alert) — nenhuma regra de violação reimplementada aqui.
- Procedência: `_save_alert` recebe `captured_at` = hora REAL da captura do
  frame (não NOW()) e `skip_auto_capture=True` — é o par que
  `ProcedenciaBadge.classificarLatencia` no front lê para pintar "coleta
  retroativa"; sem isto o alerta pareceria ao vivo.
- Idempotência: `AlertRepository.exists_at_capture` pula frame já processado
  — rodar duas vezes não duplica alerta.
- Falha alta: sem detector carregado, NENHUM alerta nasce (zero dado
  mocado); se TODAS as tentativas da janela caírem nisso, a task levanta
  RuntimeError em vez de devolver silenciosamente zero alerta.
"""
from __future__ import annotations

import sys
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# Mesmo guard de test_inference_model_resolution.py / test_inference_auto_capture.py
# — evita stub de celery_app poluído por outro arquivo de teste.
_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_INFERENCE_KEY = "app.infrastructure.queue.tasks.inference"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_INFERENCE_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.infrastructure.queue.tasks import inference as inference_mod  # noqa: E402

_TENANT_ID = "99999999-8888-7777-6666-555555555555"
_CAMERA_ID = str(uuid4())


def _frame(**overrides) -> dict:
    frame = {
        "id": str(uuid4()),
        "camera_id": _CAMERA_ID,
        "r2_key": "training-images/tenant/nvr/rec/x.jpg",
        "captured_at": datetime(2026, 9, 1, 3, 0, 0),
        "module_code": "epi",
    }
    frame.update(overrides)
    return frame


class _FakeDetector:
    """Dublê mínimo do contrato `Detector` — is_ready / predict / ultimo_erro."""

    def __init__(self, ready: bool = True, detections: list | None = None):
        self.is_ready = ready
        self._detections = detections if detections is not None else [
            {"class": "Sem Luvas", "confidence": 0.9}
        ]
        self.ultimo_erro: str | None = None

    def predict(self, frame):  # noqa: ARG002
        return list(self._detections)


class _Harness:
    """Roda `retroactive_inference` com toda a fronteira de I/O mockada,
    espiando as chamadas aos helpers REUSADOS do caminho ao vivo."""

    def __init__(
        self,
        frames: list[dict] | None = None,
        exists_at_capture: bool = False,
        detector: "_FakeDetector | None" = None,
        has_violation: bool = True,
    ):
        self.frames = frames if frames is not None else [_frame()]
        self.frame_repo = MagicMock()
        self.frame_repo.get_by_tenant_source_daterange.return_value = self.frames
        self.alert_repo = MagicMock()
        self.alert_repo.exists_at_capture.return_value = exists_at_capture
        self.storage = MagicMock()
        self.storage.download_bytes.return_value = b"\xff\xd8\xff\xd9"
        self.imdecode_return = MagicMock(name="frame_bgr")

        self.get_detector_mock = MagicMock(
            return_value=detector if detector is not None else _FakeDetector()
        )
        self.has_violation_mock = MagicMock(return_value=has_violation)
        self.escopo_mock = MagicMock(side_effect=lambda _cam, d: d)
        self.save_alert_mock = MagicMock(return_value={"id": "alert-1"})

    def run(self, **kwargs) -> dict:
        mock_cv2 = MagicMock()
        mock_cv2.imdecode.return_value = self.imdecode_return
        mock_cv2.IMREAD_COLOR = 1

        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {"cv2": mock_cv2}))

            mock_dbpool_cls = stack.enter_context(
                patch("app.infrastructure.database.connection.DatabasePool")
            )
            mock_dbpool_cls.get_instance.return_value = MagicMock()

            stack.enter_context(patch(
                "app.infrastructure.database.repositories.frame_repository.FrameRepository",
                return_value=self.frame_repo,
            ))
            stack.enter_context(patch(
                "app.infrastructure.database.repositories.alert_repository.AlertRepository",
                return_value=self.alert_repo,
            ))
            stack.enter_context(patch(
                "app.infrastructure.storage.local_storage.get_storage",
                return_value=self.storage,
            ))
            stack.enter_context(patch.object(
                inference_mod, "_get_detector_for_camera", self.get_detector_mock,
            ))
            stack.enter_context(patch.object(
                inference_mod, "_has_violation", self.has_violation_mock,
            ))
            stack.enter_context(patch.object(
                inference_mod, "_no_escopo_da_camera", self.escopo_mock,
            ))
            stack.enter_context(patch.object(
                inference_mod, "_save_alert", self.save_alert_mock,
            ))

            defaults = dict(
                tenant_id=_TENANT_ID,
                date_from="2026-09-01T00:00:00",
                date_to="2026-09-02T00:00:00",
                module_code="epi",
            )
            defaults.update(kwargs)
            return inference_mod.retroactive_inference(**defaults)


class TestCriaAlertaComViolacao:
    def test_creates_alert_when_violation_detected(self):
        h = _Harness()
        stats = h.run()
        assert stats["alertas_criados"] == 1
        assert stats["frames_total"] == 1
        h.save_alert_mock.assert_called_once()

    def test_no_alert_when_has_violation_false(self):
        """Frame classificado como observação/conformidade (yolo_classes.
        is_violation != TRUE) não vira alerta."""
        h = _Harness(has_violation=False)
        stats = h.run()
        assert stats["alertas_criados"] == 0
        assert stats["sem_deteccao_violacao"] == 1
        h.save_alert_mock.assert_not_called()


class TestReusaCalibracaoDoCaminhoAoVivo:
    def test_has_violation_called_with_camera_and_scoped_detections(self):
        """A régua de violação é `_has_violation` (yolo_classes.is_violation,
        ADR-0065) — a task não reimplementa polaridade."""
        h = _Harness(detector=_FakeDetector(
            detections=[{"class": "Sem Luvas", "confidence": 0.9}]
        ))
        h.run()
        h.has_violation_mock.assert_called_once()
        camera_arg, detections_arg = h.has_violation_mock.call_args[0]
        assert camera_arg == _CAMERA_ID
        assert detections_arg[0]["class"] == "Sem Luvas"
        # bbox_unidade carimbado ANTES do escopo/violação, mesmo contrato do
        # caminho ao vivo (domain/detectors/base.py).
        assert detections_arg[0]["bbox_unidade"] == inference_mod._BBOX_UNIDADE

    def test_escopo_da_camera_applied_before_has_violation(self):
        h = _Harness()
        h.run()
        h.escopo_mock.assert_called_once()
        assert h.escopo_mock.call_args[0][0] == _CAMERA_ID

    def test_detector_resolved_via_camera_cascade(self):
        """Nenhum backend/modelo hardcoded aqui — mesma cascata WS-A6 do
        caminho ao vivo."""
        h = _Harness()
        h.run()
        h.get_detector_mock.assert_called_once_with(_CAMERA_ID)


class TestProcedenciaMarcada:
    def test_save_alert_receives_frame_real_captured_at(self):
        """`alerts.timestamp` tem de nascer com a hora REAL da captura, não
        NOW() — é o que faz `ProcedenciaBadge` pintar 'coleta retroativa'."""
        captured = datetime(2026, 8, 20, 12, 0, 0)
        h = _Harness(frames=[_frame(captured_at=captured)])
        h.run()
        _, kwargs = h.save_alert_mock.call_args
        assert kwargs["captured_at"] == captured

    def test_save_alert_skips_auto_capture(self):
        """O frame já É uma amostra de treino (source='nvr') — reinserir
        como 'auto' duplicaria a imagem e roubaria cota do teto diário."""
        h = _Harness()
        h.run()
        _, kwargs = h.save_alert_mock.call_args
        assert kwargs["skip_auto_capture"] is True


class TestIdempotencia:
    def test_skips_frame_with_existing_alert(self):
        h = _Harness(exists_at_capture=True)
        stats = h.run()
        assert stats["pulados_existentes"] == 1
        assert stats["alertas_criados"] == 0
        h.get_detector_mock.assert_not_called()
        h.save_alert_mock.assert_not_called()

    def test_running_twice_does_not_duplicate(self):
        """Falha-antes/passa-depois da idempotência: 1ª rodada cria o
        alerta; 2ª rodada (mesmo frame, agora `exists_at_capture=True`
        simulando o que a 1ª gravou) não chama `_save_alert` de novo."""
        frame = _frame()

        h1 = _Harness(frames=[frame], exists_at_capture=False)
        stats1 = h1.run()
        assert stats1["alertas_criados"] == 1
        h1.save_alert_mock.assert_called_once()

        h2 = _Harness(frames=[frame], exists_at_capture=True)
        stats2 = h2.run()
        assert stats2["alertas_criados"] == 0
        assert stats2["pulados_existentes"] == 1
        h2.save_alert_mock.assert_not_called()


class TestFalhaAlta:
    def test_raises_when_all_frames_have_no_detector(self):
        """Zero alerta possível é indistinguível de sucesso silencioso —
        tem de falhar alto, nunca fingir que rodou. Um único frame sem
        detector JÁ é 100% da janela, então a task levanta — não devolve
        stats silenciosamente."""
        h = _Harness(detector=_FakeDetector(ready=False))
        with pytest.raises(RuntimeError, match="detector"):
            h.run()
        h.save_alert_mock.assert_not_called()

    def test_does_not_raise_when_some_frames_succeed(self):
        frames = [_frame(), _frame(id=str(uuid4()))]
        h = _Harness(frames=frames)
        ready = _FakeDetector(detections=[{"class": "Sem Luvas", "confidence": 0.9}])
        not_ready = _FakeDetector(ready=False)
        h.get_detector_mock.side_effect = [ready, not_ready]
        stats = h.run()
        assert stats["alertas_criados"] == 1
        assert stats["sem_detector"] == 1

    def test_all_frames_skipped_as_existing_does_not_raise(self):
        """Janela inteira já processada não é 'sem detector' — é sucesso
        idempotente, e não deve levantar."""
        h = _Harness(exists_at_capture=True, detector=_FakeDetector(ready=False))
        stats = h.run()
        assert stats["pulados_existentes"] == 1
        assert stats["sem_detector"] == 0


class TestErrosDeFrame:
    def test_storage_download_failure_counts_as_erro_frame(self):
        h = _Harness()
        h.storage.download_bytes.side_effect = RuntimeError("r2 indisponível")
        stats = h.run()
        assert stats["erro_frame"] == 1
        assert stats["alertas_criados"] == 0
        h.save_alert_mock.assert_not_called()

    def test_frame_decode_none_counts_as_erro_frame(self):
        h = _Harness()
        h.imdecode_return = None
        stats = h.run()
        assert stats["erro_frame"] == 1
        h.save_alert_mock.assert_not_called()

    def test_predict_error_counts_as_erro_frame_not_no_detector(self):
        class _ErroDetector(_FakeDetector):
            def predict(self, frame):  # noqa: ARG002
                self.ultimo_erro = "onnxruntime explodiu"
                return []

        h = _Harness(detector=_ErroDetector())
        stats = h.run()
        assert stats["erro_frame"] == 1
        assert stats["sem_detector"] == 0
        assert stats["alertas_criados"] == 0
