export type SiteStatus = 'healthy' | 'degraded' | 'critical' | 'offline'

/**
 * Modo de deployment persistido em public.edge_sites/public.tenants
 * (migrations 065/067, CHECK constraint — NÃO renomear sem migration nova).
 *
 * ADR-0046 usa os rótulos de produto 'edge' | 'dual' | 'cloud_only', mas o
 * valor gravado no banco continua sendo 'edge' | 'hybrid' | 'cloud'. O
 * mapeamento rótulo↔valor é só de apresentação — ver DEPLOYMENT_MODE_LABELS.
 */
export type DeploymentMode = 'cloud' | 'edge' | 'hybrid'

/** Rótulo de produto (ADR-0046) exibido na UI para cada valor persistido. */
export const DEPLOYMENT_MODE_LABELS: Record<DeploymentMode, string> = {
  edge: 'Edge',
  hybrid: 'Dual (edge + cloud)',
  cloud: 'Cloud-only',
}

export type EdgeSiteStatus = 'active' | 'inactive' | 'maintenance' | 'provisioning'

/** Site edge do tenant (GET/PATCH /api/v1/edge/sites) — casado com _serialize_site. */
export interface EdgeSite {
  id: string
  tenant_id: string
  name: string
  description: string | null
  location: string | null
  deployment_mode: DeploymentMode
  status: EdgeSiteStatus
  created_at: string | null
  created_by: string | null
}

export interface EdgeOverview {
  sites_total: number
  sites_offline: number    // health-derived (stale heartbeat) — from /edge/overview
  devices_total: number
  devices_online: number
  devices_revoked: number
}

export interface SiteHealth {
  site_id: string
  site_name: string
  status: SiteStatus
  last_heartbeat: string | null
  fps: number | null
  cameras_online: number
  cameras_total: number
  device_id?: string
  /** Térmica/decode (migration 089) — null quando o agente não envia */
  gpu_temp_c?: number | null
  decode_fps?: number | null
}

/** Site da visão de frota multi-tenant (GET /admin/observability/edge-fleet). */
export interface FleetSite extends SiteHealth {
  tenant_id: string
  tenant_name: string
  tenant_slug?: string
}

export interface Heartbeat {
  timestamp: string
  fps: number | null
  cpu_percent?: number | null
  mem_percent?: number | null
  cameras_online?: number | null
  status?: SiteStatus
  /** Térmica/decode (migration 089) */
  gpu_temp_c?: number | null
  decode_fps?: number | null
}

export interface HeartbeatSummary {
  site_id: string
  avg_fps: number | null
  uptime_percent: number
  last_24h_heartbeats: number
  last_heartbeat: string | null
}

/** Métricas brutas de telemetria do site (WS10 — GET /cameras/:id/health-context). */
export interface SiteTelemetryMetrics {
  gpu_pct: number | null
  gpu_mem_pct: number | null
  cpu_pct: number | null
  inference_fps: number | null
  inference_latency_ms: number | null
  queue_depth: number | null
  cameras_online: number | null
  cameras_total: number | null
  gpu_temp_c: number | null
  decode_pct: number | null
}

/** Contexto de saúde de uma câmera: telemetria real do site ou estimativa heurística. */
export interface CameraHealthContext {
  has_telemetry: boolean
  site_id: string | null
  derived_status: SiteStatus | null
  received_at: string | null
  metrics: SiteTelemetryMetrics | null
  fps_demand_total: number
  cameras_active_count: number
}
