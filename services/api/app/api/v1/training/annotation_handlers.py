"""
Recognition — Annotation and Class handlers.

Handles: get_annotations, save_annotations, get_classes, create_class,
update_class, delete_class (WS-A1: classes tenant-scoped + module_code).
All endpoints contract-compatible with AnnotationInterface.jsx
(classes: id, name, color).
"""
import logging
from uuid import UUID

from flask import jsonify, request

from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.domain.services.class_namespace import namespace_tenant_class_id
from app.domain.services.tenant_class_service import TenantClassService
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)

from .helpers import get_annotation_service

logger = logging.getLogger(__name__)

_TRUTHY = ("1", "true", "yes")


def get_tenant_class_service() -> TenantClassService:
    """Factory do TenantClassService (WS-A1) — seam para testes."""
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return TenantClassService(AnnotationRepository(pool))


def get_annotations_handler(frame_id: str):
    """Lista anotações de um frame.
    ---
    tags:
      - training
    summary: Listar anotações de um frame
    security:
      - Bearer: []
    parameters:
      - in: path
        name: frame_id
        type: string
        required: true
    responses:
      200:
        description: Anotações do frame (formato YOLO normalizado)
    """
    try:
        user_id = get_current_user_id()
        tenant_id = get_tenant_id()
        annotations = get_annotation_service().get_frame_annotations(
            UUID(frame_id), user_id, tenant_id
        )
        return jsonify({"success": True, "annotations": annotations}), 200
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_annotations_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def save_annotations_handler(frame_id: str):
    """Salva anotações de um frame. Formato AnnotationInterface.jsx.
    ---
    tags:
      - training
    summary: Salvar anotações de um frame
    description: Salva no banco e exporta labels YOLO para R2
    security:
      - Bearer: []
    parameters:
      - in: path
        name: frame_id
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          properties:
            annotations:
              type: array
              items:
                properties:
                  class_id: {type: integer}
                  x_center: {type: number, minimum: 0, maximum: 1}
                  y_center: {type: number, minimum: 0, maximum: 1}
                  width: {type: number, minimum: 0, maximum: 1}
                  height: {type: number, minimum: 0, maximum: 1}
    responses:
      200:
        description: Anotações salvas
      400:
        description: Coordenadas inválidas
    """
    try:
        user_id = get_current_user_id()
        tenant_id = get_tenant_id()
        data = request.get_json() or {}
        annotations = data.get("annotations", [])
        count = get_annotation_service().save_annotations(
            UUID(frame_id), annotations, UUID(str(user_id)), tenant_id
        )
        return jsonify({"success": True, "saved": count}), 200
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("save_annotations_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_classes_handler():
    """Lista classes do tenant (WS-A1).
    ---
    tags:
      - training
    summary: Listar classes de anotação do tenant
    description: |
      Escopo tenant_id + module_code (fallback user_id p/ linhas legadas).
      Contrato AnnotationInterface.jsx preservado: {success, classes: [...]}.
    security:
      - Bearer: []
    parameters:
      - in: query
        name: module
        type: string
        default: epi
      - in: query
        name: include_counts
        type: boolean
        default: false
        description: Inclui annotation_count (amostras por classe)
    responses:
      200:
        description: Lista de classes (id, name, color, module_code)
    """
    try:
        user_id = get_current_user_id()
        tenant_id = get_tenant_id()
        module_code = request.args.get("module", "epi")
        include_counts = (
            request.args.get("include_counts", "").lower() in _TRUTHY
        )
        classes = get_tenant_class_service().list_classes(
            tenant_id,
            user_id=user_id,
            module_code=module_code,
            include_counts=include_counts,
        )
        return jsonify({"success": True, "classes": classes}), 200
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_classes_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def create_class_handler():
    """Cria classe de anotação tenant-scoped (WS-A1).
    ---
    tags:
      - training
    summary: Criar classe de anotação
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          properties:
            name: {type: string}
            color: {type: string, default: '#3b82f6'}
            module: {type: string, default: epi}
    responses:
      201:
        description: Classe criada
      409:
        description: Nome duplicado
    """
    try:
        user_id = get_current_user_id()
        tenant_id = get_tenant_id()
        data = request.get_json() or {}
        cls = get_tenant_class_service().create_class(
            user_id=user_id,
            tenant_id=tenant_id,
            name=data.get("name", ""),
            color=data.get("color", "#3b82f6"),
            module_code=data.get("module") or request.args.get("module", "epi"),
        )
        # AI_NOTE (união catálogo∪tenant): o anotador (AnnotationInterface.jsx
        # createNewClass) lê `result.data.class_id ?? result.data.id` — sem
        # este campo ele usaria o id CRU de yolo_classes (SERIAL global), que
        # colide com o espaço de class_id 0-based de module_classes. Namespacing
        # aqui (mesma função que ModuleService.get_classes usa pra expor a
        # classe na leitura) garante que o id que o front recebe ao criar é o
        # MESMO que ele vai ver na próxima listagem — e o mesmo que
        # AnnotationService._validate_class aceita no save.
        cls["class_id"] = namespace_tenant_class_id(cls["id"])
        return success(cls, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_class_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def update_class_handler(class_id: int):
    """Renomeia/recolore classe do tenant (WS-A1).
    ---
    tags:
      - training
    summary: Atualizar classe (name e/ou color)
    security:
      - Bearer: []
    parameters:
      - in: path
        name: class_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          properties:
            name: {type: string}
            color: {type: string}
    responses:
      200:
        description: Classe atualizada
      404:
        description: Classe não encontrada (ou de outro tenant)
    """
    try:
        user_id = get_current_user_id()
        tenant_id = get_tenant_id()
        data = request.get_json() or {}
        cls = get_tenant_class_service().update_class(
            class_id,
            tenant_id,
            user_id=user_id,
            name=data.get("name"),
            color=data.get("color"),
        )
        return success(cls)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("update_class_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def delete_class_handler(class_id: int):
    """Deleta classe do tenant sem anotações vinculadas (WS-A1).
    ---
    tags:
      - training
    summary: Deletar classe
    description: 409 se frame_annotations referenciam a classe.
    security:
      - Bearer: []
    parameters:
      - in: path
        name: class_id
        type: integer
        required: true
    responses:
      200:
        description: Classe removida
      404:
        description: Classe não encontrada (ou de outro tenant)
      409:
        description: Classe referenciada por anotações
    """
    try:
        user_id = get_current_user_id()
        tenant_id = get_tenant_id()
        get_tenant_class_service().delete_class(
            class_id, tenant_id, user_id=user_id
        )
        return success({"deleted": True, "id": class_id}, message="Classe removida")
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("delete_class_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def pre_annotate_frame_handler(frame_id: str):
    """Dispara pré-anotação assistida de um frame (WS-B4).

    Backend plugável, desligado por padrão (feature flag por tenant —
    ver ADR-0031, adendo). 403 se a flag não estiver ligada pro tenant.
    """
    try:
        user_id = get_current_user_id()
        tenant_id = get_tenant_id()
        data = request.get_json(silent=True) or {}
        module_code = data.get("module_code") or request.args.get("module", "epi")

        count = get_annotation_service().pre_annotate_frame(
            UUID(frame_id), tenant_id, UUID(str(user_id)), module_code
        )
        return success({"frame_id": frame_id, "annotations_count": count})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("pre_annotate_frame_error: frame=%s err=%s", frame_id, exc, exc_info=True)
        return error("Erro ao pré-anotar frame", 500)


def accept_suggestions_handler(frame_id: str):
    """Aceita pré-anotações sugeridas como anotações reais (WS-B4).

    Body opcional: {"indices": [0, 2]} — aceita só os índices dados (0-based,
    mesma ordem da resposta de GET .../frames/<id>/annotations). Sem body,
    aceita todas as sugestões pendentes.
    """
    try:
        user_id = get_current_user_id()
        tenant_id = get_tenant_id()
        data = request.get_json(silent=True) or {}
        indices = data.get("indices")
        if indices is not None and not isinstance(indices, list):
            return error("indices deve ser uma lista de inteiros", 400)

        count = get_annotation_service().accept_suggestions(
            UUID(frame_id), UUID(str(user_id)), indices=indices, tenant_id=tenant_id
        )
        return success({"frame_id": frame_id, "accepted": count})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("accept_suggestions_error: frame=%s err=%s", frame_id, exc, exc_info=True)
        return error("Erro ao aceitar sugestões", 500)
