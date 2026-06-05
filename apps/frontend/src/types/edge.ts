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
}

export interface Heartbeat {
  timestamp: string
  fps: number | null
  cpu_percent?: number | null
  mem_percent?: number | null
  cameras_online?: number | null
  status?: SiteStatus
}

export interface HeartbeatSummary {
  site_id: string
  avg_fps: number | null
  uptime_percent: number
  last_24h_heartbeats: number
  last_heartbeat: string | null
}
