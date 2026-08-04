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
    # Térmica/decode (migration 091 — opcionais, agentes antigos seguem válidos)
    gpu_temp_c: Decimal | None = None
    decode_pct: Decimal | None = None
    status: HeartbeatStatus
    last_error: str | None = None
    edge_version: str | None = None
    # Térmica e decode (migration 089) — opcionais, agentes antigos não enviam
    gpu_temp_c: Decimal | None = None
    cpu_temp_c: Decimal | None = None
    decode_fps: Decimal | None = None
    dropped_frames: int | None = None
    # ADR-0058 (migration 108) — config_version do RECORDER_CHANNEL_MAP
    # efetivamente em uso no device (cache local alimentado por
    # GET /api/v1/edge/config/poll, ou "" quando veio do .env/fallback).
    # Opcional — agentes antigos não enviam.
    config_version_applied: str | None = None


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
    # Térmica/decode (migration 091 — opcionais para compat com registros antigos)
    gpu_temp_c: Decimal | None = None
    decode_pct: Decimal | None = None
    status: HeartbeatStatus | None
    last_error: str | None
    edge_version: str | None
    # Térmica e decode (migration 089) — opcionais
    gpu_temp_c: Decimal | None = None
    cpu_temp_c: Decimal | None = None
    decode_fps: Decimal | None = None
    dropped_frames: int | None = None
    # ADR-0058 (migration 108) — ver Heartbeat acima.
    config_version_applied: str | None = None
