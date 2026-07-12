/**
 * InvestigationPage — testes de regressão do WS4.
 *
 * Gate falha-antes/passa-depois: o teste (1) FALHA no código antigo, que
 * chamava api.get('/api/v1/events/...') gerando '/api/api/v1/...' (double-prefix
 * que caía no catch-all SPA e exibia 'Erro ao buscar eventos').
 */
import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { InvestigationPage } from '../InvestigationPage'
import { api } from '../../../services/api'

vi.mock('../../../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('../../../hooks/useModules', () => ({
  useModules: () => ({
    modules: [
      { id: '1', module_code: 'epi', enabled: true },
      { id: '2', module_code: 'fueling', enabled: true },
    ],
    loading: false,
    error: null,
    hasModule: () => true,
    getModule: () => undefined,
    refresh: () => {},
  }),
}))

vi.mock('../../../services/moduleService', () => ({
  moduleService: {
    getClasses: vi.fn().mockResolvedValue([]),
  },
}))

/* ── Helpers ──────────────────────────────────────────────────────── */

const emptySearch = {
  success: true,
  data: { events: [], total: 0, page: 1, per_page: 20, pages: 1 },
}

const emptyTimeline = {
  success: true,
  data: { timeline: [], bucket: 'hour' },
}

function mockApiGet(overrides?: {
  search?: unknown
  timeline?: unknown
}) {
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path.startsWith('/v1/events/search')) {
      return Promise.resolve(overrides?.search ?? emptySearch)
    }
    if (path.startsWith('/v1/events/timeline')) {
      return Promise.resolve(overrides?.timeline ?? emptyTimeline)
    }
    if (path.startsWith('/cameras')) {
      return Promise.resolve({ success: true, data: { cameras: [] } })
    }
    return Promise.reject(new Error(`unexpected path: ${path}`))
  })
}

function renderPage() {
  return render(
    <MemoryRouter>
      <InvestigationPage />
    </MemoryRouter>
  )
}

/* ── Testes ───────────────────────────────────────────────────────── */

describe('InvestigationPage — paths da API (regressão double-prefix)', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
  })

  it('chama /v1/events/search e /v1/events/timeline — NUNCA /api/v1/... (api.ts já prefixa /api)', async () => {
    mockApiGet()
    renderPage()

    await waitFor(() => {
      const calls = vi.mocked(api.get).mock.calls.map((c) => String(c[0]))
      expect(calls.some((p) => p.startsWith('/v1/events/search'))).toBe(true)
      expect(calls.some((p) => p.startsWith('/v1/events/timeline'))).toBe(true)
    })

    const calls = vi.mocked(api.get).mock.calls.map((c) => String(c[0]))
    for (const path of calls) {
      expect(path.startsWith('/api/')).toBe(false)
    }
  })

  it('envia from e to na chamada inicial da timeline (default últimos 7 dias)', async () => {
    mockApiGet()
    renderPage()

    await waitFor(() => {
      const timelineCall = vi
        .mocked(api.get)
        .mock.calls.map((c) => String(c[0]))
        .find((p) => p.startsWith('/v1/events/timeline'))
      expect(timelineCall).toBeDefined()
      expect(timelineCall).toContain('from=')
      expect(timelineCall).toContain('to=')
    })
  })
})

describe('InvestigationPage — contratos de resposta', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
  })

  it('renderiza timeline {timeline, bucket} sem crash e mostra contagem de períodos', async () => {
    mockApiGet({
      timeline: {
        success: true,
        data: {
          timeline: [
            { bucket: '2026-06-25T00:00:00', count: 4 },
            { bucket: '2026-06-26T00:00:00', count: 2 },
          ],
          bucket: 'hour',
        },
      },
    })
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('2 períodos')).toBeTruthy()
    })
  })

  it('renderiza violations [{class, confidence}] como badge com % — sem erro React child', async () => {
    mockApiGet({
      search: {
        success: true,
        data: {
          events: [
            {
              id: 'ev-1',
              camera_id: null,
              camera_name: 'Portaria',
              module_code: 'epi',
              confidence: 0.92,
              violations: [{ class: 'no_helmet', confidence: 0.92 }],
              evidence_key: null,
              created_at: '2026-06-30T10:00:00',
              frame_url: null,
              is_demo: false,
            },
          ],
          total: 1,
          page: 1,
          per_page: 20,
          pages: 1,
        },
      },
    })
    renderPage()

    await waitFor(() => {
      // Badge composto "classe · NN%" — distinto dos chips de filtro
      expect(screen.getByText('no_helmet · 92%')).toBeTruthy()
      expect(screen.getByText('92% confiança')).toBeTruthy()
    })
  })

  it("exibe badge 'Demo' quando o evento tem is_demo=true", async () => {
    mockApiGet({
      search: {
        success: true,
        data: {
          events: [
            {
              id: 'ev-demo',
              camera_id: null,
              camera_name: 'Pátio (demo)',
              module_code: 'epi',
              confidence: 0.8,
              violations: [{ class: 'no_vest', confidence: 0.8 }],
              evidence_key: null,
              created_at: '2026-06-29T14:30:00',
              frame_url: null,
              is_demo: true,
            },
          ],
          total: 1,
          page: 1,
          per_page: 20,
          pages: 1,
        },
      },
    })
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Demo')).toBeTruthy()
    })
  })

  it('mostra empty state quando não há eventos', async () => {
    mockApiGet()
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Nenhum evento encontrado')).toBeTruthy()
    })
  })
})
