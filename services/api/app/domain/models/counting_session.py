"""Domain model: CountingSession (sessão de contagem / carga & descarga).

Reflete o schema de public.counting_sessions (migrations 049 + 050).
Campos de carga/descarga (bay_id, truck_plate, direction, expected_count,
divergence, video_clip_url, manual_count, acceptance_status) são opcionais —
sessões de contagem genérica (EPI etc.) não os preenchem.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

# Valores válidos (espelham os CHECK constraints da migration 050)
VALID_DIRECTIONS = ("load", "unload")
VALID_ACCEPTANCE_STATUSES = ("pending", "accepted", "rejected")


@dataclass(frozen=True)
class CountingSession:
    """Sessão de contagem (DeepSORT) com campos de carga/descarga (CD-03)."""

    id: UUID
    tenant_id: UUID
    camera_id: UUID
    module_code: str
    status: str = "running"
    total_counts: dict[str, int] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    # --- Carga & Descarga (migration 050) ---
    bay_id: Optional[UUID] = None
    truck_plate: Optional[str] = None
    direction: Optional[str] = None            # 'load' | 'unload'
    expected_count: Optional[int] = None       # CD-10 (dormante na Fase 1)
    divergence: Optional[int] = None           # system - expected
    video_clip_url: Optional[str] = None       # CD-06 evidência
    manual_count: Optional[int] = None         # CD-07 aceite
    acceptance_status: Optional[str] = None    # 'pending'|'accepted'|'rejected'

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "CountingSession":
        """Constrói a partir de uma row (RealDictCursor) do repository."""
        return cls(
            id=row["id"],
            tenant_id=row["tenant_id"],
            camera_id=row["camera_id"],
            module_code=row["module_code"],
            status=row.get("status", "running"),
            total_counts=row.get("total_counts") or {},
            started_at=row.get("started_at"),
            ended_at=row.get("ended_at"),
            bay_id=row.get("bay_id"),
            truck_plate=row.get("truck_plate"),
            direction=row.get("direction"),
            expected_count=row.get("expected_count"),
            divergence=row.get("divergence"),
            video_clip_url=row.get("video_clip_url"),
            manual_count=row.get("manual_count"),
            acceptance_status=row.get("acceptance_status"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa para resposta de API (UUIDs/datas como string)."""
        data = asdict(self)
        for key in ("id", "tenant_id", "camera_id", "bay_id"):
            if data[key] is not None:
                data[key] = str(data[key])
        for key in ("started_at", "ended_at"):
            if data[key] is not None and hasattr(data[key], "isoformat"):
                data[key] = data[key].isoformat()
        return data
