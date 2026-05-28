"""Repository: Dataset Versions."""
import json
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class DatasetRepository(BaseRepository):
    """Queries SQL para tabela dataset_versions."""

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Cria versão de dataset."""
        return self._execute_mutation(
            "INSERT INTO dataset_versions "
            "(user_id, version, frame_count, train_count, val_count, "
            "test_count, class_distribution, metadata_key) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s) RETURNING *",
            (
                str(data["user_id"]),
                data["version"],
                data["frame_count"],
                data["train_count"],
                data["val_count"],
                data["test_count"],
                json.dumps(data.get("class_distribution", {})),
                data.get("metadata_key"),
            ),
        )  # type: ignore[return-value]

    def get_by_id(self, version_id: UUID) -> Optional[dict[str, Any]]:
        """Busca versão por ID."""
        return self._execute_one(
            "SELECT * FROM dataset_versions WHERE id = %s",
            (str(version_id),),
        )

    def get_by_user(self, user_id: UUID) -> list[dict[str, Any]]:
        """Lista versões do usuário."""
        return self._execute(
            "SELECT * FROM dataset_versions WHERE user_id = %s "
            "ORDER BY created_at DESC",
            (str(user_id),),
        )

    def get_latest(self, user_id: UUID) -> Optional[dict[str, Any]]:
        """Busca versão mais recente do usuário."""
        return self._execute_one(
            "SELECT * FROM dataset_versions WHERE user_id = %s "
            "ORDER BY created_at DESC LIMIT 1",
            (str(user_id),),
        )
