import { api } from './api'
import type {
  EdgeOverview,
  SiteHealth,
  Heartbeat,
  HeartbeatSummary,
  EdgeSite,
  DeploymentMode,
  EdgeSiteStatus,
} from '../types/edge'

// ---------------------------------------------------------------------------
// Backend raw response types (C-04 — verified against services/api routes.py)
// edge_bp is registered at url_prefix='/api/v1/edge'; api.ts prepends '/api'
// → paths here must start with '/v1/edge/...'
// ---------------------------------------------------------------------------

interface BackendOverview {
  sites_total: number
  sites_por_status: Record<string, number>
  devices_total: number
  devices_online: number
  devices_revoked: number
  sites_offline: number
}

interface BackendSiteHealth {
  site_id: string
  name: string                    // backend uses 'name', not 'site_name'
  deployment_mode?: string
  derived_status: string          // backend uses 'derived_status', not 'status'
  last_heartbeat_at: string | null  // backend uses 'last_heartbeat_at'
  inference_fps: number | null    // backend uses 'inference_fps', not 'fps'
  cameras_online: number
  cameras_total: number
  cpu_pct?: number | null
  gpu_pct?: number | null
  queue_depth?: number | null
  edge_version?: string | null
  gpu_temp_c?: number | null      // migration 089
  decode_fps?: number | null      // migration 089
}

interface BackendHeartbeat {
  id?: string
  received_at: string | null      // backend uses 'received_at', not 'timestamp'
  status?: string | null
  inference_fps: number | null    // backend uses 'inference_fps', not 'fps'
  cameras_online?: number | null
  cameras_total?: number | null
  cpu_pct?: number | null         // backend uses 'cpu_pct', not 'cpu_percent'
  gpu_temp_c?: number | null      // migration 089
  decode_fps?: number | null      // migration 089
}

/** Casado com _serialize_site em services/api/app/api/v1/edge/routes.py. */
interface BackendEdgeSite {
  id: string
  tenant_id: string
  name: string
  description: string | null
  location: string | null
  deployment_mode: string
  status: string
  created_at: string | null
  created_by: string | null
}

interface BackendHeartbeatSummary {
  site_id: string
  heartbeat_count: number         // backend uses 'heartbeat_count', not 'last_24h_heartbeats'
  avg_inference_fps: number | null  // backend uses 'avg_inference_fps', not 'avg_fps'
  uptime_pct: number | null       // backend uses 'uptime_pct', not 'uptime_percent'
  last_received_at: string | null  // backend uses 'last_received_at', not 'last_heartbeat'
  max_inference_fps?: number | null
  avg_inference_latency_ms?: number | null
  last_status?: string | null
  derived_status?: string
  window_seconds?: number
}

// ---------------------------------------------------------------------------
// Adapters: backend response → frontend types
// ---------------------------------------------------------------------------

function adaptOverview(raw: BackendOverview): EdgeOverview {
  return {
    sites_total: raw.sites_total,
    sites_offline: raw.sites_offline,
    devices_total: raw.devices_total,
    devices_online: raw.devices_online,
    devices_revoked: raw.devices_revoked,
  }
}

function adaptSiteHealth(raw: BackendSiteHealth): SiteHealth {
  return {
    site_id: raw.site_id,
    site_name: raw.name,
    status: raw.derived_status as SiteHealth['status'],
    last_heartbeat: raw.last_heartbeat_at,
    fps: raw.inference_fps,
    cameras_online: raw.cameras_online,
    cameras_total: raw.cameras_total,
    gpu_temp_c: raw.gpu_temp_c ?? null,
    decode_fps: raw.decode_fps ?? null,
  }
}

function adaptHeartbeat(raw: BackendHeartbeat): Heartbeat {
  return {
    timestamp: raw.received_at ?? '',
    fps: raw.inference_fps,
    cpu_percent: raw.cpu_pct ?? null,
    cameras_online: raw.cameras_online ?? null,
    gpu_temp_c: raw.gpu_temp_c ?? null,
    decode_fps: raw.decode_fps ?? null,
  }
}

function adaptSummary(raw: BackendHeartbeatSummary, siteId: string): HeartbeatSummary {
  return {
    site_id: siteId,
    avg_fps: raw.avg_inference_fps,
    uptime_percent: raw.uptime_pct ?? 0,
    last_24h_heartbeats: raw.heartbeat_count,
    last_heartbeat: raw.last_received_at,
  }
}

function adaptEdgeSite(raw: BackendEdgeSite): EdgeSite {
  return {
    id: raw.id,
    tenant_id: raw.tenant_id,
    name: raw.name,
    description: raw.description,
    location: raw.location,
    deployment_mode: raw.deployment_mode as DeploymentMode,
    status: raw.status as EdgeSiteStatus,
    created_at: raw.created_at,
    created_by: raw.created_by,
  }
}

// ---------------------------------------------------------------------------
// edgeService
// ---------------------------------------------------------------------------

export const edgeService = {
  async getOverview(): Promise<EdgeOverview> {
    const res = await api.get<{ data: BackendOverview }>('/v1/edge/overview')
    return adaptOverview(res.data)
  },

  async getSitesHealth(): Promise<SiteHealth[]> {
    const res = await api.get<{ data: { sites: BackendSiteHealth[] } }>('/v1/edge/sites/health')
    return res.data.sites.map(adaptSiteHealth)
  },

  async getSiteHeartbeats(siteId: string): Promise<Heartbeat[]> {
    const res = await api.get<{ data: { heartbeats: BackendHeartbeat[] } }>(
      `/v1/edge/sites/${siteId}/heartbeats`
    )
    return res.data.heartbeats.map(adaptHeartbeat)
  },

  async getHeartbeatSummary(siteId: string): Promise<HeartbeatSummary> {
    const res = await api.get<{ data: BackendHeartbeatSummary }>(
      `/v1/edge/sites/${siteId}/heartbeat-summary`
    )
    return adaptSummary(res.data, siteId)
  },

  /** GET /v1/edge/sites — sites do tenant do JWT (admin/superadmin only, backend). */
  async listSites(): Promise<EdgeSite[]> {
    const res = await api.get<{ data: { sites: BackendEdgeSite[] } }>('/v1/edge/sites')
    return res.data.sites.map(adaptEdgeSite)
  },

  /**
   * PATCH /v1/edge/sites/:id — atualização parcial (aqui usada só para
   * deployment_mode, mas aceita name/location/status também).
   * Cross-tenant e role insuficiente já são tratados pelo backend (404/403) —
   * o caller deve propagar o erro (ver ApiError em services/api.ts).
   */
  async updateSite(
    siteId: string,
    updates: Partial<Pick<EdgeSite, 'name' | 'location' | 'status' | 'deployment_mode'>>
  ): Promise<EdgeSite> {
    const res = await api.patch<{ data: { site: BackendEdgeSite } }>(
      `/v1/edge/sites/${siteId}`,
      updates
    )
    return adaptEdgeSite(res.data.site)
  },
}
