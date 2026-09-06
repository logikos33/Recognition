/**
 * Aba Classificar — o MESMO #801 do Estúdio, na rota irmã (veredito do cético).
 *
 * `CropClassifier.approve()` faz GET das anotações do recorte, monta
 * "preservadas + as minhas" e manda no MESMO endpoint replace-all
 * (`POST /training/frames/<id>/annotations`) que o Estúdio usa. A guarda de
 * versão nasceu opt-in no servidor: quem não manda `version` continua
 * sobrescrevendo em silêncio. O PR ligou o Estúdio e deixou esta aba de fora
 * — a aba que corre a ~3s/recorte, na fila que é a MESMA para os três
 * anotadores da RVB (issue #828), onde a colisão é mais provável, não menos.
 *
 * Medido: Ana classifica o recorte, Bruno (que abriu o mesmo recorte antes)
 * classifica em seguida — o POST de Bruno levava `existingAnnotations` VELHO
 * (vazio) e apagava a caixa da Ana, com 200 na cara dele.
 *
 * O que este arquivo prova:
 *   1. o POST de aprovação leva a `version` que o GET devolveu;
 *   2. no 409 a aba RELÊ e reenvia a UNIÃO — a caixa da Ana sobrevive e a de
 *      Bruno entra junto (aqui travar o usuário seria matar o fluxo: a
 *      intenção desta aba é aditiva);
 *   3. o replay pós-401 (`pendingApprovals` do localStorage, cujo ref de
 *      versão morreu com a página) relê ANTES de gravar, em vez de estampar
 *      um conjunto velho por cima do que está lá agora.
 *
 * Mutações que este arquivo mata (todas passam na suíte sem ele):
 *   · tirar `version` do corpo do POST de approve → caso 1 e 2;
 *   · trocar a releitura do 409 por um `throw` → caso 2 (a caixa da Ana some
 *     do conjunto reenviado ou nada é reenviado);
 *   · fazer o replay mandar `repaired.annotations` cru → caso 3.
 */
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { CropClassifier } from '../../../components/annotation/CropClassifier'
import { ApiError } from '../../../services/api'

const STORAGE_KEY = 'epi_crop_classifier_session_v1'
const MASCARA_ID = 100003
const SEM_MASCARA_ID = 100004

const FRAME = { id: 'f1', url: null, filename: 'f1.jpg', camera_id: null, created_at: '2026-09-05T10:00:00Z' }

/** A caixa que a ANA gravou neste recorte antes do Bruno apertar Enter. */
const CAIXA_DA_ANA = {
  id: 'ana-1', class_id: SEM_MASCARA_ID, class_name: 'Sem mascara', module_code: 'epi',
  x_center: 0.5, y_center: 0.5, width: 1, height: 1, source: 'manual',
}

class MemoryStorage implements Storage {
  private store = new Map<string, string>()
  get length(): number { return this.store.size }
  clear(): void { this.store.clear() }
  getItem(key: string): string | null { return this.store.get(key) ?? null }
  key(index: number): string | null { return Array.from(this.store.keys())[index] ?? null }
  removeItem(key: string): void { this.store.delete(key) }
  setItem(key: string, value: string): void { this.store.set(key, String(value)) }
}

const getMock = vi.fn()
const postMock = vi.fn()

// A classe vive DENTRO da fábrica (vi.mock é içado para o topo do arquivo:
// referenciar um binding de fora daqui estoura em runtime). O componente
// testa `err instanceof ApiError`, então a classe que o teste usa para
// construir o 409 precisa ser a MESMA — por isso ela é reimportada abaixo.
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
vi.mock('../../../components/ui/Toast/useToast', () => ({ useToast: () => toastMock }))

/** Estado do recorte no "servidor" — muda entre a leitura do Bruno e o save. */
let anotacoesDoServidor: Record<string, unknown>[] = []
let versaoDoServidor = 'v-inicial'

function routeGet(path: string): Promise<unknown> {
  if (path.startsWith('/modules/epi/classes')) {
    return Promise.resolve({
      success: true,
      data: {
        classes: [
          { class_id: MASCARA_ID, class_name: 'mascara' },
          { class_id: SEM_MASCARA_ID, class_name: 'Sem mascara' },
        ],
      },
    })
  }
  if (path.startsWith('/training/coverage-matrix')) return Promise.resolve({ success: true, data: { gaps: [] } })
  if (path.startsWith('/training/images')) return Promise.resolve({ success: true, data: { frames: [FRAME] } })
  if (path === '/training/frames/f1/annotations') {
    return Promise.resolve({ success: true, annotations: anotacoesDoServidor, version: versaoDoServidor })
  }
  return Promise.resolve({ success: true, data: {} })
}

