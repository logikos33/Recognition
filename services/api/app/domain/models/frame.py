"""Domain model: Frame."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.constants import FrameStatus


@dataclass(frozen=True)
class Frame:
    """Frame de treinamento — extraído de vídeo, uploadado, auto-capturado ou de NVR.

    video_id é Optional desde migration 094 (frames de upload/auto-captura não têm vídeo pai).
    """

    id: UUID
    frame_number: int
    filename: str
    is_annotated: bool
    created_at: datetime
    # Campos opcionais (defaults para retrocompat com código legado)
    video_id: Optional[UUID] = None
    timestamp_seconds: Optional[float] = None
    status: FrameStatus = FrameStatus.RAW
    # Campos adicionados em migration 094
    source: Optional[str] = None           # 'video' | 'upload' | 'auto' | 'nvr'
    r2_key: Optional[str] = None           # Chave R2 canônica do frame
    camera_id: Optional[UUID] = None       # Câmera de origem (auto-captura/nvr)
    recorder_id: Optional[UUID] = None     # NVR/DVR de origem
    width: Optional[int] = None            # Largura em pixels
    height: Optional[int] = None           # Altura em pixels
    model_confidence: Optional[float] = None  # Confiança da detecção que gerou o frame
    captured_at: Optional[datetime] = None    # Timestamp de captura original
    module_code: Optional[str] = None
    tenant_id: Optional[UUID] = None
