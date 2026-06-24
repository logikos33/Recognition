"""Repository: Counting Sessions + Events (DeepSORT anti-duplicate counting).

Inclui os campos de carga/descarga da migration 050 (CD-03/CD-06/CD-07):
bay_id, truck_plate, direction, expected_count, divergence, video_clip_url,
manual_count, acceptance_status.
"""
import json
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository

# Colunas que podem ser alteradas via update parcial (PATCH).
# Whitelist fixa — nomes de coluna NUNCA vêm de input do usuário.
UPDATABLE_SESSION_FIELDS = (
    "bay_id",
    "truck_plate",
    "direction",
    "expected_count",
    "divergence",
    "video_clip_url",
    "manual_count",
    "acceptance_status",
)

# Subquery reutilizada: contagem real (eventos DeepSORT) por sessão.
_EVENT_COUNTS_SUBQUERY = (
    "(SELECT session_id, COUNT(*) AS system_count "
    "FROM counting_events GROUP BY session_id) ev"
)


class CountingRepository(BaseRepository):
    """Queries SQL para counting_sessions e counting_events."""

    # --- Sessions ---

    def create_session(
        self,
        tenant_id: UUID,
        camera_id: UUID,
        module_code: str,
        bay_id: Optional[UUID] = None,
        truck_plate: Optional[str] = None,
        direction: Optional[str] = None,
        expected_count: Optional[int] = None,
    ) -> dict[str, Any]:
        return self._execute_mutation(
            "INSERT INTO counting_sessions "
            "(tenant_id, camera_id, module_code, bay_id, truck_plate, "
            "direction, expected_count) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
            (
                str(tenant_id),
                str(camera_id),
                module_code,
                str(bay_id) if bay_id else None,
                truck_plate,
                direction,
                expected_count,
            ),
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
        """Update parcial de campos da sessão (PATCH).

        Apenas colunas em UPDATABLE_SESSION_FIELDS são aceitas — campos
        fora da whitelist são ignorados silenciosamente. O SET é montado
        somente com nomes da whitelist fixa; valores sempre via %s.
        """
        valid = {k: v for k, v in fields.items() if k in UPDATABLE_SESSION_FIELDS}
        if not valid:
            return None
        set_clause = ", ".join(f"{col} = %s" for col in valid)
        params: list[Any] = list(valid.values())
        params.extend([str(session_id), str(tenant_id)])
        return self._execute_mutation(
            f"UPDATE counting_sessions SET {set_clause} "  # noqa: S608 — colunas da whitelist fixa
            "WHERE id = %s AND tenant_id = %s RETURNING *",
            tuple(params),
        )

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
