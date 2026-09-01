/**
 * CropClassifier — vazio honesto da fila de classificação (task B4).
 *
 * Causa medida no DEV: a fila (only_crops=True) exigia, ao mesmo tempo,
 * proposta de IA pendente E câmera ativa — das 8 câmeras is_active=false do
 * tenant RVB, 100% (159/159) dos recortes elegíveis pertenciam a elas (fix
 * real em frame_repository.py, fora deste arquivo). Este teste cobre a
 * OUTRA metade do contrato: mesmo com o backend corrigido, um filtro de
 * câmera qualquer pode legitimamente zerar a fila — e a tela nunca pode
 * voltar a mentir "nada para classificar" sem revelar QUAL filtro foi.
 * Mesmo padrão já usado na fila de Propostas (TrainingGallery.test.tsx,
 * daab1d8d).
 *
 * Rede e localStorage mockados no mesmo padrão de CropClassifierFiltro.test.tsx.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { CropClassifier } from '../../../components/annotation/CropClassifier'

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
const listCamerasMock = vi.fn()

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
  cameraService: { list: (...args: unknown[]) => listCamerasMock(...args) },
}))

const toastMock = { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }
vi.mock('../../../components/ui/Toast/useToast', () => ({
  useToast: () => toastMock,
}))

function routeGet(path: string): Promise<unknown> {
  if (path.startsWith('/modules/epi/classes')) {
    return Promise.resolve({ success: true, data: { classes: [] } })
  }
  if (path.startsWith('/training/coverage-matrix')) {
    return Promise.resolve({ success: true, data: { gaps: [] } })
  }
  if (path.startsWith('/training/images')) {
    return Promise.resolve({ success: true, data: { frames: [] } })
  }
  return Promise.resolve({ success: true, data: {} })
}

beforeEach(() => {
  vi.stubGlobal('localStorage', new MemoryStorage())
  getMock.mockReset().mockImplementation(routeGet)
  postMock.mockReset().mockResolvedValue({ success: true })
  listCamerasMock.mockReset().mockResolvedValue([
    { id: 'cam-1', name: 'Guarita', manufacturer: 'hikvision', host: '10.0.0.1', port: 554, channel: 1 },
  ])
})

describe('CropClassifier — vazio revela o filtro que esvaziou a fila', () => {
  it('câmera filtrada + fila vazia: mostra QUAL câmera e oferece "Limpar filtros"; limpar tira o filtro da próxima busca', async () => {
    render(<CropClassifier initialCameraId="cam-1" onOpenAdjust={vi.fn()} />)

    await screen.findByText('Nenhum recorte com estes filtros: Câmera: Guarita.')
    const limpar = screen.getByRole('button', { name: 'Limpar filtros' })

    getMock.mockClear()
    fireEvent.click(limpar)

    await waitFor(() => {
      const chamada = getMock.mock.calls
        .map(c => String(c[0]))
        .find(u => u.startsWith('/training/images?'))
      expect(chamada).toBeDefined()
      expect(chamada).not.toContain('camera_ids')
    })
  })

  it('vazio sem NENHUM filtro ativo continua a mensagem neutra (nada para revelar, sem botão "Limpar filtros")', async () => {
    listCamerasMock.mockResolvedValue([])
    render(<CropClassifier onOpenAdjust={vi.fn()} />)

    await screen.findByText('Nenhum recorte não anotado disponível — recarregue para buscar mais.')
    expect(screen.queryByRole('button', { name: 'Limpar filtros' })).toBeNull()
  })

  // RODADA 3 (veredito do cético, QUEBRA 3): metade "classe" do mesmo
  // contrato acima nunca tinha teste de comportamento — uma mutação que
  // fazia tipoFilterLabel voltar sempre `null` E clearFilters parar de
  // limpar tiposSel passava a suíte inteira (1249/1249) em silêncio. Este
  // teste é o gabarito dessa mutação: precisa reprovar se qualquer uma das
  // duas quebrar de novo.
  it('filtro de CLASSE + fila vazia: mostra QUAL classe e oferece "Limpar filtros"; limpar tira o filtro (proposal_classes) da próxima busca E desmarca de volta', async () => {
    render(<CropClassifier onOpenAdjust={vi.fn()} />)

    await screen.findByText('Nenhum recorte não anotado disponível — recarregue para buscar mais.')

    const mascara = screen.getByRole('checkbox', { name: /Máscara/ }) as HTMLInputElement
    expect(mascara.checked).toBe(true) // conjunto vazio = tudo marcado (sem filtro)
    fireEvent.click(mascara) // desmarca só "Máscara" -> tiposSel vira {demais 4 tipos}

    // Mata a mutação "tipoFilterLabel sempre null": sem o rótulo "Classe: …"
    // este findByText nunca resolve e o teste estoura por timeout.
    await screen.findByText(/Nenhum recorte com estes filtros:.*Classe:/)
    expect(mascara.checked).toBe(false)

    const limpar = screen.getByRole('button', { name: 'Limpar filtros' })
    getMock.mockClear()
    fireEvent.click(limpar)

    // Mata a mutação "clearFilters não chama setTiposSel": sem isso o
    // checkbox continua desmarcado e o próximo /training/images continua
    // levando ?proposal_classes=.
    await waitFor(() => expect(mascara.checked).toBe(true))
    await waitFor(() => {
      const chamada = getMock.mock.calls
        .map(c => String(c[0]))
        .find(u => u.startsWith('/training/images?'))
      expect(chamada).toBeDefined()
      expect(chamada).not.toContain('proposal_classes')
    })
  })
})
