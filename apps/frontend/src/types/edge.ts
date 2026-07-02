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
  // Métricas que o backend já devolve em /edge/sites/health (WS10 — aditivo)
  cpu_pct?: number | null
  gpu_pct?: number | null
  gpu_mem_pct?: number | null
  queue_depth?: number | null
  gpu_temp_c?: number | null
  decode_pct?: number | null
  edge_version?: string | null
}

export interface Heartbeat {
  timestamp: string
  fps: number | null
  cpu_percent?: number | null
  mem_percent?: number | null
  cameras_online?: number | null
  status?: SiteStatus
  // Métricas que o backend já devolve no serializer (WS10 — aditivo)
  gpu_pct?: number | null
  queue_depth?: number | null
  gpu_temp_c?: number | null
  decode_pct?: number | null
}

export interface HeartbeatSummary {
  site_id: string
  avg_fps: number | null
  uptime_percent: number
  last_24h_heartbeats: number
  last_heartbeat: string | null
}

// ---------------------------------------------------------------------------
// WS10 — GET /api/cameras/<id>/health-context
// Telemetria real do site da câmera para o aviso health-aware de FPS.
// ---------------------------------------------------------------------------

export interface CameraHealthMetrics {
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

export interface CameraHealthContext {
  has_telemetry: boolean
  site_id: string | null
  derived_status: SiteStatus | null
  received_at: string | null
  metrics: CameraHealthMetrics | null
  fps_demand_total: number
  cameras_active_count: number
}
