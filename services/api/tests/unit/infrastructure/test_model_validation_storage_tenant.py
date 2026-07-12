"""Tests: tasks/model_validation.py — storage tenant-aware (fix R2/integrações).

validate_onnx baixava o ONNX sempre via env de plataforma (get_storage()
sem tenant_id) — quebra "BYO por tenant" pra modelos treinados com R2
próprio do tenant. Cobertura:
  test_download_uses_model_tenant_id  — get_storage recebe tenant_id do model
  test_model_not_found                — status 'error', não chama storage
  test_missing_onnx_key_marks_failed  — status 'failed', não chama storage
"""
from unittest.mock import MagicMock, patch

from app.infrastructure.queue.tasks import model_validation


def _make_model(**overrides):
    model = {
        "id": "model-1",
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "r2_onnx_key": "models/tenant/model.onnx",
    }
    model.update(overrides)
    return model


class TestDownloadUsesModelTenantId:
    def test_download_uses_model_tenant_id(self) -> None:
        model = _make_model()
        repo = MagicMock()
        repo.get_by_id.return_value = model

        fake_storage = MagicMock()
        fake_storage.download_bytes.return_value = b"onnx-bytes"

        with patch.object(model_validation, "_get_registry_repo", return_value=repo):
            with patch(
                "app.infrastructure.storage.local_storage.get_storage",
                return_value=fake_storage,
            ) as mock_get_storage:
                with patch("onnxruntime.InferenceSession") as mock_session_cls:
                    mock_session = MagicMock()
                    mock_input = MagicMock(shape=[1, 3, 640, 640], type="tensor(float)", name="images")
                    mock_session.get_inputs.return_value = [mock_input]
                    mock_session.run.return_value = [MagicMock()]
                    mock_session_cls.return_value = mock_session

                    result = model_validation.validate_onnx("model-1")

        mock_get_storage.assert_called_once_with(model["tenant_id"])
        assert result["status"] == "completed"
        assert result["validated"] is True
        repo.mark_validation.assert_called_once_with("model-1", True)


class TestModelNotFound:
    def test_model_not_found_never_touches_storage(self) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = None

        with patch.object(model_validation, "_get_registry_repo", return_value=repo):
            with patch(
                "app.infrastructure.storage.local_storage.get_storage"
            ) as mock_get_storage:
                result = model_validation.validate_onnx("missing")

        mock_get_storage.assert_not_called()
        assert result == {
            "status": "error",
            "model_id": "missing",
            "reason": "model_not_found",
        }


class TestMissingOnnxKey:
    def test_missing_onnx_key_marks_failed_without_storage(self) -> None:
        model = _make_model(r2_onnx_key=None)
        repo = MagicMock()
        repo.get_by_id.return_value = model

        with patch.object(model_validation, "_get_registry_repo", return_value=repo):
            with patch(
                "app.infrastructure.storage.local_storage.get_storage"
            ) as mock_get_storage:
                result = model_validation.validate_onnx("model-1")

        mock_get_storage.assert_not_called()
        assert result["status"] == "failed"
        assert result["validated"] is False
        repo.mark_validation.assert_called_once_with(
            "model-1", False, error="r2_onnx_key ausente no registro"
        )
