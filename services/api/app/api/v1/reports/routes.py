"""
Recognition — Reports Routes.

Reports globais para home page do app + relatório de compliance EPI.
"""
import logging
from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import error, success
from app.domain.services.compliance_report_service import compliance_report_service
from app.domain.services.report_service import report_service

logger = logging.getLogger(__name__)

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@reports_bp.route("/home", methods=["GET"])
@jwt_required()
def home_reports():  # type: ignore[no-untyped-def]
    """Reports globais para a home page (todos os módulos do tenant)."""
    try:
        tenant_id = get_tenant_id()
        reports = report_service.get_home_reports(tenant_id)
        return success(reports)
    except Exception as exc:
        logger.error("home_reports_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@reports_bp.route("/compliance", methods=["GET"])
@jwt_required()
def compliance_report():  # type: ignore[no-untyped-def]
    """Relatório de compliance EPI on-demand.

    Query params:
      - period: "dia" | "semana" (obrigatório)
      - from: ISO 8601 UTC (opcional, sobrescreve period)
      - to:   ISO 8601 UTC (opcional, sobrescreve period)

    Returns:
      { summary: {...}, pdf_url: "...", period: {...} }
    """
    try:
        tenant_id = get_tenant_id()
    except Exception as exc:
        logger.warning("compliance_report_auth_error: %s", exc)
        return error("Não autorizado", 401)

    period = request.args.get("period", "").strip().lower()
    if not period:
        return error("Parâmetro 'period' é obrigatório (dia | semana)", 400)

    from_str = request.args.get("from", "").strip()
    to_str = request.args.get("to", "").strip()

    from_dt: datetime | None = None
    to_dt: datetime | None = None

    if from_str:
        try:
            from_dt = datetime.fromisoformat(from_str.replace("Z", "+00:00"))
            if from_dt.tzinfo is None:
                from_dt = from_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return error("Parâmetro 'from' inválido — use ISO 8601 (ex: 2024-01-01T00:00:00Z)", 400)

    if to_str:
        try:
            to_dt = datetime.fromisoformat(to_str.replace("Z", "+00:00"))
            if to_dt.tzinfo is None:
                to_dt = to_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return error("Parâmetro 'to' inválido — use ISO 8601 (ex: 2024-01-31T23:59:59Z)", 400)

    try:
        result = compliance_report_service.generate(
            tenant_id=tenant_id,
            period=period,
            from_dt=from_dt,
            to_dt=to_dt,
        )
        return success(result)
    except ValueError as exc:
        logger.warning("compliance_report_invalid_period: %s", exc)
        return error(str(exc), 400)
    except Exception as exc:
        logger.error("compliance_report_error: %s", exc, exc_info=True)
        return error("Erro interno ao gerar relatório de compliance", 500)
