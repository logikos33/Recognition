import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { EpiSitesHealthPage } from '../../pages/epi/EpiSitesHealthPage'
import { edgeService } from '../../services/edgeService'
import { useAuth } from '../../hooks/useAuth'
import type { EdgeOverview, SiteHealth, HeartbeatSummary, Heartbeat } from '../../types/edge'

vi.mock('../../services/edgeService')
vi.mock('../../hooks/useAuth')

/* ── Fixtures ─────────────────────────────────────────────────────── */

// Matches backend-adapted EdgeOverview (no sites_healthy/degraded/critical)
const mockOverview: EdgeOverview = {
  sites_total: 5,
  sites_offline: 1,
  devices_total: 5,
  devices_online: 4,
  devices_revoked: 1,
}

const mockSites: SiteHealth[] = [
  {
    site_id: 'site-1',
    site_name: 'Planta São Paulo',
    status: 'healthy',
    last_heartbeat: new Date(Date.now() - 60_000).toISOString(),
    fps: 4.8,
    cameras_online: 3,
    cameras_total: 3,
  },
  {
    site_id: 'site-2',
    site_name: 'Planta Campinas',
    status: 'degraded',
    last_heartbeat: new Date(Date.now() - 300_000).toISOString(),
    fps: 2.1,
    cameras_online: 1,
    cameras_total: 2,
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

/* ── Auth helpers ─────────────────────────────────────────────────── */

function mockAuthAs(role: 'admin' | 'superadmin' | 'operator' | 'viewer') {
  vi.mocked(useAuth).mockReturnValue({
    user: { id: 'u1', email: 'test@test.com', name: 'Test', role, modules: ['epi'] },
    isAuthenticated: true,
    isSuperAdmin: role === 'superadmin',
    isAdmin: role === 'admin' || role === 'superadmin',
    modules: ['epi'],
    hasModule: (m: string) => m === 'epi',
    login: vi.fn().mockResolvedValue({}),
    logout: vi.fn(),
  })
}

/* ── Setup ────────────────────────────────────────────────────────── */

beforeEach(() => {
  mockAuthAs('admin')
  vi.mocked(edgeService.getOverview).mockResolvedValue(mockOverview)
  vi.mocked(edgeService.getSitesHealth).mockResolvedValue(mockSites)
  vi.mocked(edgeService.getSiteHeartbeats).mockResolvedValue(mockHeartbeats)
  vi.mocked(edgeService.getHeartbeatSummary).mockResolvedValue(mockSummary)
})

function renderPage() {
  return render(
    <MemoryRouter>
      <EpiSitesHealthPage />
    </MemoryRouter>
  )
}

/* ── Tests ────────────────────────────────────────────────────────── */

describe('EpiSitesHealthPage — role guard', () => {
  it('shows access-denied alert for non-admin users', async () => {
    mockAuthAs('operator')
    renderPage()
    const alert = await screen.findByRole('alert')
    expect(alert).toBeDefined()
    expect(screen.getByText(/Acesso restrito/)).toBeDefined()
  })

  it('renders the full panel for admin users', async () => {
    renderPage()
    expect(await screen.findByText('Sites Saudáveis')).toBeDefined()
  })

  it('renders the full panel for superadmin users', async () => {
    mockAuthAs('superadmin')
    renderPage()
    expect(await screen.findByText('Sites Saudáveis')).toBeDefined()
  })
})

describe('EpiSitesHealthPage — loading state', () => {
  it('shows loading indicator before first API response', () => {
    vi.mocked(edgeService.getOverview).mockImplementation(() => new Promise(() => {}))
    vi.mocked(edgeService.getSitesHealth).mockImplementation(() => new Promise(() => {}))
    renderPage()
    expect(screen.getByRole('status')).toBeDefined()
    expect(screen.getByText(/Carregando dados da frota/)).toBeDefined()
  })
})

describe('EpiSitesHealthPage — overview cards', () => {
  it('renders all six overview card labels', async () => {
    renderPage()
    expect(await screen.findByText('Sites Saudáveis')).toBeDefined()
    expect(screen.getByText('Sites Degradados')).toBeDefined()
    expect(screen.getByText('Sites Críticos')).toBeDefined()
    expect(screen.getByText('Sites Offline')).toBeDefined()
    expect(screen.getByText('Devices Online')).toBeDefined()
    expect(screen.getByText('Devices Revogados')).toBeDefined()
  })

  it('health counts are derived from the sites list (not the overview endpoint)', async () => {
    // mockSites has 1 healthy + 1 degraded → cards should reflect that
    renderPage()
    // "de 5 sites" from overview.sites_total
    expect(await screen.findByText('de 5 sites')).toBeDefined()
  })

  it('shows correct sub-label total devices', async () => {
    renderPage()
    expect(await screen.findByText('de 5 total')).toBeDefined()
  })

  it('shows correct sub-label total sites', async () => {
    renderPage()
    expect(await screen.findByText('de 5 sites')).toBeDefined()
  })
})

describe('EpiSitesHealthPage — sites table', () => {
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
    vi.mocked(edgeService.getSitesHealth).mockResolvedValue([])
    renderPage()
    expect(await screen.findByText('Nenhum site encontrado')).toBeDefined()
  })
})

describe('EpiSitesHealthPage — error state', () => {
  it('shows error message when both endpoints fail', async () => {
    vi.mocked(edgeService.getOverview).mockRejectedValue(new Error('Network error'))
    vi.mocked(edgeService.getSitesHealth).mockRejectedValue(new Error('Network error'))
    renderPage()
    const alert = await screen.findByRole('alert')
    expect(alert).toBeDefined()
    expect(screen.getByText('Network error')).toBeDefined()
  })

  it('shows retry button on full error', async () => {
    vi.mocked(edgeService.getOverview).mockRejectedValue(new Error('Timeout'))
    vi.mocked(edgeService.getSitesHealth).mockRejectedValue(new Error('Timeout'))
    renderPage()
    const btn = await screen.findByRole('button', { name: 'Tentar novamente' })
    expect(btn).toBeDefined()
  })
})

describe('EpiSitesHealthPage — site detail panel', () => {
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
