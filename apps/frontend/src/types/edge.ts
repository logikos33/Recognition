export type SiteStatus = 'healthy' | 'degraded' | 'critical' | 'offline'

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
