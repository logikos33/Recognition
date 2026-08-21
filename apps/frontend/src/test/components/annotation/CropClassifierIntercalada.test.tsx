/**
 * Teste de componente — intercalação normais/propostas na aba Classificar (D5).
 *
 * Fila do servidor: n1, n2, p1, p2 (p* = pending_proposals_count > 0). Com
 * cadência 1/1 a tela tem de mostrar n1 → p1 → n2 → p2, o aviso "Enter
 * confirma" só nos recortes com proposta pré-selecionada e o nº do lote
 * derivado da fila (p1 = lote #1, p2 = lote #2). Desligada, a ordem do servidor.
 *
 * Rede mockada no módulo `api` (mesmo padrão de CropClassifierFiltro.test).
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { CropClassifier } from '../../../components/annotation/CropClassifier'

const STORAGE_KEY = 'epi_crop_classifier_session_v1'
const MASCARA_ID = 100003

const frame = (id: string, pending: number, classes?: string[]) => ({
  id,
  url: null,
  filename: `${id}.jpg`,
  camera_id: null,
  created_at: '2026-08-21T10:00:00Z',
  pending_proposals_count: pending,
  pending_proposal_classes: classes ?? (pending > 0 ? ['mascara'] : null),
})
const FRAMES = [frame('n1', 0), frame('n2', 0), frame('p1', 2), frame('p2', 1)]

const getMock = vi.fn()
const postMock = vi.fn()

class MemoryStorage implements Storage {
  private store = new Map<string, string>()
  get length(): number { return this.store.size }
  clear(): void { this.store.clear() }
  getItem(key: string): string | null { return this.store.get(key) ?? null }
  key(index: number): string | null { return Array.from(this.store.keys())[index] ?? null }
  removeItem(key: string): void { this.store.delete(key) }
  setItem(key: string, value: string): void { this.store.set(key, String(value)) }
}

vi.mock('../../../services/api', () => ({
  api: {
    get: (...args: unknown[]) => getMock(...args),
    post: (...args: unknown[]) => postMock(...args),
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(message: string, status: number) { super(message); this.status = status }
  },
}))

vi.mock('../../../services/cameraService', () => ({
  cameraService: { list: () => Promise.resolve([]) },
}))

const toastMock = { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }
vi.mock('../../../components/ui/Toast/useToast', () => ({
  useToast: () => toastMock,
}))

function routeGet(path: string): Promise<unknown> {
  if (path.startsWith('/modules/epi/classes')) {
    return Promise.resolve({
      success: true,
      data: { classes: [{ class_id: MASCARA_ID, class_name: 'mascara' }, { class_id: 100004, class_name: 'Sem mascara' }] },
    })
  }
  if (path.startsWith('/training/coverage-matrix')) {
    return Promise.resolve({ success: true, data: { gaps: [] } })
  }
  if (path.startsWith('/training/images')) {
    return Promise.resolve({ success: true, data: { frames: FRAMES } })
  }
  const m = /^\/training\/frames\/(\w+)\/annotations$/.exec(path)
  if (m) {
    const comProposta = m[1].startsWith('p')
    return Promise.resolve({
      success: true,
      annotations: comProposta
        ? [{ id: 'pre-0', class_id: MASCARA_ID, class_name: 'mascara', x_center: 0.5, y_center: 0.5, width: 1, height: 1, source: 'ai' }]
        : [],
    })
  }
  return Promise.resolve({ success: true, data: {} })
}

const AVISO = /proposta da IA pré-selecionada/
const pular = () => fireEvent.click(screen.getByRole('button', { name: 'Pular' }))

describe('CropClassifier — intercalação normais/propostas (D5)', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', new MemoryStorage())
    getMock.mockReset().mockImplementation(routeGet)
    postMock.mockReset().mockResolvedValue({ success: true })
  })

  it('cadência 1/1: n1 → p1 (lote #1) → n2 → p2 (lote #2); aviso só com proposta', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ cadencia: { normais: 1, propostas: 1 } }))
    render(<CropClassifier onOpenAdjust={() => {}} />)

    await screen.findByAltText('n1.jpg')
    expect(screen.queryByText(AVISO)).toBeNull()

    pular()
    await screen.findByAltText('p1.jpg')
    await screen.findByText(/proposta da IA pré-selecionada · lote #1/)

    pular()
    await screen.findByAltText('n2.jpg')
    await waitFor(() => expect(screen.queryByText(AVISO)).toBeNull())

    pular()
    await screen.findByAltText('p2.jpg')
    await screen.findByText(/lote #2/)
  })

  it('⛔ sem sessão persistida vem DESLIGADA (opt-in): ordem do servidor e seletor vazio', async () => {
    render(<CropClassifier onOpenAdjust={() => {}} />)
    await screen.findByAltText('n1.jpg')
    expect((screen.getByLabelText('cadência da intercalação') as HTMLSelectElement).value).toBe('')
    pular()
    await screen.findByAltText('n2.jpg')
    pular()
    await screen.findByAltText('p1.jpg')
  })

  it('cadência persistida inválida ({}/NaN) não trava a tela — cai em desligada', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ cadencia: { normais: NaN } }))
    render(<CropClassifier onOpenAdjust={() => {}} />)
    await screen.findByAltText('n1.jpg')
    expect((screen.getByLabelText('cadência da intercalação') as HTMLSelectElement).value).toBe('')
    pular()
    await screen.findByAltText('n2.jpg')
  }, 5000)

  it('proposta só de AUSÊNCIA não entra no braço "propostas" — é recorte normal', async () => {
    // a1 tem proposta pendente, mas de "Sem mascara": nada seria pré-selecionado,
    // então com 1/1 ele é NORMAL (a1 → p1 → n1 …), não o 1º do bloco de propostas.
    const comAusencia = [frame('a1', 1, ['sem mascara']), ...FRAMES]
    getMock.mockImplementation((path: string) =>
      path.startsWith('/training/images')
        ? Promise.resolve({ success: true, data: { frames: comAusencia } })
        : routeGet(path),
    )
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ cadencia: { normais: 1, propostas: 1 } }))
    render(<CropClassifier onOpenAdjust={() => {}} />)
    await screen.findByAltText('a1.jpg')
    expect(screen.queryByText(AVISO)).toBeNull()
    pular()
    await screen.findByAltText('p1.jpg')
    await screen.findByText(/lote #1/)
    pular()
    await screen.findByAltText('n1.jpg')
  })

  it('desligada: ordem do servidor (n1 → n2) e o seletor marca "desligado"', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ cadencia: null }))
    render(<CropClassifier onOpenAdjust={() => {}} />)

    await screen.findByAltText('n1.jpg')
    expect((screen.getByLabelText('cadência da intercalação') as HTMLSelectElement).value).toBe('')
    pular()
    await screen.findByAltText('n2.jpg')
  })

  it('trocar a cadência no seletor persiste na sessão (401-safety)', async () => {
    render(<CropClassifier onOpenAdjust={() => {}} />)
    await screen.findByAltText('n1.jpg')
    fireEvent.change(screen.getByLabelText('cadência da intercalação'), { target: { value: '10/5' } })
    await waitFor(() => {
      const salvo = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as { cadencia?: unknown }
      expect(salvo.cadencia).toEqual({ normais: 10, propostas: 5 })
    })
  })
})
