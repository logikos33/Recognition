"""
Recognition — Operations API.

CRUD de operações configuráveis por câmera/módulo.
Todas as rotas exigem JWT e filtram por tenant_id.
"""
import contextlib
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import error, success
from app.domain.services.operations.registry import OperationTypeRegistry
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.operation_repository import OperationRepository

logger = logging.getLogger(__name__)

operations_bp = Blueprint("operations", __name__, url_prefix="/api")


def _get_repo() -> OperationRepository:
    """Obtém instância do repository via DatabasePool singleton."""
    pool = DatabasePool.get_instance()
    return OperationRepository(pool)


@operations_bp.route("/modules/<module_id>/operation-types", methods=["GET"])
@jwt_required()
def list_operation_types(module_id: str):
    """Lista tipos de operação disponíveis para o módulo informado.

    Retorna canônicos (available_modules=['*']) + específicos do módulo.
    """
    # Garante que imports das canonicas foram feitos (auto-registro)
    with contextlib.suppress(Exception):
        import app.domain.services.operations.canonical  # noqa: F401

    types = OperationTypeRegistry.to_catalog(module_id)
    return success({"types": types, "module_id": module_id})


@operations_bp.route("/cameras/<int:camera_id>/operations", methods=["GET"])
@jwt_required()
def list_camera_operations(camera_id: int):
    """Lista operações de uma câmera. Filtra por module_id se informado."""
    tenant_id = str(get_tenant_id())
    module_id = request.args.get("module_id")
    repo = _get_repo()

    if module_id:
        ops = repo.list_by_camera_and_module(tenant_id, camera_id, module_id)
    else:
        ops = repo.list_by_camera(tenant_id, camera_id)

    return success({"operations": ops, "camera_id": camera_id})


@operations_bp.route("/cameras/<int:camera_id>/operations", methods=["POST"])
@jwt_required()
def create_operation(camera_id: int):
    """Cria nova operação para a câmera. Valida config antes de persistir."""
    tenant_id = str(get_tenant_id())
    body = request.get_json(silent=True) or {}

    module_id = body.get("module_id", "generic")
    type_id = body.get("type_id", "")
    name = (body.get("name") or "").strip()
    config = body.get("config", {})

    if not type_id:
        return error("type_id é obrigatório", 422)
    if not name:
        return error("name é obrigatório", 422)

    # Valida config usando a classe de operação registrada
    with contextlib.suppress(Exception):
        import app.domain.services.operations.canonical  # noqa: F401

    op_class = OperationTypeRegistry.get(type_id)
    if op_class is None:
        return error(f"Tipo de operação desconhecido: {type_id}", 422)

    instance = op_class(config)
    validation_errors = instance.validate_config(config)
    if validation_errors:
        return error(f"Configuração inválida: {'; '.join(validation_errors)}", 422)

    repo = _get_repo()
    row = repo.create(tenant_id, camera_id, module_id, type_id, name, config)
    if not row:
        return error("Erro ao criar operação", 500)

    logger.info("operation_created: id=%s type=%s camera=%s", row["id"], type_id, camera_id)
    return success({"operation": row}), 201


@operations_bp.route("/operations/<int:operation_id>", methods=["PUT"])
@jwt_required()
def update_operation(operation_id: int):
    """Atualiza nome e config de uma operação. Incrementa version."""
    import json

    import redis as redis_lib

    from app.config import get_config

    tenant_id = str(get_tenant_id())
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    config = body.get("config", {})

    if not name:
        return error("name é obrigatório", 422)

    repo = _get_repo()
    existing = repo.get_by_id(tenant_id, operation_id)
    if not existing:
        return error("Operação não encontrada", 404)

    type_id = existing["type_id"]
    with contextlib.suppress(Exception):
        import app.domain.services.operations.canonical  # noqa: F401

    op_class = OperationTypeRegistry.get(type_id)
    if op_class:
        instance = op_class(config)
        validation_errors = instance.validate_config(config)
        if validation_errors:
            return error(f"Configuração inválida: {'; '.join(validation_errors)}", 422)

    updated = repo.update(tenant_id, operation_id, name, config)
    if not updated:
        return error("Erro ao atualizar operação", 500)

    # Publica no Redis para hot-reload no worker
    try:
        cfg = get_config()
        if cfg.REDIS_URL:
            r = redis_lib.from_url(cfg.REDIS_URL, socket_connect_timeout=2)
            r.publish(
                f"operations:reload:{operation_id}",
                json.dumps({"operation_id": operation_id, "version": updated["version"]}),
            )
    except Exception as exc:
        logger.warning("operation_reload_publish_failed: id=%s err=%s", operation_id, exc)

    logger.info("operation_updated: id=%s version=%s", operation_id, updated.get("version"))
    return success({"operation": updated})


@operations_bp.route("/operations/<int:operation_id>", methods=["DELETE"])
@jwt_required()
def delete_operation(operation_id: int):
    """Remove operação. Se há histórico, exige confirm_name no query string."""
    tenant_id = str(get_tenant_id())
    confirm_name = request.args.get("confirm_name", "")

    repo = _get_repo()
    existing = repo.get_by_id(tenant_id, operation_id)
    if not existing:
        return error("Operação não encontrada", 404)

    result_count = repo.count_results(operation_id)
    if result_count > 0 and confirm_name != existing["name"]:
        return error(
            f"Esta operação tem {result_count} resultados históricos. "
            "Passe confirm_name com o nome exato para confirmar exclusão.",
            409,
        )

    deleted = repo.delete(tenant_id, operation_id)
    if deleted == 0:
        return error("Erro ao excluir operação", 500)

    logger.info("operation_deleted: id=%s name=%s", operation_id, existing["name"])
    return success({"deleted": True, "operation_id": operation_id})


@operations_bp.route("/operations/<int:operation_id>/results", methods=["GET"])
@jwt_required()
def get_operation_results(operation_id: int):
    """Retorna histórico de resultados de uma operação."""
    tenant_id = str(get_tenant_id())
    limit = min(int(request.args.get("limit", 100)), 500)

    repo = _get_repo()
    existing = repo.get_by_id(tenant_id, operation_id)
    if not existing:
        return error("Operação não encontrada", 404)

    results = repo.list_results(operation_id, limit)
    return success({"results": results, "operation_id": operation_id})


@operations_bp.route("/operations/<int:operation_id>/test", methods=["POST"])
@jwt_required()
def test_operation(operation_id: int):
    """Executa evaluate() com detecções fornecidas sem persistir resultado.

    Útil para testar configuração antes de salvar.
    """
    tenant_id = str(get_tenant_id())
    body = request.get_json(silent=True) or {}
    detections = body.get("detections", [])
    frame_meta = body.get("frame_meta", {"width": 640, "height": 360})

    with contextlib.suppress(Exception):
        import app.domain.services.operations.canonical  # noqa: F401

    repo = _get_repo()
    existing = repo.get_by_id(tenant_id, operation_id)
    if not existing:
        return error("Operação não encontrada", 404)

    op_class = OperationTypeRegistry.get(existing["type_id"])
    if op_class is None:
        return error(f"Tipo desconhecido: {existing['type_id']}", 422)

    instance = op_class(existing["config"])
    result = instance.evaluate(detections, frame_meta, {})
    return success({"test_result": result, "operation_id": operation_id})
