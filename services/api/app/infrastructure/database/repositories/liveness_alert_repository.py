"""
Repository: Liveness alerts (camera_gap violation type).

Layer: infrastructure
Pattern: Repository (extends BaseRepository)

Handles SQL for camera-gap liveness monitoring. Kept separate from
AlertRepository to avoid coupling it to the camera_id-required interface.
All queries are tenant-scoped (C-01 multi-tenant constraint).

Related: app/domain/services/liveness_service.py
"""
import json
import logging
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class LivenessAlertRepository(BaseRepository):
    """SQL queries for camera-gap liveness alerts on the alerts table."""

    def get_open_gap_alert(
        self, tenant_id: str, evidence_key: str
    ) -> dict[str, Any] | None:
        """
        Return the oldest unacknowledged camera_gap alert for this site, or None.

        Uses LIKE on violations::text to find the 'camera_gap' type entry
        without needing a dedicated column.
        """
        return self._execute_one(
            "SELECT * FROM alerts "
            "WHERE tenant_id = %s AND evidence_key = %s "
            "AND acknowledged = FALSE "
            "AND violations::text LIKE %s "
            "ORDER BY created_at ASC LIMIT 1",
            (tenant_id, evidence_key, "%camera_gap%"),
        )

    def find_camera_for_tenant(self, tenant_id: str) -> str | None:
        """
        Return the ID of any active camera for the tenant, or None.

        This is needed to satisfy the NOT NULL camera_id FK on the alerts table.
        Returns None when no cameras are configured for the tenant.
        """
        row = self._execute_one(
            "SELECT id FROM cameras WHERE tenant_id = %s AND is_active = TRUE LIMIT 1",
            (tenant_id,),
        )
        return str(row["id"]) if row else None

    def create_gap_alert(
        self,
        camera_id: str,
        tenant_id: str,
        evidence_key: str,
        cameras_online: int,
        cameras_total: int,
    ) -> dict[str, Any] | None:
        """
        Insert a camera_gap alert row into the alerts table.

        The camera_id is used to satisfy the FK constraint (any active camera
        from the tenant). The violations JSON encodes the true liveness data.
        """
        violations = json.dumps(
            [
                {
                    "type": "camera_gap",
                    "cameras_online": cameras_online,
                    "cameras_total": cameras_total,
                }
            ]
        )
        return self._execute_mutation(
            "INSERT INTO alerts "
            "  (camera_id, violations, confidence, evidence_key, tenant_id, acknowledged) "
            "VALUES (%s, %s::jsonb, %s, %s, %s, FALSE) "
            "RETURNING *",
            (camera_id, violations, 1.0, evidence_key, tenant_id),
        )

    def acknowledge_gap_alerts(
        self, tenant_id: str, evidence_key: str
    ) -> int:
        """
        Acknowledge all open camera_gap alerts for this site.

        Returns the number of rows updated. Scoped by tenant_id to prevent
        cross-tenant acknowledgement.
        """
        return self._execute_mutation_no_return(
            "UPDATE alerts SET acknowledged = TRUE "
            "WHERE tenant_id = %s AND evidence_key = %s "
            "AND acknowledged = FALSE "
            "AND violations::text LIKE %s",
            (tenant_id, evidence_key, "%camera_gap%"),
        )
