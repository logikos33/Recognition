"""Tests: InferenceService."""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.exceptions import NotFoundError
from app.domain.services.inference_service import InferenceService


class TestInferenceService:
    """Testes para InferenceService."""

    def setup_method(self) -> None:
        self.alert_repo = MagicMock()
        self.service = InferenceService(self.alert_repo)

    def test_get_alerts(self) -> None:
        cam_id = uuid4()
        self.alert_repo.get_by_camera.return_value = [
            {"id": uuid4(), "confidence": 0.9},
            {"id": uuid4(), "confidence": 0.8},
        ]
        result = self.service.get_alerts(cam_id, "tenant-a")
        assert len(result) == 2

    def test_get_alerts_leva_o_tenant_ao_repositorio(self) -> None:
        """C-01, leitura. O irmão `acknowledge` já levava o tenant; a LEITURA
        não — e `GET /api/cameras/<id>/alerts` devolvia alerta de qualquer
        tenant pelo camera_id (#545)."""
        cam_id = uuid4()
        self.alert_repo.get_by_camera.return_value = []
        self.service.get_alerts(cam_id, "tenant-a", 10, 5)
        self.alert_repo.get_by_camera.assert_called_once_with(
            cam_id, "tenant-a", 10, 5
        )

    def test_get_unacknowledged(self) -> None:
        self.alert_repo.get_unacknowledged.return_value = [
            {"id": uuid4(), "acknowledged": False},
        ]
        result = self.service.get_unacknowledged("tenant-a")
        assert len(result) == 1

    def test_get_unacknowledged_by_camera(self) -> None:
        cam_id = uuid4()
        self.alert_repo.get_unacknowledged.return_value = []
        result = self.service.get_unacknowledged("tenant-a", cam_id)
        assert len(result) == 0
        # o tenant chega ao repositório: antes ficava None e virava a string
        # "None" contra uma coluna uuid
        self.alert_repo.get_unacknowledged.assert_called_with(cam_id, 50, "tenant-a")

    def test_acknowledge_alert(self) -> None:
        aid = uuid4()
        self.alert_repo.acknowledge.return_value = {
            "id": aid, "acknowledged": True,
        }
        result = self.service.acknowledge_alert(aid, "tenant-a")
        assert result["acknowledged"] is True

    def test_acknowledge_leva_o_tenant_ao_repositorio(self) -> None:
        """C-01: sem o tenant no UPDATE, reconhecer alerta de outro tenant passa."""
        aid = uuid4()
        self.alert_repo.acknowledge.return_value = {"id": aid, "acknowledged": True}
        self.service.acknowledge_alert(aid, "tenant-a")
        self.alert_repo.acknowledge.assert_called_once_with(aid, "tenant-a")

    def test_acknowledge_not_found(self) -> None:
        self.alert_repo.acknowledge.return_value = None
        with pytest.raises(NotFoundError):
            self.service.acknowledge_alert(uuid4(), "tenant-a")

    def test_get_alert_count(self) -> None:
        cam_id = uuid4()
        self.alert_repo.count_by_camera.return_value = 42
        result = self.service.get_alert_count(cam_id)
        assert result == 42
