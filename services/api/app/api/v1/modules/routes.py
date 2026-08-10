"""
Recognition — Modules Routes.

Endpoints de módulos multi-tenant: listing, classes e stats.
"""
import logging

from flask import Blueprint
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.exceptions import NotFoundError
from app.core.responses import error, success
from app.core.tenant import has_permission
from app.domain.services.module_service import module_service

logger = logging.getLogger(__name__)

modules_bp = Blueprint("modules", __name__, url_prefix="/api/modules")

# WS7/task-073: gate por permissão — default_roles de modules:write ==
# {admin, superadmin} (app/core/permissions.py).
_MODULES_WRITE_PERMISSION = "modules:write"


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
    """Lista classes YOLO do módulo: catálogo global ∪ custom do tenant do
    contexto (get_tenant_id() — honra contexto assumido, C-01/ADR-0017).

    `?include_archived=1` inclui classes do tenant arquivadas (archived_at
    preenchido) — a tela de gestão de classes (estúdio de anotação) precisa
    delas para oferecer "restaurar"; o anotador em si nunca passa esse
    param, então continua sem ofertar classe aposentada para escolha nova.
    """
    from flask import request  # noqa: PLC0415

    try:
        tenant_id = get_tenant_id()
        include_archived = request.args.get("include_archived", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        classes = module_service.get_classes(
            module_code, tenant_id=tenant_id, include_archived=include_archived
        )
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


@modules_bp.route("/<module_code>/classes/<class_id>", methods=["PATCH"])
@jwt_required()
def toggle_module_class(module_code: str, class_id: str):  # type: ignore[no-untyped-def]
    """Ativa ou desativa uma classe do módulo.

    task-073/achado #6: requer permissão `modules:write` (admin/superadmin) e
    isola por tenant — uma classe de um módulo que o tenant requisitante não
    tem habilitado retorna 404 (nunca 403, para não vazar existência de
    recurso de outro tenant/módulo — C-01).
    """
    from flask import request  # noqa: PLC0415

    try:
        if not has_permission(_MODULES_WRITE_PERMISSION):
            return error("Permissão insuficiente para alterar classes do módulo", 403)

        tenant_id = get_tenant_id()
        data = request.get_json() or {}
        is_active = bool(data.get("is_active", True))
        cls = module_service.toggle_class(tenant_id, module_code, class_id, is_active)
        return success({"class": cls})
    except NotFoundError:
        raise
    except Exception as exc:
        logger.error("toggle_class_error: class=%s err=%s", class_id, exc, exc_info=True)
        return error("Erro interno", 500)
