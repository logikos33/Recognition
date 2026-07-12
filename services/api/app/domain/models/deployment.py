"""Domain model: ModelDeployment (migration 100)."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.constants import DeploymentStatus


@dataclass(frozen=True)
class ModelDeployment:
    """Vínculo auditável modelo↔câmera↔módulo com config de geometria (ADR-0032).

    config JSONB: {roi: [[x,y],...], line: [[x,y],[x,y]], classes: [],
                   thresholds: {"helmet": 0.6, ...}} — geometrias normalizadas 0..1.
    Histórico completo de deployments permite rollback (reativar anterior).
    """

    id: UUID
    tenant_id: UUID
    model_id: UUID
    camera_id: UUID
    created_at: datetime
    module_code: str = "epi"
    status: DeploymentStatus = DeploymentStatus.ACTIVE
    config: Optional[dict[str, Any]] = None
    deployed_by: Optional[UUID] = None
    deactivated_at: Optional[datetime] = None
