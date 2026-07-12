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
    # Atribuição de modelo por módulo (migration 026 / Task 045)
    model_epi_id: Optional[UUID] = None
    model_quality_id: Optional[UUID] = None
    model_counting_id: Optional[UUID] = None
    # Controle de FPS e qualidade por câmera (migration 052 / deliverable j)
    fps_target: int = 5
    quality_preset: str = "medium"
    # task-067: subtype exclusivo do live view (migration 092) — independente
    # de `subtype` (detecção/inferência/gravação). Default 1 = substream.
    live_view_subtype: int = 1
