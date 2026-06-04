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

    def get_last_heartbeat_per_site(self, tenant_id: str) -> list[dict[str, Any]]:
        """Último heartbeat por site do tenant (DISTINCT ON site_id).

        Retorna uma linha por site, mesmo que não haja heartbeat (LEFT JOIN).
        Colunas de heartbeat serão NULL para sites sem nenhum heartbeat.
        """
        return self._execute(
            """
            SELECT DISTINCT ON (s.id)
                s.id              AS site_id,
                s.name            AS site_name,
                s.deployment_mode,
                h.received_at,
                h.status          AS heartbeat_status,
                h.inference_fps,
                h.cameras_online,
                h.cameras_total,
                h.cpu_pct,
                h.gpu_pct,
                h.queue_depth,
                h.edge_version
            FROM public.edge_sites s
            LEFT JOIN public.edge_heartbeats h
                ON h.site_id = s.id AND h.tenant_id = %s
            WHERE s.tenant_id = %s
            ORDER BY s.id, h.received_at DESC NULLS LAST
            """,
            (tenant_id, tenant_id),
        )

    def list_heartbeats(
        self,
        tenant_id: str,
        site_id: str,
        limit: int = 100,
        before: str | None = None,
    ) -> list[dict[str, Any]]:
        """Série temporal de heartbeats de um site, paginada por cursor temporal.

        limit é clampado ao máximo de 500.
        before é um ISO timestamp exclusivo (cursor).
        """
        limit = min(max(limit, 1), 500)
        if before:
            return self._execute(
                """
                SELECT id, received_at, status, inference_fps, cameras_online,
                       cameras_total, cpu_pct, gpu_pct, queue_depth, edge_version
                FROM public.edge_heartbeats
                WHERE tenant_id = %s AND site_id = %s AND received_at < %s
                ORDER BY received_at DESC
                LIMIT %s
                """,
                (tenant_id, site_id, before, limit),
            )
        return self._execute(
            """
            SELECT id, received_at, status, inference_fps, cameras_online,
                   cameras_total, cpu_pct, gpu_pct, queue_depth, edge_version
            FROM public.edge_heartbeats
            WHERE tenant_id = %s AND site_id = %s
            ORDER BY received_at DESC
            LIMIT %s
            """,
            (tenant_id, site_id, limit),
        )
