"""Domain model: Annotation."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Annotation:
    """Anotação YOLO de um frame (bounding box normalizado)."""

    id: UUID
    frame_id: UUID
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float
    created_at: datetime


@dataclass(frozen=True)
class YoloClass:
    """Classe de detecção YOLO customizada."""

    id: int
    user_id: UUID
    name: str
    color: str
    created_at: datetime
