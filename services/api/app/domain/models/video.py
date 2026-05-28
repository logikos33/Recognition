"""Domain model: Video."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.constants import VideoStatus


@dataclass(frozen=True)
class Video:
    """Vídeo de treinamento enviado pelo usuário."""

    id: UUID
    user_id: UUID
    filename: str
    original_filename: Optional[str]
    file_size: Optional[int]
    duration_seconds: Optional[float]
    status: VideoStatus
    frame_count: int
    error_message: Optional[str]
    created_at: datetime
