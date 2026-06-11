"""Repository: Counting Sessions + Events (DeepSORT anti-duplicate counting).

Inclui os campos de carga/descarga da migration 050 (CD-03/CD-06/CD-07):
bay_id, truck_plate, direction, expected_count, divergence, video_clip_url,
manual_count, acceptance_status.
"""
import json
from datetime import datetime
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

    def get_session(self, session_id: UUID) -> Optional[dict[str, Any]]:
        return self._execute_one(
            "SELECT * FROM counting_sessions WHERE id = %s",
            (str(session_id),),
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
        total_counts: dict[str, int],
    ) -> Optional[dict[str, Any]]:
        return self._execute_mutation(
            "UPDATE counting_sessions "
            "SET status = 'stopped', ended_at = NOW(), total_counts = %s "
            "WHERE id = %s RETURNING *",
            (json.dumps(total_counts), str(session_id)),
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

    def get_session_total(self, session_id: UUID) -> int:
        """Total de objetos contados (eventos DeepSORT) numa sessão."""
        row = self._execute_one(
            "SELECT COUNT(*) AS total FROM counting_events WHERE session_id = %s",
            (str(session_id),),
        )
        return int(row["total"]) if row else 0

    # --- CD-07: relatório de validação/aceite (system vs manual) ---

    def get_validation_sessions(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        bay_id: Optional[UUID] = None,
    ) -> list[dict[str, Any]]:
        """Sessões com manual_count preenchido + erro absoluto/percentual.

        system_count = eventos DeepSORT da sessão (fonte da verdade).
        error_pct é NULL quando manual_count = 0 (caller decide pass/fail
        via abs_error nesse caso).
        """
        query = (
            "SELECT cs.id, cs.bay_id, cs.camera_id, cs.truck_plate, cs.direction, "
            "cs.started_at, cs.ended_at, cs.acceptance_status, cs.video_clip_url, "
            "cs.manual_count, COALESCE(ev.system_count, 0) AS system_count, "
            "ABS(COALESCE(ev.system_count, 0) - cs.manual_count) AS abs_error, "
            "CASE WHEN cs.manual_count > 0 THEN "
            "ROUND(ABS(COALESCE(ev.system_count, 0) - cs.manual_count)::numeric "
            "/ cs.manual_count * 100, 2) ELSE NULL END AS error_pct "
            "FROM counting_sessions cs "
            f"LEFT JOIN {_EVENT_COUNTS_SUBQUERY} ON ev.session_id = cs.id "
            "WHERE cs.tenant_id = %s AND cs.manual_count IS NOT NULL "
            "AND cs.started_at >= %s AND cs.started_at < %s"
        )
        params: list[Any] = [str(tenant_id), start, end]
        if bay_id is not None:
            query += " AND cs.bay_id = %s"
            params.append(str(bay_id))
        query += " ORDER BY cs.started_at"
        return self._execute(query, tuple(params))

    def get_validation_daily(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        bay_id: Optional[UUID] = None,
    ) -> list[dict[str, Any]]:
        """Agregado por dia: total system vs total manual + erro percentual."""
        query = (
            "SELECT cs.started_at::date AS day, "
            "COUNT(*) AS sessions, "
            "COALESCE(SUM(COALESCE(ev.system_count, 0)), 0) AS system_total, "
            "COALESCE(SUM(cs.manual_count), 0) AS manual_total, "
            "ABS(COALESCE(SUM(COALESCE(ev.system_count, 0)), 0) "
            "- COALESCE(SUM(cs.manual_count), 0)) AS abs_error, "
            "ROUND(ABS(COALESCE(SUM(COALESCE(ev.system_count, 0)), 0) "
            "- COALESCE(SUM(cs.manual_count), 0))::numeric "
            "/ NULLIF(SUM(cs.manual_count), 0) * 100, 2) AS error_pct "
            "FROM counting_sessions cs "
            f"LEFT JOIN {_EVENT_COUNTS_SUBQUERY} ON ev.session_id = cs.id "
            "WHERE cs.tenant_id = %s AND cs.manual_count IS NOT NULL "
            "AND cs.started_at >= %s AND cs.started_at < %s"
        )
        params: list[Any] = [str(tenant_id), start, end]
        if bay_id is not None:
            query += " AND cs.bay_id = %s"
            params.append(str(bay_id))
        query += " GROUP BY cs.started_at::date ORDER BY day"
        return self._execute(query, tuple(params))

    # --- Dashboard real (flag fueling_use_mock desligada) ---

    def get_loading_rollup(
        self,
        tenant_id: UUID,
        module_code: str,
        start: datetime,
    ) -> Optional[dict[str, Any]]:
        """KPIs agregados de sessões de carga/descarga desde `start`."""
        return self._execute_one(
            "SELECT COUNT(*) AS total_sessoes, "
            "COALESCE(SUM(COALESCE(ev.system_count, 0)), 0) AS total_itens, "
            "AVG(EXTRACT(EPOCH FROM (cs.ended_at - cs.started_at)) / 60.0) "
            "FILTER (WHERE cs.ended_at IS NOT NULL) AS tempo_medio_minutos, "
            "COUNT(*) FILTER (WHERE cs.divergence IS NOT NULL "
            "AND cs.divergence <> 0) AS sessoes_divergentes "
            "FROM counting_sessions cs "
            f"LEFT JOIN {_EVENT_COUNTS_SUBQUERY} ON ev.session_id = cs.id "
            "WHERE cs.tenant_id = %s AND cs.module_code = %s "
            "AND cs.started_at >= %s",
            (str(tenant_id), module_code, start),
        )

    def get_loading_daily_series(
        self,
        tenant_id: UUID,
        module_code: str,
        start: datetime,
    ) -> list[dict[str, Any]]:
        """Série diária de operações (sessões iniciadas por dia)."""
        return self._execute(
            "SELECT started_at::date AS dia, COUNT(*) AS operacoes "
            "FROM counting_sessions "
            "WHERE tenant_id = %s AND module_code = %s AND started_at >= %s "
            "GROUP BY started_at::date ORDER BY dia",
            (str(tenant_id), module_code, start),
        )

    def list_active_loading_bays(
        self,
        tenant_id: UUID,
        module_code: str,
    ) -> list[dict[str, Any]]:
        """Sessões em andamento com totais parciais (visão de baias real)."""
        return self._execute(
            "SELECT cs.id AS session_id, cs.bay_id, cs.truck_plate, "
            "cs.direction, cs.started_at, "
            "COALESCE(ev.system_count, 0) AS total_itens "
            "FROM counting_sessions cs "
            f"LEFT JOIN {_EVENT_COUNTS_SUBQUERY} ON ev.session_id = cs.id "
            "WHERE cs.tenant_id = %s AND cs.module_code = %s "
            "AND cs.status = 'running' "
            "ORDER BY cs.started_at DESC",
            (str(tenant_id), module_code),
        )
