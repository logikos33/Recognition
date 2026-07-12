/**
 * Contract tests: verify edgeService correctly transforms backend response shapes
 * into frontend types. Mocks api.get at the HTTP boundary so these tests prove
 * the transformation layer works regardless of UI.
 *
 * Backend field names verified against services/api/app/api/v1/edge/routes.py (C-04).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api } from '../../services/api'
import { edgeService } from '../../services/edgeService'

vi.mock('../../services/api')

beforeEach(() => {
  vi.resetAllMocks()
})

// ---------------------------------------------------------------------------
// getOverview
// ---------------------------------------------------------------------------

describe('edgeService.getOverview — contract', () => {
  it('maps backend sites_offline → EdgeOverview.sites_offline', async () => {
    vi.mocked(api.get).mockResolvedValue({
      status: 'success',
      data: {
        sites_total: 4,
        sites_por_status: { active: 3, inactive: 1 },
        devices_total: 4,
        devices_online: 3,
        devices_revoked: 1,
        sites_offline: 2,
      },
    })

    const result = await edgeService.getOverview()

    expect(result.sites_total).toBe(4)
    expect(result.sites_offline).toBe(2)
    expect(result.devices_total).toBe(4)
    expect(result.devices_online).toBe(3)
    expect(result.devices_revoked).toBe(1)
  })

  it('uses /v1/edge/overview path (api.ts prepends /api → /api/v1/edge/overview)', async () => {
    vi.mocked(api.get).mockResolvedValue({
      status: 'success',
      data: { sites_total: 0, sites_por_status: {}, devices_total: 0, devices_online: 0, devices_revoked: 0, sites_offline: 0 },
    })

    await edgeService.getOverview()

    expect(vi.mocked(api.get)).toHaveBeenCalledWith('/v1/edge/overview')
  })
})

// ---------------------------------------------------------------------------
// getSitesHealth
// ---------------------------------------------------------------------------

describe('edgeService.getSitesHealth — contract', () => {
  const backendSite = {
    site_id: 's1',
    name: 'Factory Floor',           // backend: 'name'
    deployment_mode: 'standalone',
    derived_status: 'healthy',        // backend: 'derived_status'
    last_heartbeat_at: '2026-01-01T10:00:00Z',  // backend: 'last_heartbeat_at'
    inference_fps: 5.0,               // backend: 'inference_fps'
    cameras_online: 2,
    cameras_total: 3,
    cpu_pct: 30.0,
  }

  beforeEach(() => {
    vi.mocked(api.get).mockResolvedValue({
      status: 'success',
      data: { sites: [backendSite] },
    })
  })

  it('maps backend name → site_name', async () => {
    const sites = await edgeService.getSitesHealth()
    expect(sites[0].site_name).toBe('Factory Floor')
  })

  it('maps backend derived_status → status', async () => {
    const sites = await edgeService.getSitesHealth()
    expect(sites[0].status).toBe('healthy')
  })

  it('maps backend last_heartbeat_at → last_heartbeat', async () => {
    const sites = await edgeService.getSitesHealth()
    expect(sites[0].last_heartbeat).toBe('2026-01-01T10:00:00Z')
  })

  it('maps backend inference_fps → fps', async () => {
    const sites = await edgeService.getSitesHealth()
    expect(sites[0].fps).toBe(5.0)
  })

  it('unwraps nested sites array from data.sites', async () => {
    const sites = await edgeService.getSitesHealth()
    expect(Array.isArray(sites)).toBe(true)
    expect(sites).toHaveLength(1)
  })

  it('uses /v1/edge/sites/health path', async () => {
    await edgeService.getSitesHealth()
    expect(vi.mocked(api.get)).toHaveBeenCalledWith('/v1/edge/sites/health')
  })
})

// ---------------------------------------------------------------------------
// getSiteHeartbeats
// ---------------------------------------------------------------------------

describe('edgeService.getSiteHeartbeats — contract', () => {
  const backendHeartbeat = {
    id: 'hb-1',
    received_at: '2026-01-01T10:00:00Z',  // backend: 'received_at'
    inference_fps: 4.8,                     // backend: 'inference_fps'
    cpu_pct: 25.0,                          // backend: 'cpu_pct'
    cameras_online: 2,
  }

  beforeEach(() => {
    vi.mocked(api.get).mockResolvedValue({
      status: 'success',
      data: { heartbeats: [backendHeartbeat] },
    })
  })

  it('maps backend received_at → timestamp', async () => {
    const hb = await edgeService.getSiteHeartbeats('s1')
    expect(hb[0].timestamp).toBe('2026-01-01T10:00:00Z')
  })

  it('maps backend inference_fps → fps', async () => {
    const hb = await edgeService.getSiteHeartbeats('s1')
    expect(hb[0].fps).toBe(4.8)
  })

  it('maps backend cpu_pct → cpu_percent', async () => {
    const hb = await edgeService.getSiteHeartbeats('s1')
    expect(hb[0].cpu_percent).toBe(25.0)
  })

  it('unwraps nested heartbeats array from data.heartbeats', async () => {
    const hb = await edgeService.getSiteHeartbeats('s1')
    expect(Array.isArray(hb)).toBe(true)
    expect(hb).toHaveLength(1)
  })

  it('uses /v1/edge/sites/:id/heartbeats path', async () => {
    await edgeService.getSiteHeartbeats('site-42')
    expect(vi.mocked(api.get)).toHaveBeenCalledWith('/v1/edge/sites/site-42/heartbeats')
  })
})

// ---------------------------------------------------------------------------
// getHeartbeatSummary
// ---------------------------------------------------------------------------

describe('edgeService.getHeartbeatSummary — contract', () => {
  const backendSummary = {
    site_id: 's1',
    heartbeat_count: 144,             // backend: 'heartbeat_count'
    avg_inference_fps: 4.7,           // backend: 'avg_inference_fps'
    uptime_pct: 97.5,                 // backend: 'uptime_pct'
    last_received_at: '2026-01-01T10:00:00Z',  // backend: 'last_received_at'
    derived_status: 'healthy',
  }

  beforeEach(() => {
    vi.mocked(api.get).mockResolvedValue({
      status: 'success',
      data: backendSummary,
    })
  })

  it('maps backend heartbeat_count → last_24h_heartbeats', async () => {
    const s = await edgeService.getHeartbeatSummary('s1')
    expect(s.last_24h_heartbeats).toBe(144)
  })

  it('maps backend avg_inference_fps → avg_fps', async () => {
    const s = await edgeService.getHeartbeatSummary('s1')
    expect(s.avg_fps).toBe(4.7)
  })

  it('maps backend uptime_pct → uptime_percent', async () => {
    const s = await edgeService.getHeartbeatSummary('s1')
    expect(s.uptime_percent).toBe(97.5)
  })

  it('maps backend last_received_at → last_heartbeat', async () => {
    const s = await edgeService.getHeartbeatSummary('s1')
    expect(s.last_heartbeat).toBe('2026-01-01T10:00:00Z')
  })

  it('uses /v1/edge/sites/:id/heartbeat-summary path (path param, not query string)', async () => {
    await edgeService.getHeartbeatSummary('site-42')
    expect(vi.mocked(api.get)).toHaveBeenCalledWith('/v1/edge/sites/site-42/heartbeat-summary')
  })
})
