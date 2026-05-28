"""Domain model: TrainingJob and TrainedModel."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.constants import TrainingStatus


@dataclass(frozen=True)
class TrainingJob:
    """Job de treinamento YOLOv8."""

    id: UUID
    user_id: UUID
    preset: str
    model_size: str
    status: TrainingStatus
    progress: int
    current_epoch: int
    total_epochs: int
    metrics: dict[str, Any]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime


@dataclass(frozen=True)
class TrainedModel:
    """Modelo YOLO treinado e registrado."""

    id: UUID
    user_id: UUID
    job_id: Optional[UUID]
    name: str
    model_path: str
    map50: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    is_active: bool
    created_at: datetime
