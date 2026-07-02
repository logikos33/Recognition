"""Repository: Counting Sessions + Events (DeepSORT anti-duplicate counting)."""
import json
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository

UPDATABLE_SESSION_FIELDS: frozenset[str] = frozenset({
    "bay_id", "truck_plate", "direction", "expected_count",
    "divergence", "video_clip_url", "manual_count", "acceptance_status",
})


class CountingRepository(BaseRepository):
    """Queries SQL para counting_sessions e counting_events."""

    # --- Sessions ---

    def create_session(
        self,
        tenant_id: UUID,
        camera_id: UUID,
        module_code: str,
    ) -> dict[str, Any]:
        return self._execute_mutation(
            "INSERT INTO counting_sessions (tenant_id, camera_id, module_code) "
            "VALUES (%s, %s, %s) RETURNING *",
            (str(tenant_id), str(camera_id), module_code),
        )  # type: ignore[return-value]

    def get_session(self, session_id: UUID, tenant_id: UUID) -> Optional[dict[str, Any]]:
        """Busca sessão por ID verificando isolamento por tenant (P0-05 fix)."""
        return self._execute_one(
            "SELECT * FROM counting_sessions WHERE id = %s AND tenant_id = %s",
            (str(session_id), str(tenant_id)),
        )

    def list_active_sessions(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return self._execute(
            "SELECT cs.*, c.name AS camera_name "
            "FROM counting_sessions cs "
            "LEFT JOIN cameras c ON c.id = cs.camera_id "
            "WHERE cs.tenant_id = %s AND cs.status = 'running' "
            "ORDER BY cs.started_at DESC",
            (str(tenant_id),),
        )

    def stop_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
        total_counts: dict[str, int],
    ) -> Optional[dict[str, Any]]:
        """Encerra sessão verificando isolamento por tenant (P0-05 fix)."""
        return self._execute_mutation(
            "UPDATE counting_sessions "
            "SET status = 'stopped', ended_at = NOW(), total_counts = %s "
            "WHERE id = %s AND tenant_id = %s RETURNING *",
            (json.dumps(total_counts), str(session_id), str(tenant_id)),
        )

    def update_session_fields(
        self, session_id: UUID, tenant_id: UUID, fields: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Partial UPDATE scoped to UPDATABLE_SESSION_FIELDS whitelist."""
        valid = {k: v for k, v in fields.items() if k in UPDATABLE_SESSION_FIELDS}
        if not valid:
            return None
        set_clause = ", ".join(f"{k} = %s" for k in valid)
        params = list(valid.values()) + [str(session_id), str(tenant_id)]
        return self._execute_mutation(
            f"UPDATE counting_sessions SET {set_clause} "
            "WHERE id = %s AND tenant_id = %s RETURNING *",
            params,
        )

    def get_session_total(self, session_id: UUID) -> int:
        """Returns total distinct events counted in session (for divergence calc)."""
        row = self._execute_one(
            "SELECT COUNT(*) AS cnt FROM counting_events WHERE session_id = %s",
            (str(session_id),),
        )
        return int(row["cnt"]) if row else 0

    # --- Events (idempotent upsert by track_id) ---

    def upsert_event(
        self,
        session_id: UUID,
        track_id: int,
        class_name: str,
        confidence: float,
    ) -> Optional[dict[str, Any]]:
        """INSERT or UPDATE detection event. UNIQUE(session_id, track_id)."""
        return self._execute_mutation(
            "INSERT INTO counting_events (session_id, track_id, class_name, confidence) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (session_id, track_id) DO UPDATE "
            "SET last_seen_at = NOW(), confidence = EXCLUDED.confidence "
            "RETURNING *",
            (str(session_id), track_id, class_name, confidence),
        )

    def get_session_counts(self, session_id: UUID) -> list[dict[str, Any]]:
        """Aggregated counts per class for a session."""
        return self._execute(
            "SELECT class_name, COUNT(*) AS count "
            "FROM counting_events WHERE session_id = %s "
            "GROUP BY class_name ORDER BY count DESC",
            (str(session_id),),
        )

    # --- LPR / Plate ---

    def update_plate(
        self,
        session_id: UUID,
        tenant_id: UUID,
        plate_text: str | None,
        plate_confidence: float | None = None,
        plate_review: bool = False,
        plate_manual: bool = False,
    ) -> Optional[dict[str, Any]]:
        """
        Persiste resultado de LPR (OCR automático ou correção manual) na sessão.
        Filtra por tenant_id para garantir isolamento.
        """
        return self._execute_mutation(
            "UPDATE counting_sessions "
            "SET plate_text = %s, plate_confidence = %s, "
            "    plate_review = %s, plate_manual = %s "
            "WHERE id = %s AND tenant_id = %s "
            "RETURNING *",
            (
                plate_text,
                plate_confidence,
                plate_review,
                plate_manual,
                str(session_id),
                str(tenant_id),
            ),
        )

    def list_sessions_with_plate(
        self,
        tenant_id: UUID,
        *,
        only_review: bool = False,
    ) -> list[dict[str, Any]]:
        """Lista sessões com placa associada; filtra por plate_review se solicitado."""
        base = (
            "SELECT cs.*, c.name AS camera_name "
            "FROM counting_sessions cs "
            "LEFT JOIN cameras c ON c.id = cs.camera_id "
            "WHERE cs.tenant_id = %s AND cs.plate_text IS NOT NULL"
        )
        if only_review:
            base += " AND cs.plate_review = TRUE"
        base += " ORDER BY cs.started_at DESC LIMIT 200"
        return self._execute(base, (str(tenant_id),))
