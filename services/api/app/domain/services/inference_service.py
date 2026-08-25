"""
DOMAIN inference_service.py — Alert management use cases for YOLO inference results.

Layer: domain
Pattern: Service (framework-agnostic)

Key exports:
  - InferenceService.get_alerts(camera_id, limit, offset): paginated alert list for a camera
  - InferenceService.get_unacknowledged(camera_id, limit): unacknowledged alerts, optionally filtered by camera
  - InferenceService.acknowledge_alert(alert_id): marks alert as acknowledged, raises NotFoundError if missing
  - InferenceService.get_alert_count(camera_id): total alert count for a camera

Constraints:
  - Alert creation is handled by the worker service via Redis pub/sub, not by this service
  - All returned dicts have id converted to str (UUID serialization)
  - Default limit is 50 for all list methods

Related: app/infrastructure/database/repositories/alert_repository.py,
         services/shared/events.py (worker publishes alerts via Redis)
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
        tenant_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Lista alertas de uma câmera, dentro do tenant de quem pediu (C-01)."""
        alerts = self._alert_repo.get_by_camera(camera_id, tenant_id, limit, offset)
        for a in alerts:
            a["id"] = str(a["id"])
        return alerts

    def get_unacknowledged(
        self,
        tenant_id: str,
        camera_id: UUID | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Lista alertas não reconhecidos do tenant.

        O repositório sempre teve `tenant_id` na cláusula, mas este método o
        omitia na chamada: passava só `(camera_id, limit)`, deixando
        `tenant_id=None` virar a string "None" contra uma coluna uuid. Este
        caminho nunca devolveu nada de útil — não apareceu porque nada o chama.
        """
        alerts = self._alert_repo.get_unacknowledged(camera_id, limit, tenant_id)
        for a in alerts:
            a["id"] = str(a["id"])
        return alerts

    def acknowledge_alert(self, alert_id: UUID, tenant_id: str) -> dict:
        """Marca alerta como reconhecido, dentro do tenant de quem pediu."""
        result = self._alert_repo.acknowledge(alert_id, tenant_id)
        if not result:
            raise NotFoundError("Alerta", str(alert_id))
        result["id"] = str(result["id"])
        return result

    def get_alert_count(self, camera_id: UUID) -> int:
        """Conta alertas de uma câmera."""
        return self._alert_repo.count_by_camera(camera_id)
