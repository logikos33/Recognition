"""Repository: Alerts."""
import json
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class AlertRepository(BaseRepository):
    """Queries SQL para tabela alerts."""

    def create(
        self,
        camera_id: UUID,
        violations: list[dict[str, Any]],
        confidence: float,
        evidence_key: str,
    ) -> dict[str, Any]:
        """Cria alerta de violação."""
        return self._execute_mutation(
            "INSERT INTO alerts (camera_id, violations, confidence, evidence_key) "
            "VALUES (%s, %s::jsonb, %s, %s) RETURNING *",
            (str(camera_id), json.dumps(violations), confidence, evidence_key),
        )  # type: ignore[return-value]

    def get_by_camera(
        self,
        camera_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Lista alertas de uma câmera com paginação."""
        return self._execute(
            "SELECT * FROM alerts WHERE camera_id = %s "
            "ORDER BY timestamp DESC LIMIT %s OFFSET %s",
            (str(camera_id), limit, offset),
        )

    def get_unacknowledged(
        self, camera_id: Optional[UUID] = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Lista alertas não reconhecidos."""
        if camera_id:
            return self._execute(
                "SELECT * FROM alerts "
                "WHERE camera_id = %s AND acknowledged = FALSE "
                "ORDER BY timestamp DESC LIMIT %s",
                (str(camera_id), limit),
            )
        return self._execute(
            "SELECT * FROM alerts WHERE acknowledged = FALSE "
            "ORDER BY timestamp DESC LIMIT %s",
            (limit,),
        )

    def acknowledge(self, alert_id: UUID) -> Optional[dict[str, Any]]:
        """Marca alerta como reconhecido."""
        return self._execute_mutation(
            "UPDATE alerts SET acknowledged = TRUE "
            "WHERE id = %s RETURNING *",
            (str(alert_id),),
        )

    def count_by_camera(self, camera_id: UUID) -> int:
        """Conta alertas de uma câmera."""
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM alerts WHERE camera_id = %s",
            (str(camera_id),),
        )
        return row["count"] if row else 0
