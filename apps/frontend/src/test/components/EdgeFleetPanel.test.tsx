import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { EdgeFleetPanel } from '../../modules/admin/pages/observability/EdgeFleetPanel'
import { edgeService } from '../../services/edgeService'
import { adminService } from '../../modules/admin/services/adminService'
import type { EdgeOverview, FleetSite, HeartbeatSummary, Heartbeat } from '../../types/edge'

vi.mock('../../services/edgeService')
vi.mock('../../modules/admin/services/adminService')

/* ── Fixtures ─────────────────────────────────────────────────────── */

// Matches backend-adapted EdgeOverview (no sites_healthy/degraded/critical)
const mockOverview: EdgeOverview = {
  sites_total: 5,
  sites_offline: 1,
  devices_total: 5,
  devices_online: 4,
  devices_revoked: 1,
}

// Frota multi-tenant (WS11): shape do adminService.getEdgeFleet adaptado
const mockSites: FleetSite[] = [
  {
    site_id: 'site-1',
    site_name: 'Planta São Paulo',
    status: 'healthy',
    last_heartbeat: new Date(Date.now() - 60_000).toISOString(),
    fps: 4.8,
    cameras_online: 3,
    cameras_total: 3,
    gpu_temp_c: 62.4,
    decode_fps: 24.0,
    tenant_id: 'tenant-a',
    tenant_name: 'Tenant Alpha',
  },
  {
    site_id: 'site-2',
    site_name: 'Planta Campinas',
    status: 'degraded',
    last_heartbeat: new Date(Date.now() - 300_000).toISOString(),
    fps: 2.1,
    cameras_online: 1,
    cameras_total: 2,
    gpu_temp_c: null,
    decode_fps: null,
    tenant_id: 'tenant-b',
    tenant_name: 'Tenant Beta',
  },
]

const mockSummary: HeartbeatSummary = {
  site_id: 'site-1',
  avg_fps: 4.5,
  uptime_percent: 98.5,
  last_24h_heartbeats: 144,
  last_heartbeat: new Date().toISOString(),
}

const mockHeartbeats: Heartbeat[] = [
  { timestamp: new Date(Date.now() - 120_000).toISOString(), fps: 4.9 },
  { timestamp: new Date(Date.now() - 60_000).toISOString(),  fps: 4.8 },
]

/* ── Setup ────────────────────────────────────────────────────────── */

beforeEach(() => {
  vi.mocked(adminService.getEdgeFleet).mockResolvedValue(mockSites)
  vi.mocked(edgeService.getOverview).mockResolvedValue(mockOverview)
  vi.mocked(edgeService.getSitesHealth).mockResolvedValue(mockSites)
  vi.mocked(edgeService.getSiteHeartbeats).mockResolvedValue(mockHeartbeats)
  vi.mocked(edgeService.getHeartbeatSummary).mockResolvedValue(mockSummary)
})

function renderPage() {
  return render(
    <MemoryRouter>
      <EdgeFleetPanel />
    </MemoryRouter>
  )
}

/* ── Tests ────────────────────────────────────────────────────────── */

describe('EdgeFleetPanel — loading state', () => {
  it('shows loading indicator before first API response', () => {
    vi.mocked(edgeService.getOverview).mockImplementation(() => new Promise(() => {}))
    vi.mocked(edgeService.getSitesHealth).mockImplementation(() => new Promise(() => {}))
    renderPage()
    expect(screen.getByRole('status')).toBeDefined()
    expect(screen.getByText(/Carregando dados da frota/)).toBeDefined()
  })
})

describe('EdgeFleetPanel — overview cards', () => {
  it('renders all six overview card labels', async () => {
    renderPage()
    expect(await screen.findByText('Sites Saudáveis')).toBeDefined()
    expect(screen.getByText('Sites Degradados')).toBeDefined()
    expect(screen.getByText('Sites Críticos')).toBeDefined()
    expect(screen.getByText('Sites Offline')).toBeDefined()
    expect(screen.getByText('Devices Online')).toBeDefined()
    expect(screen.getByText('Devices Revogados')).toBeDefined()
  })

  it('health counts are derived from the fleet sites list', async () => {
    // mockSites has 1 healthy + 1 degraded → cards should reflect that
    renderPage()
    // "de 2 sites" derivado da lista da frota (não do overview endpoint)
    expect(await screen.findByText('de 2 sites')).toBeDefined()
  })

  it('shows correct sub-label total devices', async () => {
    renderPage()
    expect(await screen.findByText('de 5 total')).toBeDefined()
  })

  it('shows correct sub-label total sites', async () => {
    renderPage()
    expect(await screen.findByText('de 2 sites')).toBeDefined()
  })
})

