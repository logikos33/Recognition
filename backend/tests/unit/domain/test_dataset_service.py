"""Tests: DatasetService."""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.exceptions import NotFoundError
from app.domain.services.dataset_service import DatasetService


class TestDatasetService:
    """Testes para DatasetService."""

    def setup_method(self) -> None:
        self.dataset_repo = MagicMock()
        self.service = DatasetService(self.dataset_repo)

    def test_create_version(self) -> None:
        vid = uuid4()
        uid = uuid4()
        self.dataset_repo.create.return_value = {
            "id": vid, "version": "v1.0.0",
            "frame_count": 100, "train_count": 70,
            "val_count": 20, "test_count": 10,
        }
        result = self.service.create_version(
            user_id=uid, version="v1.0.0",
            frame_count=100, train_count=70,
            val_count=20, test_count=10,
            class_distribution={"helmet": 50, "vest": 50},
        )
        assert result["version"] == "v1.0.0"
        assert result["id"] == str(vid)

    def test_list_versions(self) -> None:
        uid = uuid4()
        self.dataset_repo.get_by_user.return_value = [
            {"id": uuid4(), "version": "v1.0.0"},
            {"id": uuid4(), "version": "v1.1.0"},
        ]
        result = self.service.list_versions(uid)
        assert len(result) == 2

    def test_get_version_success(self) -> None:
        vid = uuid4()
        self.dataset_repo.get_by_id.return_value = {
            "id": vid, "version": "v1.0.0",
        }
        result = self.service.get_version(vid)
        assert result["id"] == str(vid)

    def test_get_version_not_found(self) -> None:
        self.dataset_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.service.get_version(uuid4())

    def test_get_latest(self) -> None:
        uid = uuid4()
        self.dataset_repo.get_latest.return_value = {
            "id": uuid4(), "version": "v2.0.0",
        }
        result = self.service.get_latest(uid)
        assert result is not None
        assert result["version"] == "v2.0.0"

    def test_get_latest_none(self) -> None:
        self.dataset_repo.get_latest.return_value = None
        result = self.service.get_latest(uuid4())
        assert result is None
