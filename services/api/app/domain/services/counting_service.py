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
    ) -> dict:
        """Partial update of loading-session fields (whitelist enforced)."""
        unknown = set(fields) - UPDATABLE_SESSION_FIELDS
        if unknown:
            raise ValidationError(f"Campo não atualizável: {', '.join(sorted(unknown))}")

        if "acceptance_status" in fields and fields["acceptance_status"] not in VALID_ACCEPTANCE_STATUSES:
            raise ValidationError(f"acceptance_status inválido: {fields['acceptance_status']!r}")
        if "direction" in fields and fields["direction"] not in VALID_DIRECTIONS:
            raise ValidationError(f"direction inválido: {fields['direction']!r}")
        if "manual_count" in fields and fields["manual_count"] < 0:
            raise ValidationError("manual_count não pode ser negativo")

        session = self._repo.get_session(session_id, tenant_id)
        if not session:
            raise NotFoundError(f"Sessão {session_id} não encontrada")
        if str(session.get("tenant_id", "")) != str(tenant_id):
            raise NotFoundError(f"Sessão {session_id} não encontrada")

        if "expected_count" in fields and "divergence" not in fields:
            system_total = self._repo.get_session_total(session_id)
            fields = {**fields, "divergence": system_total - fields["expected_count"]}

        result = self._repo.update_session_fields(session_id, tenant_id, fields)
        return result or session

    def get_validation_report(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        threshold_pct: float = 5.0,
        bay_id: Optional[UUID] = None,
    ) -> dict:
        """Validation report: per-session error + daily aggregate + summary."""
        if threshold_pct < 0:
            raise ValidationError("threshold deve ser ≥ 0")
        if start > end:
            raise ValidationError("Período inválido: start > end")

        sessions_raw = self._repo.get_validation_sessions(tenant_id, start, end, bay_id)
        daily_raw = self._repo.get_validation_daily(tenant_id, start, end, bay_id)

        def _pct(row: dict) -> Optional[float]:
            v = row.get("error_pct")
            if v is None:
                return None
            return float(v)

        def _passes(row: dict) -> bool:
            pct = _pct(row)
            if pct is None:
                return row.get("abs_error", 0) == 0
            return pct <= threshold_pct

        sessions = [
            {**{k: (str(v) if isinstance(v, UUID) else v) for k, v in r.items()},
             "error_pct": _pct(r),
             "passed": _passes(r)}
            for r in sessions_raw
        ]
        daily = [
            {**{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()},
             "error_pct": _pct(r),
             "passed": _passes(r)}
            for r in daily_raw
        ]

        total_sys = sum(r.get("system_count", 0) for r in sessions_raw)
        total_man = sum(r.get("manual_count", 0) for r in sessions_raw)
        total_abs = sum(r.get("abs_error", 0) for r in sessions_raw)
        n = len(sessions_raw)
        if n == 0:
            summary_pct = None
            summary_passed = True
        elif total_man == 0:
            summary_pct = None
            summary_passed = total_abs == 0
        else:
            summary_pct = round(total_abs / total_man * 100, 4)
            summary_passed = summary_pct <= threshold_pct

        return {
            "bay_id": str(bay_id) if bay_id else None,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "threshold_pct": threshold_pct,
            "sessions": sessions,
            "daily": daily,
            "summary": {
                "sessions_validated": n,
                "system_count": total_sys,
                "manual_count": total_man,
                "abs_error": total_abs,
                "error_pct": summary_pct,
                "passed": summary_passed,
            },
        }
