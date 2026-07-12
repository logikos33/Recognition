"""Domain model: YoloClass (yolo_classes, estendida em migration 093).

Versão tenant-scoped da classe legada em annotation.py (que permanece por
retrocompat) — nova fonte canônica para o pipeline de treinamento.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class YoloClass:
    """Classe de detecção customizada, escopada por tenant+módulo (093).

    tenant_id é Optional apenas para linhas legadas ainda não backfilladas;
    module_code tem default 'epi' (NOT NULL DEFAULT no schema).
    """

    id: int
    user_id: UUID
    name: str
    color: str
    created_at: datetime
    tenant_id: Optional[UUID] = None
    module_code: str = "epi"
