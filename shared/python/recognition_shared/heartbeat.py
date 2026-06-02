from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .enums import HeartbeatStatus


class Heartbeat(BaseModel):
    """Payload enviado pelo agente edge a cada ciclo de telemetria."""
    model_config = ConfigDict(from_attributes=True)

    device_id: str
    cpu_pct: Decimal | None = None
    mem_pct: Decimal | None = None
    gpu_pct: Decimal | None = None
    gpu_mem_pct: Decimal | None = None
    disk_pct: Decimal | None = None
    inference_fps: Decimal | None = None
    inference_latency_ms: Decimal | None = None
    cameras_online: int | None = None
    cameras_total: int | None = None
    queue_depth: int | None = None
    upload_kbps: Decimal | None = None
    download_kbps: Decimal | None = None
    status: HeartbeatStatus
    last_error: str | None = None
    edge_version: str | None = None


class HeartbeatRecord(BaseModel):
    """Registro persistido em public.edge_heartbeats."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: UUID
    site_id: UUID
    device_id: str
    received_at: datetime
    cpu_pct: Decimal | None
    mem_pct: Decimal | None
    gpu_pct: Decimal | None
    gpu_mem_pct: Decimal | None
    disk_pct: Decimal | None
    inference_fps: Decimal | None
    inference_latency_ms: Decimal | None
    cameras_online: int | None
    cameras_total: int | None
    queue_depth: int | None
    upload_kbps: Decimal | None
    download_kbps: Decimal | None
    status: HeartbeatStatus | None
    last_error: str | None
    edge_version: str | None
