"""Domain model: Frame."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.constants import FrameStatus


@dataclass(frozen=True)
class Frame:
    """Frame extraído de um vídeo de treinamento."""

    id: UUID
    video_id: UUID
    frame_number: int
    filename: str
    timestamp_seconds: Optional[float]
    status: FrameStatus
    is_annotated: bool
    created_at: datetime
