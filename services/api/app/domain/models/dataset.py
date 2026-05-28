"""Domain model: Dataset and DatasetVersion."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID


@dataclass(frozen=True)
class DatasetVersion:
    """Versão de dataset para treinamento YOLO."""

    id: UUID
    user_id: UUID
    version: str
    frame_count: int
    train_count: int
    val_count: int
    test_count: int
    class_distribution: dict[str, int]
    metadata_key: str
    created_at: datetime
