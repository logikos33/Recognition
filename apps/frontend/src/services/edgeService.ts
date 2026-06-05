import { api } from './api'
import type { EdgeOverview, SiteHealth, Heartbeat, HeartbeatSummary } from '../types/edge'

type Envelope<T> = { status?: string; data?: T }

function unwrap<T>(res: Envelope<T> | T): T {
  const enveloped = res as Envelope<T>
  return enveloped?.data !== undefined ? enveloped.data : (res as T)
}

export const edgeService = {
  async getOverview(): Promise<EdgeOverview> {
    const res = await api.get<Envelope<EdgeOverview> | EdgeOverview>('/edge/overview')
    return unwrap(res)
  },

  async getSitesHealth(): Promise<SiteHealth[]> {
    const res = await api.get<Envelope<SiteHealth[]> | SiteHealth[]>('/edge/sites/health')
    const data = unwrap(res)
    return Array.isArray(data) ? data : []
  },

  async getSiteHeartbeats(siteId: string): Promise<Heartbeat[]> {
    const res = await api.get<Envelope<Heartbeat[]> | Heartbeat[]>(`/sites/${siteId}/heartbeats`)
    const data = unwrap(res)
    return Array.isArray(data) ? data : []
  },

  async getHeartbeatSummary(siteId: string): Promise<HeartbeatSummary> {
    const res = await api.get<Envelope<HeartbeatSummary> | HeartbeatSummary>(`/heartbeat-summary?site_id=${siteId}`)
    return unwrap(res)
  },
}
