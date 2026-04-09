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

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        camera_id: str = None,
        start_date=None,
        end_date=None,
        violation_type: str = None,
        acknowledged: bool = None,
    ) -> dict:
        """Lista alertas com filtros e paginação."""
        conditions = ["1=1"]
        params: list = []

        if camera_id:
            conditions.append("a.camera_id = %s")
            params.append(camera_id)
        if start_date:
            conditions.append("a.created_at >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("a.created_at <= %s")
            params.append(end_date)
        if violation_type:
            conditions.append("a.violations::text LIKE %s")
            params.append(f'%{violation_type}%')
        if acknowledged is not None:
            conditions.append("a.acknowledged = %s")
            params.append(acknowledged)

        where = " AND ".join(conditions)

        # Count
        count_params = list(params)
        total_row = self._execute_one(
            f"SELECT COUNT(*) as count FROM alerts a WHERE {where}",
            tuple(count_params),
        )
        total = total_row["count"] if total_row else 0

        # Items with camera name join (best-effort — camera table may vary)
        page_params = list(params) + [limit, offset]
        items = self._execute(
            f"""SELECT a.*,
               COALESCE(i.name, 'Unknown') as camera_name
            FROM alerts a
            LEFT JOIN ip_cameras i ON a.camera_id = i.id
            WHERE {where}
            ORDER BY a.created_at DESC
            LIMIT %s OFFSET %s""",
            tuple(page_params),
        )

        return {"items": items, "total": total}
