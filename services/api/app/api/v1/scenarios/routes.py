"""
Recognition — Scenario API (read-only).

Compõe o "cenário" de uma câmera (câmera + módulos + operações + regras + agenda)
e expõe o catálogo de operation-types por módulo.
Todas as rotas exigem JWT e filtram por tenant_id (C-01).
"""
import contextlib
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import error, success
from app.domain.services.operations.registry import OperationTypeRegistry
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository
from app.infrastructure.database.repositories.camera_repository import CameraRepository
from app.infrastructure.database.repositories.module_repository import ModuleRepository
from app.infrastructure.database.repositories.operation_repository import OperationRepository

logger = logging.getLogger(__name__)

scenarios_bp = Blueprint("scenarios", __name__, url_prefix="/api/v1")


def _get_camera_repo() -> CameraRepository:
    return CameraRepository(DatabasePool.get_instance())


def _get_module_repo() -> ModuleRepository:
    return ModuleRepository(DatabasePool.get_instance())


def _get_operation_repo() -> OperationRepository:
    return OperationRepository(DatabasePool.get_instance())


def _get_alert_repo() -> AlertRepository:
    return AlertRepository(DatabasePool.get_instance())


@scenarios_bp.route("/cameras/<camera_id>/scenario", methods=["GET"])
@jwt_required()
def get_camera_scenario(camera_id: str):
    """Compõe e retorna o cenário completo de uma câmera.

    Inclui: câmera, módulos habilitados + classes, operações, regras de alerta e agenda.
    Câmera de outro tenant → 404 (C-01).
    """
    tenant_id = str(get_tenant_id())

    cam_repo = _get_camera_repo()
    camera = cam_repo.get_by_id_and_tenant(camera_id, tenant_id)
    if camera is None:
        return error("Câmera não encontrada", 404)

    mod_repo = _get_module_repo()
    tenant_modules = mod_repo.get_by_tenant(tenant_id)
    modules = []
    for tm in tenant_modules:
        if not tm.get("enabled"):
            continue
        module_code = str(tm["module_code"])
        classes = mod_repo.get_classes(module_code)
        modules.append(
            {
                "module_code": module_code,
                "enabled": True,
                "config": tm.get("config"),
                "activated_at": tm.get("activated_at"),
                "expires_at": tm.get("expires_at"),
                "classes": [dict(c) for c in classes],
            }
        )

    op_repo = _get_operation_repo()
    operations = op_repo.list_by_camera(tenant_id, camera_id)

    alert_repo = _get_alert_repo()
    alert_rules = alert_repo.list_for_camera_scenario(tenant_id, camera_id)

    schedule = camera.get("schedule_rules") or []

    scenario = {
        "camera": {
            "id": str(camera["id"]),
            "name": camera["name"],
            "site_id": camera.get("site_id"),
        },
        "modules": modules,
        "operations": [dict(op) for op in operations],
        "alert_rules": [dict(r) for r in alert_rules],
        "schedule": schedule,
    }

    logger.info("scenario_read: camera=%s tenant=%s", camera_id, tenant_id)
    return success({"scenario": scenario})


@scenarios_bp.route("/scenarios/operation-types", methods=["GET"])
@jwt_required()
def list_scenario_operation_types():
    """Catálogo de operation-types por módulo com schema de config.

    Reutiliza OperationTypeRegistry (mesmo registro de /api/modules/<id>/operation-types).
    Módulo inválido → lista vazia (sem tipos registrados para ele), sem erro 4xx/5xx.
    """
    module_code = request.args.get("module", "")

    with contextlib.suppress(Exception):
        import app.domain.services.operations.canonical  # noqa: F401

    types = OperationTypeRegistry.to_catalog(module_code)
    return success({"types": types, "module": module_code})
