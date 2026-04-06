"""
EPI Monitor V2 — Inference Service.

Coordena inferência YOLO e alertas. NÃO conhece Flask.
"""
import logging
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.infrastructure.database.repositories.alert_repository import AlertRepository

logger = logging.getLogger(__name__)


class InferenceService:
    """Use cases de inferência e alertas."""

    def __init__(self, alert_repo: AlertRepository) -> None:
        self._alert_repo = alert_repo

    def get_alerts(
        self,
        camera_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Lista alertas de uma câmera."""
        alerts = self._alert_repo.get_by_camera(camera_id, limit, offset)
        for a in alerts:
            a["id"] = str(a["id"])
        return alerts

    def get_unacknowledged(
        self,
        camera_id: UUID | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Lista alertas não reconhecidos."""
        alerts = self._alert_repo.get_unacknowledged(camera_id, limit)
        for a in alerts:
            a["id"] = str(a["id"])
        return alerts

    def acknowledge_alert(self, alert_id: UUID) -> dict:
        """Marca alerta como reconhecido."""
        result = self._alert_repo.acknowledge(alert_id)
        if not result:
            raise NotFoundError("Alerta", str(alert_id))
        result["id"] = str(result["id"])
        return result

    def get_alert_count(self, camera_id: UUID) -> int:
        """Conta alertas de uma câmera."""
        return self._alert_repo.count_by_camera(camera_id)
