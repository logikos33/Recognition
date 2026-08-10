/**
 * Testes Vitest/RTL — galeria → AnnotationStudio (estúdio de anotação).
 *
 * Substitui TrainingPageDirectFrame.test.tsx: o branch `img.video_id` do
 * anotador legado morreu — TODO clique fora do modo seleção abre o
 * AnnotationStudio com a lista CONGELADA da página filtrada atual.
 *
 * AnnotationStudio é mockado (pesado) capturando props via data-attributes —
 * mesmo padrão de TrainingPageNav.test.tsx.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { TrainingPage } from '../../pages/TrainingPage'
import type { AnnotationStudioProps } from '../../components/annotation/AnnotationStudio'

// ── Fixtures ──────────────────────────────────────────────────────────────────

const frameA = {
  id: 'frame-a',
  video_id: 'video-abc', // mesmo com vídeo pai, o clique abre o estúdio
  frame_number: 5,
  filename: 'f1.jpg',
  is_annotated: false,
  created_at: '2026-08-01T12:00:00Z',
  camera_id: 'cam-1',
  curation_status: 'active',
  provenance: null,
  annotation_count: 0,
}

const frameB = {
  id: 'frame-b',
  video_id: null,
  frame_number: 12,
  filename: 'f2.jpg',
  is_annotated: true,
  created_at: '2026-08-02T12:00:00Z',
  camera_id: 'cam-1',
  curation_status: 'active',
  provenance: 'humana',
  annotation_count: 3,
}

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock('../../services/api', () => ({
  getToken: () => 'test-token',
  api: {
    get: vi.fn((path: string) => {
      if (path.startsWith('/training/images/facets')) {
        return Promise.resolve({
          success: true,
          data: {
            cameras: [{ camera_id: 'cam-1', camera_name: 'Portaria', count: 2 }],
            status: { nao_anotado: 1, anotado: 1, duvida: 0, excluida: 0 },
          },
        })
      }
      if (path.startsWith('/training/images')) {
        return Promise.resolve({
          success: true,
          data: { frames: [frameA, frameB], total: 2, page: 1, page_size: 60, total_pages: 1 },
        })
      }
      if (path === '/training/models') {
        return Promise.resolve({ success: true, data: [] })
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
  useAuth: () => ({ modules: ['epi'], isSuperAdmin: false }),
}))

vi.mock('../../components/ui/Toast/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }),
}))

// Captura as props do estúdio em vez de renderizar o componente pesado real.
vi.mock('../../components/annotation/AnnotationStudio', () => ({
  AnnotationStudio: (props: AnnotationStudioProps) => (
    <div
      data-testid="annotation-studio"
      data-frame-count={props.frames.length}
      data-initial-index={props.initialIndex}
      data-frame-ids={props.frames.map(f => f.id).join(',')}
    />
  ),
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
      </Routes>
    </MemoryRouter>,
  )
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('TrainingPage — galeria abre o AnnotationStudio', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('clique simples num card abre o estúdio com a página congelada, começando naquele frame', async () => {
    renderTrainingPage()

    const img = await screen.findByAltText(frameB.filename)
    fireEvent.click(img)

    await waitFor(() => {
      expect(screen.getByTestId('annotation-studio')).toBeTruthy()
    })

    const el = screen.getByTestId('annotation-studio')
    // Lista congelada = resultado filtrado da página atual (2 frames)
    expect(el.getAttribute('data-frame-count')).toBe('2')
    expect(el.getAttribute('data-frame-ids')).toBe('frame-a,frame-b')
    // Começa no frame clicado (índice 1)
    expect(el.getAttribute('data-initial-index')).toBe('1')
  })

  it('frame COM video_id também abre o estúdio (branch legado morto)', async () => {
    renderTrainingPage()

    const img = await screen.findByAltText(frameA.filename)
    fireEvent.click(img)

    await waitFor(() => {
      expect(screen.getByTestId('annotation-studio')).toBeTruthy()
    })
    expect(screen.getByTestId('annotation-studio').getAttribute('data-initial-index')).toBe('0')
  })

  it('Ctrl+clique seleciona em vez de abrir; "Anotar em sequência" abre só a seleção', async () => {
    renderTrainingPage()

    const img = await screen.findByAltText(frameB.filename)
    fireEvent.click(img, { ctrlKey: true })

    // Barra de ação fixa aparece; estúdio NÃO abriu
    expect(screen.queryByTestId('annotation-studio')).toBeNull()
    const annotateBtn = await screen.findByText('Anotar em sequência (1)')
    fireEvent.click(annotateBtn)

    await waitFor(() => {
      expect(screen.getByTestId('annotation-studio')).toBeTruthy()
    })
    const el = screen.getByTestId('annotation-studio')
    expect(el.getAttribute('data-frame-count')).toBe('1')
    expect(el.getAttribute('data-frame-ids')).toBe('frame-b')
    expect(el.getAttribute('data-initial-index')).toBe('0')
  })
})
