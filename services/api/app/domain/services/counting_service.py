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

# Threshold default do aceite (CD-07): erro <= 5% por sessão/turno
DEFAULT_ACCEPTANCE_THRESHOLD_PCT = 5.0


class CountingService:

    def __init__(self, repo: CountingRepository) -> None:
        self._repo = repo

    def start_session(
        self,
        tenant_id: UUID,
        camera_id: UUID,
        module_code: str,
        bay_id: Optional[UUID] = None,
        truck_plate: Optional[str] = None,
        direction: Optional[str] = None,
        expected_count: Optional[int] = None,
    ) -> dict:
        """Cria nova sessão de contagem. Retorna session dict."""
        if not module_code:
            raise ValidationError("module_code é obrigatório")
        if direction is not None and direction not in VALID_DIRECTIONS:
            raise ValidationError(
                f"direction inválida — use {' ou '.join(VALID_DIRECTIONS)}"
            )
        session = self._repo.create_session(
            tenant_id,
            camera_id,
            module_code,
            bay_id=bay_id,
            truck_plate=truck_plate,
            direction=direction,
            expected_count=expected_count,
        )
        logger.info(
            "counting_session_started: id=%s camera=%s module=%s bay=%s",
            session["id"], camera_id, module_code, bay_id,
        )
        return session

    def stop_session(self, session_id: UUID, tenant_id: UUID) -> dict:
        """Encerra sessão e retorna totais agregados por classe."""
        session = self._repo.get_session(session_id)
        if not session:
            raise NotFoundError(f"Sessão {session_id} não encontrada")
        if str(session["tenant_id"]) != str(tenant_id):
            raise NotFoundError(f"Sessão {session_id} não encontrada")

        # Aggregate counts from events
        rows = self._repo.get_session_counts(session_id)
        total_counts = {r["class_name"]: r["count"] for r in rows}

        updated = self._repo.stop_session(session_id, total_counts)
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
        session = self._repo.get_session(session_id)
        if not session:
            raise NotFoundError(f"Sessão {session_id} não encontrada")
        if str(session["tenant_id"]) != str(tenant_id):
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

    # --- CD-03/CD-06/CD-07: update parcial de sessão ---

    def update_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
        fields: dict[str, Any],
    ) -> dict:
        """Update parcial (PATCH) de campos da sessão de carga/descarga.

        Aceita apenas campos da whitelist UPDATABLE_SESSION_FIELDS.
        Valida direction/acceptance_status contra os CHECK constraints e
        recalcula divergence quando expected_count é informado.
        """
        session = self._repo.get_session(session_id)
        if not session or str(session["tenant_id"]) != str(tenant_id):
            raise NotFoundError("Sessão", str(session_id))

        clean = {k: v for k, v in fields.items() if k in UPDATABLE_SESSION_FIELDS}
        if not clean:
            raise ValidationError(
                "Nenhum campo atualizável informado — permitidos: "
                + ", ".join(UPDATABLE_SESSION_FIELDS)
            )

        direction = clean.get("direction")
        if direction is not None and direction not in VALID_DIRECTIONS:
            raise ValidationError(
                f"direction inválida — use {' ou '.join(VALID_DIRECTIONS)}"
            )
        acceptance = clean.get("acceptance_status")
        if acceptance is not None and acceptance not in VALID_ACCEPTANCE_STATUSES:
            raise ValidationError(
                "acceptance_status inválido — use "
                + ", ".join(VALID_ACCEPTANCE_STATUSES)
            )
        for int_field in ("manual_count", "expected_count"):
            value = clean.get(int_field)
            if value is not None:
                try:
                    clean[int_field] = int(value)
                except (TypeError, ValueError) as exc:
                    raise ValidationError(f"{int_field} deve ser inteiro") from exc
                if clean[int_field] < 0:
                    raise ValidationError(f"{int_field} deve ser >= 0")

        # Divergência (CD-10 dormante): system_count - expected_count,
        # recalculada quando expected_count chega e não foi informada explícita.
        if clean.get("expected_count") is not None and "divergence" not in clean:
            system_count = self._repo.get_session_total(session_id)
            clean["divergence"] = system_count - clean["expected_count"]

        updated = self._repo.update_session_fields(session_id, tenant_id, clean)
        if not updated:
            raise NotFoundError("Sessão", str(session_id))
        logger.info(
            "counting_session_updated: id=%s fields=%s",
            session_id, sorted(clean.keys()),
        )
        return updated

    # --- CD-07: relatório de validação/aceite ---

    def get_validation_report(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        bay_id: Optional[UUID] = None,
        threshold_pct: float = DEFAULT_ACCEPTANCE_THRESHOLD_PCT,
    ) -> dict:
        """Relatório de aceite: system_count vs manual_count por sessão + dia.

        pass/fail por sessão, por dia e agregado, dado threshold percentual
        (default 5%). Quando manual_count = 0 (error_pct NULL no SQL),
        passa apenas se abs_error = 0.
        """
        if threshold_pct < 0:
            raise ValidationError("threshold deve ser >= 0")
        if end <= start:
            raise ValidationError("Período inválido — end deve ser maior que start")

        rows = self._repo.get_validation_sessions(tenant_id, start, end, bay_id)
        daily = self._repo.get_validation_daily(tenant_id, start, end, bay_id)

        sessions = [self._decorate_passed(dict(r), threshold_pct) for r in rows]
        daily_out = [self._decorate_passed(dict(d), threshold_pct) for d in daily]

        system_total = sum(int(s["system_count"]) for s in sessions)
        manual_total = sum(int(s["manual_count"]) for s in sessions)
        abs_error = abs(system_total - manual_total)
        error_pct = (
            round(abs_error / manual_total * 100, 2) if manual_total > 0 else None
        )
        summary = self._decorate_passed(
            {
                "sessions_validated": len(sessions),
                "system_count": system_total,
                "manual_count": manual_total,
                "abs_error": abs_error,
                "error_pct": error_pct,
            },
            threshold_pct,
        )

        return {
            "threshold_pct": threshold_pct,
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "bay_id": str(bay_id) if bay_id else None,
            "sessions": sessions,
            "daily": daily_out,
            "summary": summary,
        }

    @staticmethod
    def _decorate_passed(row: dict[str, Any], threshold_pct: float) -> dict[str, Any]:
        """Adiciona 'passed' a uma linha com error_pct/abs_error."""
        error_pct = row.get("error_pct")
        if error_pct is not None:
            row["error_pct"] = float(error_pct)
            row["passed"] = float(error_pct) <= threshold_pct
        else:
            # manual_count == 0 → só passa se contagem do sistema também for 0
            row["passed"] = int(row.get("abs_error") or 0) == 0
        return row

    # --- Dashboard real do módulo carga/descarga (flag mock desligada) ---

    def get_loading_dashboard(
        self,
        tenant_id: UUID,
        start: datetime,
        module_code: str = "fueling",
    ) -> dict:
        """KPIs + série diária a partir de counting_sessions (dados reais)."""
        rollup = self._repo.get_loading_rollup(tenant_id, module_code, start) or {}
        total_sessoes = int(rollup.get("total_sessoes") or 0)
        if total_sessoes == 0:
            return {
                "no_data": True,
                "message": "Nenhum dado de carregamento disponível para o período.",
            }
        series = self._repo.get_loading_daily_series(tenant_id, module_code, start)
        tempo_medio = rollup.get("tempo_medio_minutos")
        return {
            "no_data": False,
            "kpis": {
                "total_carregado": total_sessoes,
                "tempo_medio_minutos": (
                    round(float(tempo_medio), 1) if tempo_medio is not None else None
                ),
                "total_itens_movimentados": int(rollup.get("total_itens") or 0),
                "eventos_nao_conformidade": int(
                    rollup.get("sessoes_divergentes") or 0
                ),
            },
            "series_operacoes_diarias": [
                {
                    "dia": d["dia"].strftime("%d/%m") if d.get("dia") else None,
                    "operacoes": int(d["operacoes"]),
                }
                for d in series
            ],
        }

    def list_loading_bays(
        self,
        tenant_id: UUID,
        module_code: str = "fueling",
    ) -> list[dict]:
        """Sessões em andamento mapeadas para cards de baia (dados reais)."""
        rows = self._repo.list_active_loading_bays(tenant_id, module_code)
        return [
            {
                "session_id": str(r["session_id"]),
                "bay_id": str(r["bay_id"]) if r.get("bay_id") else None,
                "placa": r.get("truck_plate"),
                "direcao": r.get("direction"),
                "status": "active",
                "total_itens": int(r.get("total_itens") or 0),
                "iniciada_em": (
                    r["started_at"].isoformat() if r.get("started_at") else None
                ),
            }
            for r in rows
        ]
