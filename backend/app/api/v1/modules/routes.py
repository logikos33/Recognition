"""
EPI Monitor V2 — Modules Routes.

Endpoints de módulos multi-tenant: listing, classes e stats.
"""
import logging

from flask import Blueprint
from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.responses import error, success
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


@modules_bp.route("/<module_code>/classes/detect", methods=["POST"])
@jwt_required()
def detect_in_frame(module_code: str):  # type: ignore[no-untyped-def]
    """Testa detecção DINO em um frame. Retorna detecções para preview.

    AI_NOTE: US-037 — chama pre-annotation-service para detectar objetos
    no frame com os prompts DINO configurados no módulo.
    """
    import json  # noqa: PLC0415
    import os  # noqa: PLC0415
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    from flask import request  # noqa: PLC0415

    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
    from app.infrastructure.database.repositories.frame_repository import (
        FrameRepository,  # noqa: PLC0415
    )

    try:
        data = request.get_json() or {}
        frame_id = data.get("frame_id", "")
        if not frame_id:
            return error("frame_id obrigatório", 400)

        pool = DatabasePool.get_instance()
        frame_repo = FrameRepository(pool)
        frame = frame_repo._execute_one(
            "SELECT tf.* FROM training_frames tf "
            "JOIN training_videos tv ON tv.id = tf.video_id "
            "WHERE tf.id = %s",
            (frame_id,),
        )
        if not frame:
            return error("Frame não encontrado", 404)

        pre_annot_url = os.environ.get(
            "PRE_ANNOTATION_SERVICE_URL",
            "http://pre-annotation-service.railway.internal:8080",
        )
        url = f"{pre_annot_url}/api/v1/pre-annotate/{frame_id}"
        req = urllib.request.Request(url, method="POST")  # noqa: S310
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                body = json.loads(resp.read())
                detections = body.get("data", {}).get("annotations", [])
        except (urllib.error.URLError, Exception) as exc:  # noqa: BLE001
            logger.warning("detect_pre_annot_failed: frame=%s err=%s", frame_id, exc)
            detections = []

        return success({"detections": detections, "frame_id": frame_id})
    except Exception as exc:
        logger.error("detect_in_frame_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@modules_bp.route("/<module_code>/classes/<class_id>", methods=["PATCH"])
@jwt_required()
def toggle_module_class(module_code: str, class_id: str):  # type: ignore[no-untyped-def]
    """Ativa ou desativa uma classe do módulo."""
    from flask import request  # noqa: PLC0415

    try:
        data = request.get_json() or {}
        is_active = bool(data.get("is_active", True))
        cls = module_service.toggle_class(class_id, is_active)
        return success({"class": cls})
    except Exception as exc:
        logger.error("toggle_class_error: class=%s err=%s", class_id, exc, exc_info=True)
        return error("Erro interno", 500)
