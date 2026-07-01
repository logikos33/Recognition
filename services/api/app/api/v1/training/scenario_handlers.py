"""
Recognition — Scenario config handlers.

PUT /api/training/scenarios/<model_id>/config
GET /api/training/scenarios/<model_id>/config

Body esperado no PUT:
{
  "classes":              ["helmet", "no_helmet", ...],
  "counting_line":        {"x1": 0.1, "y1": 0.5, "x2": 0.9, "y2": 0.5} | null,
  "roi":                  [{"x": 0.1, "y": 0.1}, ...] | [],
  "confidence_threshold": 0.5,
  "camera_id":            "<uuid>" | null
}

Tenant isolation: derived via JOIN trained_models → users.tenant_id.
"""
import logging
from uuid import UUID

from flask import request

from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.training_repository import (
    TrainingRepository,
)

logger = logging.getLogger(__name__)

_VALID_EPI_CLASSES = {
    "helmet", "no_helmet", "vest", "no_vest",
    "gloves", "no_gloves", "glasses", "no_glasses",
    "truck", "plate", "fuel_nozzle", "product_box", "pallet",
}


def _get_repo() -> TrainingRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return TrainingRepository(pool)


def _validate_counting_line(data: object) -> dict | None:
    """Valida e retorna counting_line ou None."""
    if data is None:
        return None
    if not isinstance(data, dict):
        return None
    try:
        return {
            "x1": float(data["x1"]),
            "y1": float(data["y1"]),
            "x2": float(data["x2"]),
            "y2": float(data["y2"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _validate_roi(data: object) -> list:
    """Valida e retorna lista de pontos ROI normalizados."""
    if not isinstance(data, list):
        return []
    validated: list = []
    for pt in data:
        if isinstance(pt, dict) and "x" in pt and "y" in pt:
            try:
                validated.append({"x": float(pt["x"]), "y": float(pt["y"])})
            except (TypeError, ValueError):
                pass
    return validated


def upsert_scenario_config_handler(model_id: str):
    """PUT /api/training/scenarios/<model_id>/config — salva config de cenário."""
    try:
        tenant_id = get_tenant_id()
        _ = get_current_user_id()  # autentica o usuário

        body = request.get_json() or {}

        # Validar classes
        raw_classes = body.get("classes", [])
        if not isinstance(raw_classes, list):
            return error("classes deve ser uma lista", 400)
        classes = [c for c in raw_classes if isinstance(c, str) and c in _VALID_EPI_CLASSES]

        # Validar counting_line
        counting_line = _validate_counting_line(body.get("counting_line"))

        # Validar roi
        roi = _validate_roi(body.get("roi", []))

        # Validar confidence_threshold
        try:
            confidence = float(body.get("confidence_threshold", 0.5))
            confidence = max(0.1, min(0.99, confidence))
        except (TypeError, ValueError):
            confidence = 0.5

        # Validar camera_id
        raw_camera = body.get("camera_id")
        camera_id: str | None = None
        if raw_camera:
            try:
                camera_id = str(UUID(str(raw_camera)))
            except ValueError:
                return error("camera_id inválido", 400)

        config = {
            "classes": classes,
            "counting_line": counting_line,
            "roi": roi,
            "confidence_threshold": confidence,
            "camera_id": camera_id,
        }

        repo = _get_repo()
        try:
            model_uuid = UUID(model_id)
        except ValueError:
            return error("model_id inválido", 400)

        result = repo.update_scenario_config(model_uuid, tenant_id, config)
        if result is None:
            return error("Modelo não encontrado ou sem permissão", 404)

        return success({"model_id": model_id, "scenario_config": config})

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("upsert_scenario_config_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_scenario_config_handler(model_id: str):
    """GET /api/training/scenarios/<model_id>/config — retorna config atual."""
    try:
        tenant_id = get_tenant_id()
        _ = get_current_user_id()

        repo = _get_repo()
        try:
            model_uuid = UUID(model_id)
        except ValueError:
            return error("model_id inválido", 400)

        result = repo.get_scenario_config(model_uuid, tenant_id)
        if result is None:
            return error("Modelo não encontrado ou sem permissão", 404)

        return success({
            "model_id": model_id,
            "scenario_config": result.get("scenario_config"),
        })

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_scenario_config_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
