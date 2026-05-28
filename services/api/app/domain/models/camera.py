"""Domain model: Camera."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID



@dataclass(frozen=True)
class Camera:
    """Câmera IP para monitoramento."""

    id: UUID
    user_id: UUID
    name: str
    location: Optional[str]
    description: Optional[str]
    manufacturer: str
    host: str
    port: int
    username: str
    channel: int
    subtype: int
    rtsp_url_override: Optional[str]
    is_active: bool
    last_seen: Optional[datetime]
    created_at: datetime
