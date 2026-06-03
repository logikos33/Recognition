"""Repository: EdgeHeartbeat — telemetria dos dispositivos edge."""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from recognition_shared.heartbeat import Heartbeat

from app.infrastructure.database.repositories.base import BaseRepository


class EdgeHeartbeatRepository(BaseRepository):
    """SQL para public.edge_heartbeats e public.device_tokens."""

    def get_device_by_device_id(self, device_id: str) -> dict[str, Any] | None:
        """Busca device_tokens pelo device_id para lookup de public_key_pem."""
        return self._execute_one(
            "SELECT id, tenant_id, site_id, device_id, public_key_pem, revoked "
            "FROM public.device_tokens "
            "WHERE device_id = %s",
            (device_id,),
        )

    def insert_heartbeat(
        self,
        tenant_id: UUID,
        site_id: UUID,
        device_id: str,
        hb: Heartbeat,
    ) -> dict[str, Any]:
        """Persiste heartbeat em public.edge_heartbeats, retorna id e received_at."""
        row = self._execute_mutation(
            """
            INSERT INTO public.edge_heartbeats (
                tenant_id, site_id, device_id,
                cpu_pct, mem_pct, gpu_pct, gpu_mem_pct, disk_pct,
                inference_fps, inference_latency_ms,
                cameras_online, cameras_total, queue_depth,
                upload_kbps, download_kbps,
                status, last_error, edge_version
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s
            ) RETURNING id, received_at
            """,
            (
                str(tenant_id),
                str(site_id),
                device_id,
                float(hb.cpu_pct) if hb.cpu_pct is not None else None,
                float(hb.mem_pct) if hb.mem_pct is not None else None,
                float(hb.gpu_pct) if hb.gpu_pct is not None else None,
                float(hb.gpu_mem_pct) if hb.gpu_mem_pct is not None else None,
                float(hb.disk_pct) if hb.disk_pct is not None else None,
                float(hb.inference_fps) if hb.inference_fps is not None else None,
                float(hb.inference_latency_ms) if hb.inference_latency_ms is not None else None,
                hb.cameras_online,
                hb.cameras_total,
                hb.queue_depth,
                float(hb.upload_kbps) if hb.upload_kbps is not None else None,
                float(hb.download_kbps) if hb.download_kbps is not None else None,
                hb.status.value,
                hb.last_error,
                hb.edge_version,
            ),
        )
        return row  # type: ignore[return-value]

    def update_last_seen(self, device_id: str, tenant_id: UUID) -> None:
        """Atualiza device_tokens.last_seen_at para o dispositivo."""
        self._execute_mutation_no_return(
            "UPDATE public.device_tokens SET last_seen_at = %s "
            "WHERE device_id = %s AND tenant_id = %s",
            (datetime.now(timezone.utc), device_id, str(tenant_id)),
        )
