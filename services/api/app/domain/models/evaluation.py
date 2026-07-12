"""Domain models: ModelEvaluation e ModelDriftMetric (migration 101)."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.constants import EvalVerdict


@dataclass(frozen=True)
class ModelEvaluation:
    """Avaliação campeão×desafiante antes de ativar um modelo (ADR-0031).

    verdict: 'promote' se mAP_challenger >= mAP_champion - 0.01 e nenhuma
    classe crítica cai >5pp; 'reject' caso contrário; sem campeão → promote.
    """

    id: UUID
    tenant_id: UUID
    created_at: datetime
    verdict: EvalVerdict = EvalVerdict.PENDING
    model_id: Optional[UUID] = None
    champion_model_id: Optional[UUID] = None
    dataset_version_id: Optional[UUID] = None
    metrics: Optional[dict[str, Any]] = None
    confusion_matrix: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class ModelDriftMetric:
    """Métricas de drift por janela temporal (beat diário compute_drift_metrics).

    drift_score = |avg_conf - baseline| + L1(class_distribution).
    """

    id: UUID
    tenant_id: UUID
    created_at: datetime
    detections_count: int = 0
    model_id: Optional[UUID] = None
    camera_id: Optional[UUID] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    avg_confidence: Optional[float] = None
    class_distribution: Optional[dict[str, Any]] = None
    drift_score: Optional[float] = None
