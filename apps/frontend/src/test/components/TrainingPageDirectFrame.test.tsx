/**
 * Testes Vitest/RTL — task B1 (destravar anotação de frames NVR).
 *
 * Cobre:
 *   1. Clicar num frame da galeria SEM video_id (source='nvr'/'upload',
 *      migration 094) abre o AnnotationInterface em modo "frame direto"
 *      (props `frames` + `initialFrameId`, sem `videoId`).
 *   2. Clicar num frame COM video_id continua no caminho antigo intacto
 *      (prop `videoId`, sem `frames`/`initialFrameId`).
 *
 * AnnotationInterface é mockado (canvas pesado, já coberto em outro lugar)
 * capturando as props recebidas via data-attributes — mesmo padrão de
 * TrainingPageNav.test.tsx.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { TrainingPage } from '../../pages/TrainingPage'

// ── Fixtures ──────────────────────────────────────────────────────────────────

const frameWithVideo = {
  id: 'frame-vid-1',
  video_id: 'video-abc',
  frame_number: 5,
  filename: 'f1.jpg',
  is_annotated: false,
  created_at: '2026-08-01T12:00:00Z',
}

const frameNoVideo = {
  id: 'frame-nvr-1',
  video_id: null,
  frame_number: 12,
  filename: 'f2.jpg',
  is_annotated: false,
  created_at: '2026-08-02T12:00:00Z',
}

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock('../../services/api', () => ({
  getToken: () => 'test-token',
  api: {
    get: vi.fn((path: string) => {
      if (path.startsWith('/training/images')) {
        return Promise.resolve({
          success: true,
          data: {
            frames: [frameWithVideo, frameNoVideo],
            total: 2,
            page: 1,
            page_size: 24,
            total_pages: 1,
          },
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
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))

// Captura as props recebidas em vez de renderizar o componente pesado real.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
vi.mock('../../components/AnnotationInterface', () => ({
  default: (props: any) => (
    <div
      data-testid="annotation-interface"
      data-video-id={props.videoId ?? ''}
      data-frame-count={Array.isArray(props.frames) ? props.frames.length : -1}
      data-initial-frame-id={props.initialFrameId ?? ''}
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

describe('TrainingPage — abrir anotador para frame sem vídeo (task B1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('clicar em frame SEM video_id abre o anotador em modo "frame direto"', async () => {
    renderTrainingPage()

    const img = await screen.findByAltText(frameNoVideo.filename)
    fireEvent.click(img)

    await waitFor(() => {
      expect(screen.getByTestId('annotation-interface')).toBeTruthy()
    })

    const el = screen.getByTestId('annotation-interface')
    expect(el.getAttribute('data-video-id')).toBe('')
    expect(el.getAttribute('data-initial-frame-id')).toBe(frameNoVideo.id)
    // frames prop = galeria inteira já carregada (2 frames no fixture)
    expect(el.getAttribute('data-frame-count')).toBe('2')
  })

  it('clicar em frame COM video_id mantém o caminho antigo (prop videoId)', async () => {
    renderTrainingPage()

    const img = await screen.findByAltText(frameWithVideo.filename)
    fireEvent.click(img)

    await waitFor(() => {
      expect(screen.getByTestId('annotation-interface')).toBeTruthy()
    })

    const el = screen.getByTestId('annotation-interface')
    expect(el.getAttribute('data-video-id')).toBe(frameWithVideo.video_id)
    // Caminho antigo não passa frames/initialFrameId
    expect(el.getAttribute('data-frame-count')).toBe('-1')
    expect(el.getAttribute('data-initial-frame-id')).toBe('')
  })
})
