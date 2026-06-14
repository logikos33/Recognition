"""Domain model: Alert."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class Alert:
    """Alerta de violação de EPI detectada."""

    id: UUID
    camera_id: UUID
    timestamp: datetime
    violations: list[dict[str, Any]]
    confidence: float
    evidence_key: str
    acknowledged: bool
    created_at: datetime
