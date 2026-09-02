/**
 * Testes Vitest/RTL para navegação e exibição de dono/origem do TrainingPage (WS5).
 *
 * Cobre:
 *   1. Botão "Configurar Classes" navega para /epi/training/classes via router
 *      (fix do bug P1: window.location.href='/module-classes' caía no catch-all)
 *   2. Card de modelo exibe "Origem: <label pt-BR>" e "Dono: <nome>"
 *
 * Padrão: mocks nos hooks/serviços; nenhuma chamada de rede real.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { TrainingPage } from '../../pages/TrainingPage'

// ── Mocks ─────────────────────────────────────────────────────────────────────

const modelFixture = {
  id: 'model-1',
  name: 'YOLO26 yolo26n - Job abc12345',
  model_path: 'models/job/best.pt',
  map50: 0.78,
  precision: 0.82,
  recall: 0.74,
  is_active: true,
  created_at: '2026-06-01T12:00:00Z',
  origin: 'simulated',
  created_by: 'user-1',
  owner_name: 'Ana Operadora',
  owner_email: 'ana@exemplo.com',
}

vi.mock('../../services/api', () => ({
  getToken: () => 'test-token',
  api: {
    get: vi.fn((path: string) => {
      if (path.startsWith('/training/images/facets')) {
        return Promise.resolve({
          success: true,
          data: { cameras: [], status: { nao_anotado: 0, anotado: 0, duvida: 0, excluida: 0 } },
        })
      }
      if (path.startsWith('/training/images')) {
        return Promise.resolve({
          success: true,
          data: { frames: [], total: 0, page: 1, page_size: 60, total_pages: 1 },
        })
      }
      if (path === '/training/models') {
        return Promise.resolve({ success: true, data: [modelFixture] })
      }
      if (path === '/classes') {
        return Promise.resolve({ success: true, data: [] })
      }
      if (path === '/training/jobs/current/status') {
        return Promise.resolve({
          success: true,
          data: { job: null, gpu_enabled: true, live: null },
        })
      }
      if (path === '/training/jobs') {
        return Promise.resolve({ success: true, data: [] })
      }
      return Promise.resolve({ success: true, data: null })
    }),
    post: vi.fn(() => Promise.resolve({ success: true })),
  },
}))

vi.mock('../../hooks/useTrainingSocket', () => ({
  useTrainingSocket: () => ({ jobs: {} }),
}))

vi.mock('../../hooks/useAuth', () => ({
  // can() precisa existir — TrainingPage lê training:approve pro gate de
  // disparo/cancelamento de treino (achado P0 do mutirão).
  useAuth: () => ({ modules: ['epi'], isSuperAdmin: false, can: () => true }),
}))

vi.mock('../../components/ui/Toast/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))

// Wizard tem canvases próprios — testado à parte
vi.mock('../../components/scenario/ModelScenarioWizard', () => ({
  ModelScenarioWizard: () => <div data-testid="scenario-wizard" />,
}))

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderTrainingPage() {
  return render(
    <MemoryRouter initialEntries={['/epi/training']}>
      <Routes>
        <Route path="/epi/training" element={<TrainingPage />} />
        <Route path="/epi/training/classes" element={<div data-testid="classes-page" />} />
      </Routes>
    </MemoryRouter>,
  )
}

/** Ativa a aba "Modelo" (Radix Tabs seleciona no mousedown). */
async function openModeloTab() {
  const tab = await screen.findByRole('tab', { name: 'Modelo' })
  fireEvent.mouseDown(tab, { button: 0 })
  fireEvent.click(tab)
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('TrainingPage — navegação Configurar Classes (WS5 M1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('clicar em "Configurar Classes" navega para /epi/training/classes', async () => {
    renderTrainingPage()
    await openModeloTab()

    const btn = await screen.findByRole('button', { name: /Configurar Classes/i })
    fireEvent.click(btn)

    await waitFor(() => {
      expect(screen.getByTestId('classes-page')).toBeTruthy()
    })
  })
})

describe('TrainingPage — dono e origem do modelo (WS5 M4)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('exibe Origem com label pt-BR e Dono com nome do usuário', async () => {
    renderTrainingPage()
    await openModeloTab()

    // 'simulated' → 'Treino simulado' (ativo + card = 2 ocorrências)
    const origens = await screen.findAllByText(/Origem: Treino simulado/)
    expect(origens.length).toBeGreaterThanOrEqual(1)

    const donos = await screen.findAllByText(/Dono: Ana Operadora/)
    expect(donos.length).toBeGreaterThanOrEqual(1)
  })

  it('botão "Configurar Cenário" abre o wizard do modelo', async () => {
    renderTrainingPage()
    await openModeloTab()

    const btn = await screen.findByRole('button', { name: /Configurar Cenário/i })
    fireEvent.click(btn)

    await waitFor(() => {
      expect(screen.getByTestId('scenario-wizard')).toBeTruthy()
    })
  })
})