type CorpoPost = { annotations: { class_id: number }[]; version?: string }
const corposDeF1 = () =>
  postMock.mock.calls
    .filter(c => String(c[0]) === '/training/frames/f1/annotations')
    .map(c => c[1] as CorpoPost)

beforeEach(() => {
  vi.stubGlobal('localStorage', new MemoryStorage())
  anotacoesDoServidor = []
  versaoDoServidor = 'v-inicial'
  getMock.mockReset().mockImplementation(routeGet)
  postMock.mockReset().mockResolvedValue({ success: true, version: 'v-nova' })
  toastMock.error.mockReset()
})

/** Marca "mascara" e aprova com Enter (mesma manobra de CropClassifierFiltro). */
async function aprovarComEnter() {
  await screen.findByTitle('Sugerido por proposta de IA pendente')
  await act(async () => {})
  fireEvent.keyDown(window, { key: 'Enter' })
  await waitFor(() => expect(corposDeF1().length).toBeGreaterThan(0))
}

/** O recorte tem proposta de IA pendente de máscara — é o que a pré-seleção
 *  do Enter usa. Some com ela e nada é aprovado. */
const PROPOSTA_IA = {
  id: 'pre-0', class_id: MASCARA_ID, class_name: 'mascara',
  x_center: 0.5, y_center: 0.5, width: 1, height: 1, source: 'ai',
}

describe('Classificar não apaga o trabalho do colega (#801, rota irmã)', () => {
  it('o POST de aprovação leva a version que o GET devolveu', async () => {
    anotacoesDoServidor = [PROPOSTA_IA]
    versaoDoServidor = 'v-que-o-bruno-leu'
    render(<CropClassifier onOpenAdjust={() => {}} />)
    await aprovarComEnter()

    // 🔴 Sem `version` no corpo, a guarda do servidor é opt-in: ela não roda,
    // e o replace-all volta a apagar em silêncio.
    expect(corposDeF1()[0].version).toBe('v-que-o-bruno-leu')
  })

  it('409: relê e reenvia a UNIÃO — a caixa da Ana sobrevive junto com a do Bruno', async () => {
    anotacoesDoServidor = [PROPOSTA_IA]
    versaoDoServidor = 'v-que-o-bruno-leu'
    // A Ana grava entre a leitura do Bruno e o Enter dele: o servidor recusa
    // o primeiro POST e passa a devolver a caixa dela.
    postMock.mockImplementationOnce(() => {
      anotacoesDoServidor = [PROPOSTA_IA, CAIXA_DA_ANA]
      versaoDoServidor = 'v-depois-da-ana'
      return Promise.reject(new ApiError('Ana Prado salvou anotações neste frame agora há pouco.', 409))
    })

    render(<CropClassifier onOpenAdjust={() => {}} />)
    await aprovarComEnter()
    await waitFor(() => expect(corposDeF1().length).toBe(2))

    const reenvio = corposDeF1()[1]
    expect(reenvio.version).toBe('v-depois-da-ana')
    const ids = reenvio.annotations.map(a => a.class_id).sort()
    // 🔴 A caixa da Ana TEM de estar aqui: é ela que o replace-all apagava.
    expect(ids).toEqual([MASCARA_ID, SEM_MASCARA_ID].sort())
    // Sem duplicar: reler-e-somar não pode repetir caixa que já estava lá.
    expect(reenvio.annotations.length).toBe(2)
  })

  it('replay pós-401 relê antes de gravar, em vez de estampar o conjunto velho', async () => {
    // Sessão salva no localStorage por um Aprovar que o 401 interrompeu. O
    // ref de versão morreu com a página — é o caso em que "mandar sem
    // version" seria voltar ao bug.
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      pendingApprovals: [{
        frameId: 'f1',
        annotations: [{
          class_id: MASCARA_ID, class_name: 'mascara', module_code: 'epi',
          x_center: 0.5, y_center: 0.5, width: 1, height: 1,
        }],
      }],
    }))
    // Enquanto o Bruno estava fora, a Ana classificou o mesmo recorte.
    anotacoesDoServidor = [CAIXA_DA_ANA]
    versaoDoServidor = 'v-da-ana'

    render(<CropClassifier onOpenAdjust={() => {}} />)
    await waitFor(() => expect(corposDeF1().length).toBeGreaterThan(0))

    const corpo = corposDeF1()[0]
    // 🔴 Mandar `repaired.annotations` cru apagaria a caixa da Ana.
    expect(corpo.version).toBe('v-da-ana')
    expect(corpo.annotations.map(a => a.class_id).sort()).toEqual([MASCARA_ID, SEM_MASCARA_ID].sort())
  })
})
