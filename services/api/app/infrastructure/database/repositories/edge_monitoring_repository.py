"""Repository: EdgeMonitoring — leituras de frota para a página /monitoring.

Concentra o SQL do painel superadmin de observabilidade edge
(app/api/v1/monitoring/routes.py, migration 117).

ATENÇÃO — vários métodos aqui NÃO filtram por tenant. É o mesmo OVERRIDE
C-01 CONSCIENTE dos métodos `*_all_tenants` de edge_heartbeat_repository:
alimentam exclusivamente endpoints gateados por @require_superadmin_or_404
(visão de frota cross-tenant). Nunca reutilizar em rotas tenant-scoped.
"""
import json
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class EdgeMonitoringRepository(BaseRepository):
    """SQL para a visão de monitoramento da frota edge (superadmin)."""

    def get_site_any_tenant(self, site_id: str) -> dict[str, Any] | None:
        """Busca um site pelo id SEM filtro de tenant.

        OVERRIDE C-01 CONSCIENTE: não filtra tenant_id porque serve apenas
        às rotas superadmin de /api/v1/monitoring (gate 404 para qualquer
        outra role). O tenant_id retornado é usado pelas rotas para criar
        comandos e auditar no tenant correto do site.
        """
        return self._execute_one(
            """
            SELECT s.id, s.tenant_id, s.name, s.description, s.location,
                   s.deployment_mode, s.status,
                   t.name AS tenant_name, t.slug AS tenant_slug
            FROM public.edge_sites s
            JOIN public.tenants t ON t.id = s.tenant_id
            WHERE s.id = %s
            """,
            (site_id,),
        )

    def list_sites_overview(self) -> list[dict[str, Any]]:
        """Todos os sites + tenant + devices ativos + último heartbeat por device.

        OVERRIDE C-01 CONSCIENTE: visão de frota de TODOS os tenants —
        exclusivamente para o GET /api/v1/monitoring/sites (superadmin).

        Três queries compostas (sites, devices não-revogados, último
        heartbeat por device via DISTINCT ON) montadas em Python — evita um
        JOIN triplo com DISTINCT ON aninhado difícil de manter. Volume é o
        da frota (dezenas de sites), não o de telemetria.
        """
        sites = self._execute(
            """
            SELECT s.id, s.tenant_id, s.name, s.description, s.location,
                   s.deployment_mode, s.status, s.created_at,
                   t.name AS tenant_name, t.slug AS tenant_slug
            FROM public.edge_sites s
            JOIN public.tenants t ON t.id = s.tenant_id
            ORDER BY t.name, s.name
            """,
        )
        devices = self._execute(
            """
            SELECT site_id, device_id, device_name, last_seen_at, channel
            FROM public.device_tokens
            WHERE revoked = false
            ORDER BY site_id, device_id
            """,
        )
        heartbeats = self._execute(
            """
            SELECT DISTINCT ON (site_id, device_id)
                site_id, device_id, edge_version, received_at, status
            FROM public.edge_heartbeats
            ORDER BY site_id, device_id, received_at DESC
            """,
        )

        last_hb: dict[tuple[str, str], dict[str, Any]] = {
            (str(hb["site_id"]), hb["device_id"]): hb for hb in heartbeats
        }
        devices_by_site: dict[str, list[dict[str, Any]]] = {}
        for dev in devices:
            hb = last_hb.get((str(dev["site_id"]), dev["device_id"]))
            devices_by_site.setdefault(str(dev["site_id"]), []).append({
                "device_id": dev["device_id"],
                "device_name": dev.get("device_name"),
                "last_seen_at": dev.get("last_seen_at"),
                "channel": dev.get("channel"),
                "edge_version": hb.get("edge_version") if hb else None,
                "last_heartbeat_at": hb.get("received_at") if hb else None,
                "last_heartbeat_status": hb.get("status") if hb else None,
            })
        for site in sites:
            site["devices"] = devices_by_site.get(str(site["id"]), [])
        return sites

    def get_thresholds(self, site_id: str) -> dict[str, Any] | None:
        """Row de limiares do site (migration 117) ou None se nunca configurado."""
        return self._execute_one(
            """
            SELECT site_id, tenant_id, thresholds, updated_by, updated_at
            FROM public.edge_monitoring_thresholds
            WHERE site_id = %s
            """,
            (site_id,),
        )

    def upsert_thresholds(
        self,
        site_id: str,
        tenant_id: str,
        thresholds: dict[str, Any],
        updated_by: str | None,
    ) -> dict[str, Any] | None:
        """Cria/atualiza os limiares do site (uma linha por site)."""
        return self._execute_mutation(
            """
            INSERT INTO public.edge_monitoring_thresholds
                (site_id, tenant_id, thresholds, updated_by, updated_at)
            VALUES (%s, %s, %s::jsonb, %s, NOW())
            ON CONFLICT (site_id) DO UPDATE
                SET thresholds = EXCLUDED.thresholds,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = NOW()
            RETURNING site_id, tenant_id, thresholds, updated_by, updated_at
            """,
            (site_id, tenant_id, json.dumps(thresholds), updated_by),
        )

    def get_monitoring_command(self, command_id: str) -> dict[str, Any] | None:
        """Lê um comando de monitoramento (incluindo `result`, que o lado
        cloud nunca lia até aqui) pelo command_id.

        OVERRIDE C-01 CONSCIENTE: sem filtro de tenant — serve apenas às
        rotas superadmin de /api/v1/monitoring. O LIKE 'monitoring.%' garante
        que só comandos de monitoramento são visíveis por este caminho:
        qualquer outro command_type (ex.: update_camera_config) é invisível
        aqui e a rota responde 404.
        """
        return self._execute_one(
            """
            SELECT id, command_type, status, result, created_at, completed_at
            FROM public.edge_commands
            WHERE command_id = %s AND command_type LIKE 'monitoring.%%'
            """,
            (command_id,),
        )

    def last_detection_per_camera(
        self, site_id: str, window_minutes: int
    ) -> list[dict[str, Any]]:
        """Último evento 'detection' e contagem na janela, por câmera do site.

        camera_id é coluna top-level de public.edge_events (migration de
        edge_events — UUID solto, sem FK cross-schema), então não precisamos
        extrair nada do payload JSONB. Eventos sem camera_id (NULL) agrupam
        numa linha única com camera_id=None — reportados honestamente em vez
        de descartados.

        DISTINCT ON pega occurred_at/received_at do MESMO evento (o mais
        recente), então o lag calculado na rota é o lag real do último
        evento, não um MAX() de colunas de eventos diferentes.

        OVERRIDE C-01 CONSCIENTE: sem filtro de tenant — a rota superadmin
        valida antes que o site existe (get_site_any_tenant) e o site_id é
        PK, então não há como varrer eventos de outro site por aqui.
        """
        window_minutes = min(max(int(window_minutes), 1), 60 * 24 * 30)
        return self._execute(
            """
            SELECT DISTINCT ON (camera_id)
                camera_id,
                occurred_at  AS last_occurred_at,
                received_at  AS last_received_at,
                COUNT(*) OVER (PARTITION BY camera_id) AS detections_in_window
            FROM public.edge_events
            WHERE site_id = %s
              AND event_type = 'detection'
              AND received_at >= NOW() - (%s * INTERVAL '1 minute')
            ORDER BY camera_id, received_at DESC
            """,
            (site_id, window_minutes),
        )
