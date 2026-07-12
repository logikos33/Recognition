"""Repository: Counting Sessions + Events (DeepSORT anti-duplicate counting)."""
import json
from datetime import datetime
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

    # --- Validation / Acceptance (CD-07) ---

    def get_validation_sessions(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        bay_id: Optional[UUID] = None,
    ) -> list[dict[str, Any]]:
        """
        Sessões com conferência manual (manual_count preenchido) no período.

        system_count é derivado de total_counts (soma de todas as classes
        detectadas); abs_error/error_pct comparam contra manual_count.
        """
        bay_filter = "AND cs.bay_id = %s " if bay_id else ""
        query = (
            "WITH base AS ("
            "  SELECT cs.id, cs.bay_id, cs.camera_id, cs.truck_plate, cs.direction, "
            "         cs.started_at, cs.ended_at, cs.acceptance_status, cs.video_clip_url, "
            "         cs.manual_count, "
            "         COALESCE((SELECT SUM(value::int) FROM jsonb_each_text(cs.total_counts)), 0) AS system_count "
            "  FROM counting_sessions cs "
            "  WHERE cs.tenant_id = %s AND cs.manual_count IS NOT NULL "
            "    AND cs.started_at >= %s AND cs.started_at <= %s "
            f"   {bay_filter}"
            ") "
            "SELECT *, "
            "       ABS(system_count - manual_count) AS abs_error, "
            "       CASE WHEN manual_count = 0 THEN NULL "
            "            ELSE ROUND(ABS(system_count - manual_count)::numeric / manual_count * 100, 4) "
            "       END AS error_pct "
            "FROM base ORDER BY started_at DESC"
        )
        params: list[Any] = [str(tenant_id), start, end]
        if bay_id:
            params.append(str(bay_id))
        return self._execute(query, params)

    def get_validation_daily(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        bay_id: Optional[UUID] = None,
    ) -> list[dict[str, Any]]:
        """Agregado diário (system vs manual) das sessões com conferência manual."""
        bay_filter = "AND cs.bay_id = %s " if bay_id else ""
        query = (
            "WITH base AS ("
            "  SELECT cs.started_at, cs.manual_count, "
            "         COALESCE((SELECT SUM(value::int) FROM jsonb_each_text(cs.total_counts)), 0) AS system_count "
            "  FROM counting_sessions cs "
            "  WHERE cs.tenant_id = %s AND cs.manual_count IS NOT NULL "
            "    AND cs.started_at >= %s AND cs.started_at <= %s "
            f"   {bay_filter}"
            ") "
            "SELECT DATE(started_at) AS day, "
            "       COUNT(*) AS sessions, "
            "       SUM(system_count) AS system_total, "
            "       SUM(manual_count) AS manual_total, "
            "       SUM(ABS(system_count - manual_count)) AS abs_error, "
            "       CASE WHEN SUM(manual_count) = 0 THEN NULL "
            "            ELSE ROUND(SUM(ABS(system_count - manual_count))::numeric / SUM(manual_count) * 100, 4) "
            "       END AS error_pct "
            "FROM base GROUP BY DATE(started_at) ORDER BY day"
        )
        params: list[Any] = [str(tenant_id), start, end]
        if bay_id:
            params.append(str(bay_id))
        return self._execute(query, params)
