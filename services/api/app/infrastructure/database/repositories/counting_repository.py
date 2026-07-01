"""Repository: Counting Sessions + Events (DeepSORT anti-duplicate counting)."""
import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository

# Colunas permitidas em update parcial (whitelist fixa — CD-03/CD-06/CD-07)
UPDATABLE_SESSION_FIELDS: frozenset[str] = frozenset({
    "bay_id",
    "truck_plate",
    "direction",
    "expected_count",
    "divergence",
    "video_clip_url",
    "manual_count",
    "acceptance_status",
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
        self,
        session_id: UUID,
        tenant_id: UUID,
        fields: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """Atualiza campos da whitelist (UPDATABLE_SESSION_FIELDS) numa sessão.

        Campos fora da whitelist são silenciosamente ignorados.
        Retorna None sem executar query se nenhum campo válido for fornecido.
        """
        safe = {k: v for k, v in fields.items() if k in UPDATABLE_SESSION_FIELDS}
        if not safe:
            return None
        set_clause = ", ".join(f"{col} = %s" for col in safe)
        params: list[Any] = list(safe.values()) + [str(session_id), str(tenant_id)]
        return self._execute_mutation(
            f"UPDATE counting_sessions SET {set_clause} "
            f"WHERE id = %s AND tenant_id = %s RETURNING *",
            params,
        )

    def get_session_total(self, session_id: UUID) -> int:
        """Retorna total de eventos (contagens) de uma sessão."""
        row = self._execute_one(
            "SELECT COUNT(*) AS total FROM counting_events WHERE session_id = %s",
            (str(session_id),),
        )
        return int(row["total"]) if row else 0

    # --- Validation / Acceptance report (CD-07) ---

    def get_validation_sessions(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        bay_id: Optional[UUID] = None,
    ) -> list[dict[str, Any]]:
        """Lista sessões com manual_count para relatório de aceite."""
        base = (
            "SELECT cs.id, cs.started_at, cs.ended_at, cs.bay_id, "
            "  cs.truck_plate, cs.direction, cs.expected_count, "
            "  cs.manual_count, cs.acceptance_status, "
            "  (SELECT COALESCE(SUM(1), 0) FROM counting_events ce "
            "   WHERE ce.session_id = cs.id) AS system_count, "
            "  ABS(cs.manual_count - "
            "    (SELECT COALESCE(SUM(1), 0) FROM counting_events ce2 "
            "     WHERE ce2.session_id = cs.id)) AS abs_error, "
            "  CASE WHEN cs.manual_count > 0 THEN "
            "    ROUND(ABS(cs.manual_count - "
            "      (SELECT COALESCE(SUM(1), 0) FROM counting_events ce3 "
            "       WHERE ce3.session_id = cs.id))::numeric / cs.manual_count * 100, 2) "
            "  ELSE NULL END AS error_pct "
            "FROM counting_sessions cs "
            "WHERE cs.tenant_id = %s "
            "  AND cs.started_at >= %s AND cs.started_at < %s "
            "  AND cs.manual_count IS NOT NULL"
        )
        params: list[Any] = [str(tenant_id), start, end]
        if bay_id is not None:
            base += " AND cs.bay_id = %s"
            params.append(str(bay_id))
        base += " ORDER BY cs.started_at"
        return self._execute(base, params)

    def get_validation_daily(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        bay_id: Optional[UUID] = None,
    ) -> list[dict[str, Any]]:
        """Agrega erros por dia para relatório de aceite."""
        base = (
            "SELECT DATE(cs.started_at) AS day, COUNT(*) AS sessions, "
            "  SUM((SELECT COALESCE(SUM(1), 0) FROM counting_events ce "
            "       WHERE ce.session_id = cs.id)) AS system_total, "
            "  SUM(cs.manual_count) AS manual_total, "
            "  SUM(ABS(cs.manual_count - "
            "    (SELECT COALESCE(SUM(1), 0) FROM counting_events ce2 "
            "     WHERE ce2.session_id = cs.id))) AS abs_error, "
            "  CASE WHEN SUM(cs.manual_count) > 0 THEN "
            "    ROUND(SUM(ABS(cs.manual_count - "
            "      (SELECT COALESCE(SUM(1), 0) FROM counting_events ce3 "
            "       WHERE ce3.session_id = cs.id)))::numeric / SUM(cs.manual_count) * 100, 2) "
            "  ELSE NULL END AS error_pct "
            "FROM counting_sessions cs "
            "WHERE cs.tenant_id = %s "
            "  AND cs.started_at >= %s AND cs.started_at < %s "
            "  AND cs.manual_count IS NOT NULL"
        )
        params: list[Any] = [str(tenant_id), start, end]
        if bay_id is not None:
            base += " AND cs.bay_id = %s"
            params.append(str(bay_id))
        base += " GROUP BY DATE(cs.started_at) ORDER BY day"
        return self._execute(base, params)

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
