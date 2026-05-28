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
        result = self.service.get_alerts(cam_id)
        assert len(result) == 2

    def test_get_unacknowledged(self) -> None:
        self.alert_repo.get_unacknowledged.return_value = [
            {"id": uuid4(), "acknowledged": False},
        ]
        result = self.service.get_unacknowledged()
        assert len(result) == 1

    def test_get_unacknowledged_by_camera(self) -> None:
        cam_id = uuid4()
        self.alert_repo.get_unacknowledged.return_value = []
        result = self.service.get_unacknowledged(cam_id)
        assert len(result) == 0
        self.alert_repo.get_unacknowledged.assert_called_with(cam_id, 50)

    def test_acknowledge_alert(self) -> None:
        aid = uuid4()
        self.alert_repo.acknowledge.return_value = {
            "id": aid, "acknowledged": True,
        }
        result = self.service.acknowledge_alert(aid)
        assert result["acknowledged"] is True

    def test_acknowledge_not_found(self) -> None:
        self.alert_repo.acknowledge.return_value = None
        with pytest.raises(NotFoundError):
            self.service.acknowledge_alert(uuid4())

    def test_get_alert_count(self) -> None:
        cam_id = uuid4()
        self.alert_repo.count_by_camera.return_value = 42
        result = self.service.get_alert_count(cam_id)
        assert result == 42
