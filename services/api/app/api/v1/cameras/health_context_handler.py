"""
Recognition — Camera health context handler (WS10).

GET /api/cameras/<camera_id>/health-context — telemetria real do site da câmera
para o aviso health-aware do seletor de FPS.

Tenant-scoped e acessível a QUALQUER papel autenticado do tenant (operator
incluído) — diferente de GET /api/v1/edge/sites/health, que é admin-only.
Sem site_id ou sem heartbeat → 200 com has_telemetry=false (fallback na UI).
Câmera de outro tenant → 404 (C-01, não vaza existência).
"""
import logging
from typing import Any, Optional

from flask_jwt_extended import jwt_required

from app.core.auth import get_tenant_id
from app.core.edge_offline import derive_site_health_status
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.camera_repository import CameraRepository
from app.infrastructure.database.repositories.edge_heartbeat_repository import (
    EdgeHeartbeatRepository,
)

logger = logging.getLogger(__name__)


def _get_camera_repo() -> CameraRepository:
    return CameraRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


def _get_heartbeat_repo() -> EdgeHeartbeatRepository:
    return EdgeHeartbeatRepository(DatabasePool.get_instance())  # type: ignore[arg-type]


def _num(value: Any) -> Optional[float]:
    """NUMERIC (Decimal) → float, preservando None."""
    return float(value) if value is not None else None


def _empty_context(
    site_id: Optional[str], fps_demand: dict[str, Any]
) -> dict[str, Any]:
    return {
        "has_telemetry": False,
        "site_id": site_id,
        "derived_status": None,
        "received_at": None,
        "metrics": None,
        "fps_demand_total": int(fps_demand.get("fps_demand_total") or 0),
        "cameras_active_count": int(fps_demand.get("cameras_active_count") or 0),
    }


@jwt_required()
def get_camera_health_context(camera_id: str):  # type: ignore[no-untyped-def]
    """---
    tags: [cameras]
    summary: Telemetria do site da câmera para aviso health-aware de FPS
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: camera_id, type: string, required: true}
    responses:
      200: {description: Contexto de saúde (has_telemetry=false sem site/heartbeat)}
      404: {description: Câmera não encontrada}
    """
    try:
        tenant_id = get_tenant_id()

        camera_repo = _get_camera_repo()
        camera = camera_repo.get_by_id_and_tenant(camera_id, tenant_id)
        if not camera:
            return error("Câmera não encontrada", 404)

        site_id = camera.get("site_id")
        if not site_id:
            return success(_empty_context(None, {}))

        fps_demand = camera_repo.sum_fps_demand(str(site_id), tenant_id)

        hb = _get_heartbeat_repo().get_last_heartbeat_for_site(str(site_id), tenant_id)
        if hb is None:
            return success(_empty_context(str(site_id), fps_demand))

        derived_status = derive_site_health_status(
            hb.get("received_at"), hb.get("status")
        )

        return success({
            "has_telemetry": True,
            "site_id": str(site_id),
            "derived_status": derived_status,
            "received_at": str(hb["received_at"]) if hb.get("received_at") else None,
            "metrics": {
                "gpu_pct": _num(hb.get("gpu_pct")),
                "gpu_mem_pct": _num(hb.get("gpu_mem_pct")),
                "cpu_pct": _num(hb.get("cpu_pct")),
                "inference_fps": _num(hb.get("inference_fps")),
                "inference_latency_ms": _num(hb.get("inference_latency_ms")),
                "queue_depth": hb.get("queue_depth"),
                "cameras_online": hb.get("cameras_online"),
                "cameras_total": hb.get("cameras_total"),
                "gpu_temp_c": _num(hb.get("gpu_temp_c")),
                "decode_pct": _num(hb.get("decode_pct")),
            },
            "fps_demand_total": int(fps_demand.get("fps_demand_total") or 0),
            "cameras_active_count": int(fps_demand.get("cameras_active_count") or 0),
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_camera_health_context_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
