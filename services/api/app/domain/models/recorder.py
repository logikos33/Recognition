"""Domain model: Recorder (NVR/DVR — migration 099)."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.constants import RecorderProtocol, RecorderStatus


@dataclass(frozen=True)
class Recorder:
    """NVR/DVR que fornece playback gravado para extração de frames (ADR-0034).

    password_encrypted segue o padrão Fernet(CAMERA_SECRET_KEY) de
    camera_service._encrypt_password — nunca expor em respostas de API.
    """

    id: UUID
    tenant_id: UUID
    name: str
    host: str
    port: int
    created_at: datetime
    protocol: RecorderProtocol = RecorderProtocol.ONVIF
    status: RecorderStatus = RecorderStatus.UNKNOWN
    channels: int = 0
    username: Optional[str] = None
    password_encrypted: Optional[str] = None
    manufacturer: Optional[str] = None
    retention_days: Optional[int] = None
    last_tested_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_by: Optional[UUID] = None
