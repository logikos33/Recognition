"""
EPI Monitor V2 — Reports Routes.

Reports globais para home page do app.
"""
import logging

from flask import Blueprint
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import success, error
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
