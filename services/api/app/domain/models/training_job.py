"""Domain models: TrainingJob e TrainedModel."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.constants import TrainingStatus


@dataclass(frozen=True)
class TrainingJob:
    """Job de treinamento (tabela training_jobs, estendida em 097)."""

    id: UUID
    user_id: UUID
    preset: str
    model_size: str
    status: TrainingStatus
    progress: int
    current_epoch: int
    total_epochs: int
    metrics: dict[str, Any]
    created_at: datetime
    # Opcionais (legado + novos campos da 097)
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tenant_id: Optional[UUID] = None
    dataset_version_id: Optional[UUID] = None
    framework: Optional[str] = None       # 'rfdetr' | 'yolox' | 'ultralytics'
    base_model: Optional[str] = None
    hyperparams: Optional[dict[str, Any]] = None
    gpu_provider: Optional[str] = None    # 'vast_ai' | 'local' | 'hub'
    gpu_instance_ref: Optional[str] = None
    callback_token: Optional[str] = None  # Token HMAC p/ progress-callback externo


@dataclass(frozen=True)
class TrainedModel:
    """Modelo treinado registrado (tabela trained_models, estendida em 098)."""

    id: UUID
    user_id: UUID
    name: str
    model_path: str
    is_active: bool
    created_at: datetime
    # Opcionais legado
    job_id: Optional[UUID] = None
    map50: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    created_by: Optional[UUID] = None
    origin: Optional[str] = None
    tenant_id: Optional[UUID] = None
    # Novos campos migration 098
    framework: Optional[str] = None       # 'rfdetr' | 'yolox'
    r2_onnx_key: Optional[str] = None     # Chave R2 do ONNX exportado
    r2_weights_key: Optional[str] = None  # Chave R2 dos pesos (.pth/.pt)
    metrics: Optional[dict[str, Any]] = None
    dataset_version_id: Optional[UUID] = None
    module_code: Optional[str] = None
