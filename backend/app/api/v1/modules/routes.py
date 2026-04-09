"""
EPI Monitor V2 — Modules Routes.

Endpoints de módulos multi-tenant: listing, classes e stats.
"""
import logging

from flask import Blueprint
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id, get_tenant_id
from app.core.responses import success, error
from app.domain.services.module_service import module_service

logger = logging.getLogger(__name__)

modules_bp = Blueprint("modules", __name__, url_prefix="/api/modules")


@modules_bp.route("/", methods=["GET"])
@jwt_required()
def list_modules():  # type: ignore[no-untyped-def]
    """Lista módulos do tenant com stats básicas."""
    try:
        tenant_id = get_tenant_id()
        modules = module_service.list_tenant_modules(tenant_id)
        return success({"modules": modules})
    except Exception as exc:
        logger.error("list_modules_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@modules_bp.route("/<module_code>", methods=["GET"])
@jwt_required()
def get_module(module_code: str):  # type: ignore[no-untyped-def]
    """Retorna detalhes de um módulo do tenant."""
    try:
        tenant_id = get_tenant_id()
        module = module_service.get_module(tenant_id, module_code)
        if not module:
            return error("Módulo não encontrado", 404)
        return success({"module": module})
    except Exception as exc:
        logger.error("get_module_error: module=%s err=%s", module_code, exc, exc_info=True)
        return error("Erro interno", 500)


@modules_bp.route("/<module_code>/classes", methods=["GET"])
@jwt_required()
def get_module_classes(module_code: str):  # type: ignore[no-untyped-def]
    """Lista classes YOLO do módulo."""
    try:
        classes = module_service.get_classes(module_code)
        return success({"classes": classes})
    except Exception as exc:
        logger.error("get_module_classes_error: module=%s err=%s", module_code, exc, exc_info=True)
        return error("Erro interno", 500)


@modules_bp.route("/<module_code>/stats", methods=["GET"])
@jwt_required()
def get_module_stats(module_code: str):  # type: ignore[no-untyped-def]
    """Estatísticas do módulo para o tenant."""
    try:
        tenant_id = get_tenant_id()
        if not module_service.tenant_has_module(tenant_id, module_code):
            return error("Módulo não disponível", 403)
        stats = module_service.get_stats(tenant_id, module_code)
        return success({"stats": stats})
    except Exception as exc:
        logger.error("get_module_stats_error: module=%s err=%s", module_code, exc, exc_info=True)
        return error("Erro interno", 500)
