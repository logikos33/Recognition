/**
 * Teste de componente — filtro por classe da aba Classificar (#516).
 *
 * O bloqueador do 1º draft: proposta de tipo ESCONDIDO pelo filtro virava
 * anotação humana ao apertar Enter (pré-seleção + payload iteravam EPI_TYPES
 * inteiro). Aqui o recorte tem proposta de máscara E de luvas, o filtro mostra
 * só máscara, e o POST de aprovação NÃO pode levar luvas — nem quando o
 * rascunho restaurado já trazia luvas decidido.
 *
 * Rede mockada no módulo `api` (mesmo padrão de TrainingPageStudioOpen.test).
 */
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { CropClassifier } from '../../../components/annotation/CropClassifier'

const STORAGE_KEY = 'epi_crop_classifier_session_v1'
const MASCARA_ID = 100003
const GLOVES_ID = 100012

const FRAME = {
  id: 'f1',
  url: null,
  filename: 'f1.jpg',
  camera_id: null,
  created_at: '2026-08-21T10:00:00Z',
}

const getMock = vi.fn()
const postMock = vi.fn()

// localStorage real é pouco confiável neste ambiente (mesmo motivo de
// tenantContextRenewal.test.ts) — Storage in-memory via vi.stubGlobal.
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

// Objeto ESTÁVEL: `toast` entra nas deps de loadQueue/loadClasses — um objeto
// novo por render refaria o fetch em loop e a tela nunca sairia do Skeleton.
const toastMock = { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }
vi.mock('../../../components/ui/Toast/useToast', () => ({
  useToast: () => toastMock,
}))

function routeGet(path: string): Promise<unknown> {
  if (path.startsWith('/modules/epi/classes')) {
    return Promise.resolve({
      success: true,
      data: {
        classes: [
          { class_id: MASCARA_ID, class_name: 'mascara' },
          { class_id: 100004, class_name: 'Sem mascara' },
          { class_id: GLOVES_ID, class_name: 'gloves' },
          { class_id: 100013, class_name: 'no_gloves' },
        ],
      },
    })
  }
  if (path.startsWith('/training/coverage-matrix')) {
    return Promise.resolve({ success: true, data: { gaps: [] } })
  }
  if (path.startsWith('/training/images')) {
    return Promise.resolve({ success: true, data: { frames: [FRAME] } })
  }
  if (path === '/training/frames/f1/annotations') {
    // Proposta do modelo para DOIS tipos: máscara (visível) e luvas (escondido).
    return Promise.resolve({
      success: true,
      annotations: [
        { id: 'pre-0', class_id: MASCARA_ID, class_name: 'mascara', x_center: 0.5, y_center: 0.5, width: 1, height: 1, source: 'ai' },
        { id: 'pre-1', class_id: GLOVES_ID, class_name: 'gloves', x_center: 0.5, y_center: 0.5, width: 1, height: 1, source: 'ai' },
      ],
    })
  }
  return Promise.resolve({ success: true, data: {} })
}

function persist(extra: Record<string, unknown>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ tiposSelecionados: ['mascara'], ...extra }))
}

/** Grupos de tipo renderizados no PAINEL (não as checkboxes do filtro, que
 * listam todos os tipos sempre). */
const tiposNoPainel = () =>
  Array.from(document.querySelectorAll('[data-type]')).map(el => el.getAttribute('data-type'))

async function aprovarComEnter() {
  // Catálogo + fila + anotações do frame carregados: a sugestão do tipo
  // VISÍVEL aparece (título do botão). Luvas não está na tela.
  await screen.findByTitle('Sugerido por proposta de IA pendente')
  // O título vem de `suggested` (useMemo, computado NO MESMO render). A
  // pré-seleção do veredito que o Enter grava vem de um useEffect SEPARADO,
  // que também depende de `suggested` mas só comita no PRÓXIMO passe de
  // efeitos. findByTitle só prova que o primeiro aconteceu — sob contenção de
  // CPU (fila de workers do vitest) o Enter pode disparar entre um commit e
  // outro, com `verdict` ainda vazio, e approve() sai sem payload (postMock
  // nunca chamado — issue #618, medido: 2/10 execuções da suíte completa sob
  // contenção real). act() força o React a esvaziar o efeito pendente antes
  // de seguir.
  await act(async () => {})
  expect(tiposNoPainel()).toEqual(['mascara'])

  fireEvent.keyDown(window, { key: 'Enter' })
  await waitFor(() => expect(postMock).toHaveBeenCalled())
  const [path, body] = postMock.mock.calls[0] as [string, { annotations: { class_id: number }[] }]
  expect(path).toBe('/training/frames/f1/annotations')
  return body.annotations.map(a => a.class_id)
}

describe('CropClassifier — filtro por classe (#516)', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', new MemoryStorage())
    getMock.mockReset().mockImplementation(routeGet)
    postMock.mockReset().mockResolvedValue({ success: true })
  })

  it('🔴 proposta de tipo ESCONDIDO não entra no payload de aprovação', async () => {
    persist({})
    render(<CropClassifier onOpenAdjust={() => {}} />)
    const ids = await aprovarComEnter()
    expect(ids).toEqual([MASCARA_ID])
    expect(ids).not.toContain(GLOVES_ID)
  })

  it('🔴 rascunho restaurado com tipo escondido já decidido também não vaza pro payload', async () => {
    persist({ currentDraft: { frameId: 'f1', verdict: { mascara: 'presente', luvas: 'presente' } } })
    render(<CropClassifier onOpenAdjust={() => {}} />)
    const ids = await aprovarComEnter()
    expect(ids).toEqual([MASCARA_ID])
  })

  it('a fila pede ao servidor só recorte com proposta das classes do filtro', async () => {
    persist({})
    render(<CropClassifier onOpenAdjust={() => {}} />)
    await waitFor(() => expect(tiposNoPainel()).toEqual(['mascara']))
    const url = getMock.mock.calls.map(c => String(c[0])).find(u => u.startsWith('/training/images?'))
    expect(url).toBeDefined()
    const proposalClasses = new URLSearchParams(url!.split('?')[1]).get('proposal_classes') ?? ''
    expect(proposalClasses.split(',')).toEqual(expect.arrayContaining(['mascara', 'Sem mascara']))
    expect(proposalClasses).not.toContain('gloves')
  })

  it('deep-link da matriz ADICIONA o tipo da classe ao filtro (luvas volta pra tela)', async () => {
    persist({})
    render(<CropClassifier initialClassId={GLOVES_ID} onOpenAdjust={() => {}} />)
    // Só depois de o catálogo resolver GLOVES_ID → tipo "luvas".
    await waitFor(() => expect(tiposNoPainel()).toEqual(['mascara', 'luvas']))
  })

  it('sem filtro (vazio) a fila não manda proposal_classes e todos os tipos aparecem', async () => {
    render(<CropClassifier onOpenAdjust={() => {}} />)
    await waitFor(() => expect(tiposNoPainel()).toHaveLength(5))
    const url = getMock.mock.calls.map(c => String(c[0])).find(u => u.startsWith('/training/images?'))
    expect(url).not.toContain('proposal_classes')
  })
})