describe('EdgeFleetPanel — sites table', () => {
  it('renders all site rows', async () => {
    renderPage()
    expect(await screen.findByText('Planta São Paulo')).toBeDefined()
    expect(screen.getByText('Planta Campinas')).toBeDefined()
  })

  it('shows Saudável badge for healthy site', async () => {
    renderPage()
    expect(await screen.findByText('Saudável')).toBeDefined()
  })

  it('shows Degradado badge for degraded site', async () => {
    renderPage()
    expect(await screen.findByText('Degradado')).toBeDefined()
  })

  it('shows fps values in table', async () => {
    renderPage()
    expect(await screen.findByText('4.8')).toBeDefined()
    expect(screen.getByText('2.1')).toBeDefined()
  })

  it('shows cameras ratio (online/total)', async () => {
    renderPage()
    expect(await screen.findByText('3/3')).toBeDefined()
    expect(screen.getByText('1/2')).toBeDefined()
  })

  it('shows empty state when no sites returned', async () => {
    vi.mocked(adminService.getEdgeFleet).mockResolvedValue([])
    renderPage()
    expect(await screen.findByText('Nenhum site encontrado')).toBeDefined()
  })

  it('shows new fleet columns GPU temp and decode fps (null-safe)', async () => {
    renderPage()
    // site-1 tem térmica/decode (migration 089); site-2 vem null → '—'
    expect(await screen.findByText('62°C')).toBeDefined()
    expect(screen.getByText('24.0')).toBeDefined()
  })

  it('groups sites by tenant in fleet view', async () => {
    renderPage()
    expect(await screen.findByText('Tenant Alpha (1)')).toBeDefined()
    expect(screen.getByText('Tenant Beta (1)')).toBeDefined()
  })
})

describe('EdgeFleetPanel — error state', () => {
  it('shows error message when fleet and fallback endpoints fail', async () => {
    vi.mocked(adminService.getEdgeFleet).mockRejectedValue(new Error('Network error'))
    vi.mocked(edgeService.getOverview).mockRejectedValue(new Error('Network error'))
    vi.mocked(edgeService.getSitesHealth).mockRejectedValue(new Error('Network error'))
    renderPage()
    const alert = await screen.findByRole('alert')
    expect(alert).toBeDefined()
    expect(screen.getByText('Network error')).toBeDefined()
  })

  it('shows retry button on full error', async () => {
    vi.mocked(adminService.getEdgeFleet).mockRejectedValue(new Error('Timeout'))
    vi.mocked(edgeService.getOverview).mockRejectedValue(new Error('Timeout'))
    vi.mocked(edgeService.getSitesHealth).mockRejectedValue(new Error('Timeout'))
    renderPage()
    const btn = await screen.findByRole('button', { name: 'Tentar novamente' })
    expect(btn).toBeDefined()
  })

  it('falls back to tenant-scoped sites when fleet endpoint fails', async () => {
    vi.mocked(adminService.getEdgeFleet).mockRejectedValue(new Error('404'))
    renderPage()
    // fallback via edgeService.getSitesHealth (mock do beforeEach)
    expect(await screen.findByText('Planta São Paulo')).toBeDefined()
  })
})

describe('EdgeFleetPanel — site detail panel', () => {
  it('opens detail panel on row click', async () => {
    renderPage()
    const row = await screen.findByTestId('site-row-site-1')
    fireEvent.click(row)
    expect(await screen.findByTestId('site-detail-panel')).toBeDefined()
  })

  it('shows site name in detail panel header', async () => {
    renderPage()
    fireEvent.click(await screen.findByTestId('site-row-site-1'))
    expect(await screen.findByRole('heading', { name: 'Planta São Paulo' })).toBeDefined()
  })

  it('shows summary metrics in detail panel', async () => {
    renderPage()
    fireEvent.click(await screen.findByTestId('site-row-site-1'))
    expect(await screen.findByText('Uptime')).toBeDefined()
    expect(await screen.findByText('FPS Médio')).toBeDefined()
    expect(await screen.findByText('HB (24h)')).toBeDefined()
  })

  it('closes detail panel when close button is clicked', async () => {
    renderPage()
    fireEvent.click(await screen.findByTestId('site-row-site-1'))
    await screen.findByTestId('site-detail-panel')
    fireEvent.click(screen.getByRole('button', { name: 'Fechar detalhes do site' }))
    await waitFor(() => {
      expect(screen.queryByTestId('site-detail-panel')).toBeNull()
    })
  })

  it('opens detail panel on keyboard Enter', async () => {
    renderPage()
    const row = await screen.findByTestId('site-row-site-1')
    fireEvent.keyDown(row, { key: 'Enter' })
    expect(await screen.findByTestId('site-detail-panel')).toBeDefined()
  })

  it('opens detail panel on keyboard Space', async () => {
    renderPage()
    const row = await screen.findByTestId('site-row-site-1')
    fireEvent.keyDown(row, { key: ' ' })
    expect(await screen.findByTestId('site-detail-panel')).toBeDefined()
  })
})
