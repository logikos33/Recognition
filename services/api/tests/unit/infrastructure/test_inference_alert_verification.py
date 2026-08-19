"""
Tests: tasks/inference.py — disparo da verificação por IA (#132).

Contexto de por que estes testes existem aqui e não no socket_bridge:

Até agosto/2026 havia DOIS caminhos gravando `alerts` para a mesma detecção ao
vivo — `inference.py::_save_alert` (worker, via AlertRepository) e
`socket_bridge.py::_create_alert_and_verify` (thread da API, SQL cru). Sem
coordenação entre os processos, toda violação com confiança abaixo do limiar
de verificação virava DUAS linhas: justamente os casos borderline, que são os
que mais precisam de revisão humana.

O segundo caminho foi removido. O disparo de `verify_alert`, que só ele fazia,
mora agora ao lado do único INSERT — e é isto que estes testes fixam.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_INFERENCE_KEY = "app.infrastructure.queue.tasks.inference"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_INFERENCE_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

# verify_alert é importado lazy dentro da função; celery não está instalado.
_mock_verify_task = MagicMock()
_mock_verification_mod = MagicMock()
_mock_verification_mod.verify_alert = _mock_verify_task
sys.modules["app.infrastructure.queue.tasks.verification"] = _mock_verification_mod

from app.infrastructure.queue.tasks import inference as inference_mod  # noqa: E402

_CAMERA_ID = str(uuid4())
_ALERT_ID = uuid4()
_TENANT_ID = "99999999-8888-7777-6666-555555555555"


class TestQueueVerificationIfLowConfidence:
    def setup_method(self) -> None:
        _mock_verify_task.delay.reset_mock()

    def _row(self) -> dict:
        return {"id": _ALERT_ID}

    def test_baixa_confianca_enfileira(self, monkeypatch) -> None:
        monkeypatch.setattr(inference_mod, "_VERIFICATION_THRESHOLD", 0.85)
        monkeypatch.setattr(inference_mod, "_VIOLATION_CLASSES", {"no_helmet"})

        inference_mod._queue_verification_if_low_confidence(
            self._row(), _CAMERA_ID, [{"class": "no_helmet", "confidence": 0.60}], "epi"
        )

        _mock_verify_task.delay.assert_called_once_with(
            alert_id=str(_ALERT_ID),
            camera_id=_CAMERA_ID,
            class_name="no_helmet",
            confidence=0.60,
            module_code="epi",
        )

    def test_acima_do_limiar_NAO_enfileira(self, monkeypatch) -> None:
        monkeypatch.setattr(inference_mod, "_VERIFICATION_THRESHOLD", 0.85)
        monkeypatch.setattr(inference_mod, "_VIOLATION_CLASSES", {"no_helmet"})

        inference_mod._queue_verification_if_low_confidence(
            self._row(), _CAMERA_ID, [{"class": "no_helmet", "confidence": 0.95}], "epi"
        )

        _mock_verify_task.delay.assert_not_called()

    def test_escolhe_a_maior_confianca_entre_as_abaixo_do_limiar(self, monkeypatch) -> None:
        """Preserva a seleção que o caminho removido fazia — max() entre as que
        estão abaixo do limiar, não o mínimo global."""
        monkeypatch.setattr(inference_mod, "_VERIFICATION_THRESHOLD", 0.85)
        monkeypatch.setattr(inference_mod, "_VIOLATION_CLASSES", {"no_helmet", "no_vest"})

        inference_mod._queue_verification_if_low_confidence(
            self._row(),
            _CAMERA_ID,
            [
                {"class": "no_helmet", "confidence": 0.40},
                {"class": "no_vest", "confidence": 0.80},
                {"class": "no_helmet", "confidence": 0.99},  # acima: fora da escolha
            ],
            "epi",
        )

        _, kwargs = _mock_verify_task.delay.call_args
        assert kwargs["class_name"] == "no_vest"
        assert kwargs["confidence"] == 0.80

    def test_usa_VIOLATION_CLASSES_e_nao_o_prefixo_no_(self, monkeypatch) -> None:
        """O caminho removido filtrava por `class.startswith("no_")`, que NÃO é
        a mesma coisa que VIOLATION_CLASSES. Com a configuração documentada
        para teste com COCO (VIOLATION_CLASSES=person) o alerta nascia por uma
        regra e era verificado por outra — a violação real ficava sem revisão."""
        monkeypatch.setattr(inference_mod, "_VERIFICATION_THRESHOLD", 0.85)
        monkeypatch.setattr(inference_mod, "_VIOLATION_CLASSES", {"person"})

        inference_mod._queue_verification_if_low_confidence(
            self._row(), _CAMERA_ID, [{"class": "person", "confidence": 0.50}], "epi"
        )

        _mock_verify_task.delay.assert_called_once()
        assert _mock_verify_task.delay.call_args.kwargs["class_name"] == "person"

    def test_classe_fora_de_VIOLATION_CLASSES_nao_enfileira(self, monkeypatch) -> None:
        monkeypatch.setattr(inference_mod, "_VERIFICATION_THRESHOLD", 0.85)
        monkeypatch.setattr(inference_mod, "_VIOLATION_CLASSES", {"no_helmet"})

        inference_mod._queue_verification_if_low_confidence(
            self._row(), _CAMERA_ID, [{"class": "helmet", "confidence": 0.10}], "epi"
        )

        _mock_verify_task.delay.assert_not_called()

    def test_sem_id_no_row_nao_enfileira(self, monkeypatch) -> None:
        """Alerta sem id devolvido não tem o que verificar — e passar None pro
        Celery viraria uma task que falha longe daqui."""
        monkeypatch.setattr(inference_mod, "_VERIFICATION_THRESHOLD", 0.85)
        monkeypatch.setattr(inference_mod, "_VIOLATION_CLASSES", {"no_helmet"})

        inference_mod._queue_verification_if_low_confidence(
            {}, _CAMERA_ID, [{"class": "no_helmet", "confidence": 0.1}], "epi"
        )

        _mock_verify_task.delay.assert_not_called()

    def test_falha_no_enfileiramento_nao_propaga(self, monkeypatch) -> None:
        """O alerta JÁ foi gravado quando esta função roda — estourar aqui
        transformaria uma verificação perdida numa exceção no loop de
        inferência."""
        monkeypatch.setattr(inference_mod, "_VERIFICATION_THRESHOLD", 0.85)
        monkeypatch.setattr(inference_mod, "_VIOLATION_CLASSES", {"no_helmet"})
        _mock_verify_task.delay.side_effect = RuntimeError("broker down")
        try:
            inference_mod._queue_verification_if_low_confidence(
                self._row(), _CAMERA_ID, [{"class": "no_helmet", "confidence": 0.1}], "epi"
            )
        finally:
            _mock_verify_task.delay.side_effect = None


class TestSaveAlertEnfileiraVerificacao:
    def setup_method(self) -> None:
        _mock_verify_task.delay.reset_mock()

    def test_save_alert_enfileira_com_o_id_devolvido_pelo_repository(
        self, monkeypatch
    ) -> None:
        """A ponta que fecha o #132: o alerta gravado pelo worker é o MESMO que
        vai para a fila de verificação. Antes, quem verificava era a linha
        duplicada criada pela API, e a do worker ficava sem revisão nenhuma."""
        monkeypatch.setattr(inference_mod, "_VERIFICATION_THRESHOLD", 0.85)
        monkeypatch.setattr(inference_mod, "_VIOLATION_CLASSES", {"no_helmet"})
        monkeypatch.setattr(inference_mod, "_auto_capture_frame", lambda *a, **kw: None)
        monkeypatch.setattr(
            inference_mod, "_camera_tenant_module", lambda pool, cam: (_TENANT_ID, "epi")
        )

        mock_cv2 = MagicMock()
        mock_cv2.imencode.return_value = (True, MagicMock(tobytes=lambda: b"jpeg"))
        mock_alert_repo = MagicMock()
        mock_alert_repo.create.return_value = {"id": _ALERT_ID}

        with patch.dict(sys.modules, {"cv2": mock_cv2}), patch(
            "app.infrastructure.database.connection.DatabasePool"
        ) as mock_dbpool_cls, patch(
            "app.infrastructure.database.repositories.alert_repository.AlertRepository",
            return_value=mock_alert_repo,
        ), patch(
            "app.infrastructure.storage.local_storage.get_storage", return_value=MagicMock()
        ):
            mock_dbpool_cls.get_instance.return_value = MagicMock()
            inference_mod._save_alert(
                _CAMERA_ID, [{"class": "no_helmet", "confidence": 0.55}], MagicMock()
            )

        mock_alert_repo.create.assert_called_once()
        _mock_verify_task.delay.assert_called_once()
        assert _mock_verify_task.delay.call_args.kwargs["alert_id"] == str(_ALERT_ID)
