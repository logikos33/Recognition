"""Domain models: Dataset (catálogo pai) e DatasetVersion."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID


@dataclass(frozen=True)
class Dataset:
    """Catálogo pai de um dataset (migration 096 — tabela datasets)."""

    id: UUID
    tenant_id: UUID
    name: str
    module_code: str
    created_at: datetime
    description: Optional[str] = None
    created_by: Optional[UUID] = None


@dataclass(frozen=True)
class DatasetVersion:
    """Versão de dataset para treinamento (tabela dataset_versions, estendida em 096)."""

    id: UUID
    user_id: UUID
    version: str
    frame_count: int
    train_count: int
    val_count: int
    test_count: int
    class_distribution: dict[str, Any]
    created_at: datetime
    # Campos adicionados em migration 096
    metadata_key: Optional[str] = None
    tenant_id: Optional[UUID] = None
    module_code: Optional[str] = None
    dataset_id: Optional[UUID] = None     # FK → datasets.id
    split: Optional[dict[str, Any]] = None
    augmentations: Optional[dict[str, Any]] = None
    coco_r2_key: Optional[str] = None     # Chave R2 do manifest COCO exportado
    export_format: Optional[str] = None   # 'coco' | 'yolo'
    status: str = "ready"
    created_by: Optional[UUID] = None
