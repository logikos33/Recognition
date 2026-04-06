"""
EPI Monitor V2 — Dataset Service.

Lógica de versionamento de datasets para treinamento YOLO.
"""
import logging
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.infrastructure.database.repositories.dataset_repository import (
    DatasetRepository,
)

logger = logging.getLogger(__name__)


class DatasetService:
    """Use cases de dataset versioning."""

    def __init__(self, dataset_repo: DatasetRepository) -> None:
        self._dataset_repo = dataset_repo

    def create_version(
        self,
        user_id: UUID,
        version: str,
        frame_count: int,
        train_count: int,
        val_count: int,
        test_count: int,
        class_distribution: dict[str, int],
        metadata_key: str | None = None,
    ) -> dict:
        """Cria nova versão de dataset."""
        data = {
            "user_id": user_id,
            "version": version,
            "frame_count": frame_count,
            "train_count": train_count,
            "val_count": val_count,
            "test_count": test_count,
            "class_distribution": class_distribution,
            "metadata_key": metadata_key,
        }
        result = self._dataset_repo.create(data)
        result["id"] = str(result["id"])
        return result

    def list_versions(self, user_id: UUID) -> list[dict]:
        """Lista versões de dataset do usuário."""
        versions = self._dataset_repo.get_by_user(user_id)
        for v in versions:
            v["id"] = str(v["id"])
        return versions

    def get_version(self, version_id: UUID) -> dict:
        """Busca versão por ID."""
        version = self._dataset_repo.get_by_id(version_id)
        if not version:
            raise NotFoundError("Dataset version", str(version_id))
        version["id"] = str(version["id"])
        return version

    def get_latest(self, user_id: UUID) -> dict | None:
        """Busca versão mais recente do usuário."""
        version = self._dataset_repo.get_latest(user_id)
        if version:
            version["id"] = str(version["id"])
        return version
