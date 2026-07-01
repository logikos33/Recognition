"""
DOMAIN counting_service.py — Sessões de contagem com anti-duplicata via track_id.

Fluxo:
  1. start_session(camera_id, module_code) → cria sessão, retorna session_id
  2. record_detection(session_id, track_id, class_name, confidence)
     → upsert idempotente por track_id (DeepSORT garante unicidade)
  3. stop_session(session_id) → finaliza, retorna totais agregados

O track_id vem do DeepSORT no inference-service. Cada objeto físico recebe
um track_id único por sessão — sem duplicatas mesmo com múltiplas detecções.
"""
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.models.counting_session import (
    VALID_ACCEPTANCE_STATUSES,
    VALID_DIRECTIONS,
)
from app.infrastructure.database.repositories.counting_repository import (
    UPDATABLE_SESSION_FIELDS,
    CountingRepository,
)

logger = logging.getLogger(__name__)


class CountingService:

    def __init__(self, repo: CountingRepository) -> None:
        self._repo = repo

    def start_session(
        self,
        tenant_id: UUID,
        camera_id: UUID,
        module_code: str,
    ) -> dict:
        """Cria nova sessão de contagem. Retorna session dict."""
        if not module_code:
            raise ValidationError("module_code é obrigatório")
        session = self._repo.create_session(tenant_id, camera_id, module_code)
        logger.info(
            "counting_session_started: id=%s camera=%s module=%s",
            session["id"], camera_id, module_code,
        )
        return session

    def stop_session(self, session_id: UUID, tenant_id: UUID) -> dict:
        """Encerra sessão e retorna totais agregados por classe."""
        session = self._repo.get_session(session_id, tenant_id)
        if not session:
            raise NotFoundError(f"Sessão {session_id} não encontrada")

        # Aggregate counts from events
        rows = self._repo.get_session_counts(session_id)
        total_counts = {r["class_name"]: r["count"] for r in rows}

        updated = self._repo.stop_session(session_id, tenant_id, total_counts)
        logger.info(
            "counting_session_stopped: id=%s counts=%s",
            session_id, total_counts,
        )
        return updated or session  # type: ignore[return-value]

    def record_detection(
        self,
        session_id: UUID,
        track_id: int,
        class_name: str,
        confidence: float,
    ) -> None:
        """Registra (ou atualiza) uma detecção rastreada. Idempotente por track_id."""
        try:
            self._repo.upsert_event(session_id, track_id, class_name, confidence)
        except Exception as exc:
            logger.warning("counting_record_error: session=%s track=%s err=%s", session_id, track_id, exc)

    def get_live_stats(self, session_id: UUID, tenant_id: UUID) -> dict:
        """Retorna contagens ao vivo por classe."""
        session = self._repo.get_session(session_id, tenant_id)
        if not session:
            raise NotFoundError(f"Sessão {session_id} não encontrada")

        rows = self._repo.get_session_counts(session_id)
        counts = {r["class_name"]: r["count"] for r in rows}
        return {
            "session_id": str(session_id),
            "status": session["status"],
            "started_at": session["started_at"].isoformat() if session.get("started_at") else None,
            "counts": counts,
            "total": sum(counts.values()),
        }

    def list_active(self, tenant_id: UUID) -> list[dict]:
        return self._repo.list_active_sessions(tenant_id)

    def update_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """Atualiza campos de carga/descarga numa sessão (PATCH parcial).

        Apenas campos em UPDATABLE_SESSION_FIELDS são aceitos.
        Levanta ValidationError para campos fora da whitelist ou valores inválidos.
        Levanta NotFoundError se a sessão não existir ou pertencer a outro tenant.
        """
        # 1. Rejeita qualquer campo fora da whitelist
        unknown = set(fields) - UPDATABLE_SESSION_FIELDS
        if unknown:
            raise ValidationError(
                f"Campo não atualizável: {sorted(unknown)}. "
                f"Permitidos: {sorted(UPDATABLE_SESSION_FIELDS)}"
            )

        # 2. Valida valores semânticos
        if "acceptance_status" in fields:
            if fields["acceptance_status"] not in VALID_ACCEPTANCE_STATUSES:
                raise ValidationError(
                    f"acceptance_status inválido: {fields['acceptance_status']!r}. "
                    f"Valores válidos: {VALID_ACCEPTANCE_STATUSES}"
                )
        if "direction" in fields:
            if fields["direction"] not in VALID_DIRECTIONS:
                raise ValidationError(
                    f"direction inválido: {fields['direction']!r}. "
                    f"Valores válidos: {VALID_DIRECTIONS}"
                )
        if "manual_count" in fields:
            if fields["manual_count"] < 0:
                raise ValidationError("manual_count não pode ser negativo")

        # 3. Verifica existência + isolamento de tenant
        session = self._repo.get_session(session_id, tenant_id)
        if not session:
            raise NotFoundError(f"Sessão {session_id} não encontrada")
        if str(session.get("tenant_id")) != str(tenant_id):
            raise NotFoundError(f"Sessão {session_id} não encontrada")

        # 4. Auto-computa divergência quando expected_count for fornecido
        #    (apenas se divergence não foi explicitamente informado)
        update_fields = dict(fields)
        if "expected_count" in update_fields and "divergence" not in update_fields:
            system_count = self._repo.get_session_total(session_id)
            update_fields["divergence"] = system_count - update_fields["expected_count"]

        # 5. Persiste
        updated = self._repo.update_session_fields(session_id, tenant_id, update_fields)
        return updated or session  # type: ignore[return-value]

    def get_validation_report(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        *,
        bay_id: Optional[UUID] = None,
        threshold_pct: float = 5.0,
    ) -> dict[str, Any]:
        """Relatório de aceite de contagem (CD-07).

        Retorna:
          - sessions: lista de sessões com erro % e pass/fail por threshold
          - daily: agregado diário com pass/fail
          - summary: totais do período
          - bay_id, threshold_pct: metadados do filtro
        """
        if threshold_pct < 0:
            raise ValidationError("threshold_pct não pode ser negativo")
        if end <= start:
            raise ValidationError("Período inválido: end deve ser posterior a start")

        raw_sessions = self._repo.get_validation_sessions(tenant_id, start, end, bay_id)
        raw_daily = self._repo.get_validation_daily(tenant_id, start, end, bay_id)

        def _session_passed(s: dict) -> bool:
            error_pct = s.get("error_pct")
            if error_pct is None:
                return int(s.get("abs_error", 0)) == 0
            return float(error_pct) <= threshold_pct

        sessions_out = [
            {**s, "passed": _session_passed(s), "id": str(s["id"])}
            for s in raw_sessions
        ]

        def _daily_passed(d: dict) -> bool:
            error_pct = d.get("error_pct")
            if error_pct is None:
                return int(d.get("abs_error", 0)) == 0
            return float(error_pct) <= threshold_pct

        daily_out = [{**d, "passed": _daily_passed(d)} for d in raw_daily]

        # Summary
        total_sessions = len(raw_sessions)
        total_system = sum(int(s.get("system_count", 0) or 0) for s in raw_sessions)
        total_manual = sum(int(s.get("manual_count", 0) or 0) for s in raw_sessions)
        total_abs_error = sum(int(s.get("abs_error", 0) or 0) for s in raw_sessions)
        if total_manual > 0:
            summary_error_pct: Optional[float] = round(total_abs_error / total_manual * 100, 2)
            summary_passed = summary_error_pct <= threshold_pct
        else:
            summary_error_pct = None
            summary_passed = total_abs_error == 0

        return {
            "sessions": sessions_out,
            "daily": daily_out,
            "summary": {
                "sessions_validated": total_sessions,
                "system_count": total_system,
                "manual_count": total_manual,
                "abs_error": total_abs_error,
                "error_pct": summary_error_pct,
                "passed": summary_passed,
            },
            "bay_id": str(bay_id) if bay_id is not None else None,
            "threshold_pct": threshold_pct,
        }
