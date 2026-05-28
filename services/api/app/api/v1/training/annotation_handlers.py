"""
Recognition — Annotation and Class handlers.

Handles: get_annotations, save_annotations, get_classes, create_class
All endpoints contract-compatible with AnnotationInterface.jsx.
"""
import logging
from uuid import UUID

from flask import jsonify, request

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success

from .helpers import get_annotation_service

logger = logging.getLogger(__name__)


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
        annotations = get_annotation_service().get_frame_annotations(UUID(frame_id), user_id)
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
        data = request.get_json() or {}
        annotations = data.get("annotations", [])
        count = get_annotation_service().save_annotations(
            UUID(frame_id), annotations, UUID(str(user_id))
        )
        return jsonify({"success": True, "saved": count}), 200
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("save_annotations_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_classes_handler():
    """Lista classes YOLO do usuário.
    ---
    tags:
      - training
    summary: Listar classes YOLO do usuário
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de classes
    """
    try:
        user_id = get_current_user_id()
        classes = get_annotation_service().get_classes(user_id)
        return jsonify({"success": True, "classes": classes}), 200
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_classes_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def create_class_handler():
    """Cria classe YOLO."""
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        cls = get_annotation_service().create_class(
            user_id=user_id,
            name=data.get("name", ""),
            color=data.get("color", "#3b82f6"),
        )
        return success(cls, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_class_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
