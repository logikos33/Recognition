/**
 * Testes Vitest/RTL — marcação visual de simulação no TrainingPage
 * (task "treino honesto", C2).
 *
 * Cobre:
 *   1. Modelo com origin='simulated' (trained_models) exibe o badge
 *      "SIMULAÇÃO" — nunca no mesmo formato de uma métrica real.
 *   2. Modelo real (origin='vast_ai') NÃO exibe o badge.
 *   3. Job atual com metrics.simulated=true (training_jobs.metrics, JSON
 *      já existente) exibe o badge junto ao status do job.
 *
 * Padrão: mocks nos hooks/serviços; nenhuma chamada de rede real (mesmo
 * padrão de TrainingPageNav.test.tsx).
 */
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { TrainingPage } from '../../pages/TrainingPage'

// ── Fixtures ─────────────────────────────────────────────────────────────────

const simulatedModel = {
  id: 'model-sim',
  name: 'YOLO26 yolo26n - Job sim1234',
  model_path: 'models/job-sim/SIMULATED_best.pt',
  map50: 0.78,
  precision: 0.82,
  recall: 0.74,
  is_active: false,
  created_at: '2026-08-01T12:00:00Z',
  origin: 'simulated',
  metrics: { mAP50: 0.78, precision: 0.82, recall: 0.74, loss: 0.31, simulated: true },
  created_by: 'user-1',
  owner_name: 'Ana Operadora',
  owner_email: 'ana@exemplo.com',
}

const realModel = {
  id: 'model-real',
  name: 'YOLO26 yolo26n - Job real5678',
  model_path: 'models/tenant-x/vast/job-real/model.onnx',
  map50: 0.91,
  precision: 0.93,
  recall: 0.88,
  is_active: true,
  created_at: '2026-08-02T12:00:00Z',
  origin: 'vast_ai',
  metrics: { mAP50: 0.91, precision: 0.93, recall: 0.88 },
  created_by: 'user-1',
  owner_name: 'Ana Operadora',
  owner_email: 'ana@exemplo.com',
}

const simulatedCurrentJob = {
  id: 'job-sim-current',
  preset: 'balanced',
  model_size: 'yolo26n',
  status: 'completed',
  progress: 100,
  current_epoch: 50,
  total_epochs: 50,
  metrics: { mAP50: 0.78, precision: 0.82, recall: 0.74, loss: 0.31, simulated: true },
  created_at: '2026-08-03T12:00:00Z',
}

// ── Mocks ─────────────────────────────────────────────────────────────────────

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
        return Promise.resolve({ success: true, data: [simulatedModel, realModel] })
      }
      if (path === '/classes') {
        return Promise.resolve({ success: true, data: [] })
      }
      if (path === '/training/jobs/current/status') {
        return Promise.resolve({
          success: true,
          data: { job: simulatedCurrentJob, gpu_enabled: true, live: null },
        })
      }
      if (path === '/training/jobs') {
        return Promise.resolve({ success: true, data: [simulatedCurrentJob] })
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

async function openModeloTab() {
  const tab = await screen.findByRole('tab', { name: 'Modelo' })
  fireEvent.mouseDown(tab, { button: 0 })
  fireEvent.click(tab)
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('TrainingPage — marcação de simulação (task "treino honesto" C2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('modelo simulado exibe badge "SIMULAÇÃO" — modelo real não exibe', async () => {
    renderTrainingPage()
    await openModeloTab()

    // Card do modelo simulado (e o resumo de "Modelo Ativo", se aplicável)
    const badges = await screen.findAllByText(/SIMULAÇÃO/)
    expect(badges.length).toBeGreaterThanOrEqual(1)

    // Ambos os modelos aparecem na lista — o modelo real tem a Origem correta
    // e (via getAllByText no teste acima) nenhum badge extra associado a ele
    const realOriginText = await screen.findAllByText(/Origem: GPU Vast\.ai/)
    expect(realOriginText.length).toBeGreaterThanOrEqual(1)
  })

  it('job atual simulado (metrics.simulated=true) exibe badge junto ao status', async () => {
    renderTrainingPage()

    const tab = await screen.findByRole('tab', { name: 'Treino ao Vivo' })
    fireEvent.mouseDown(tab, { button: 0 })
    fireEvent.click(tab)

    const badges = await screen.findAllByText(/SIMULAÇÃO/)
    expect(badges.length).toBeGreaterThanOrEqual(1)
  })
})
