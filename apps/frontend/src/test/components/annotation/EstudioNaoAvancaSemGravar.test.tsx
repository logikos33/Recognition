/**
 * O Estúdio não pode fingir que gravou (#788) nem apagar trabalho alheio (#801).
 *
 * #788 — as teclas F (dúvida), V (aprovar proposta) e X (rejeitar proposta)
 * chamavam o backend e avançavam o frame na MESMA volta, fora do `.then`. Com
 * 403 (o operador entra no Estúdio por `frames:annotate`, mas aprovar/rejeitar
 * proposta exige `training:write`) o frame andava igual: o anotador achava que
 * tinha classificado 40 frames e não tinha classificado nenhum.
 *
 * #801 — o save era replace-all cego. Agora o cliente ecoa a `version` que leu
 * e o servidor recusa (409) substituir o que ele não viu.
 *
 * A contagem "N de M" do cabeçalho é a prova de que o frame NÃO andou.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AnnotationStudio } from '../../../components/annotation/AnnotationStudio'
// Do módulo MOCKADO abaixo — o `instanceof ApiError` do componente só bate se
// o erro lançado aqui for da MESMA classe que ele importa.
import { ApiError } from '../../../services/api'

const getMock = vi.fn()
const postMock = vi.fn()

vi.mock('../../../services/api', () => ({
  getToken: () => 'test-token',
  api: {
    get: (...args: unknown[]) => getMock(...args),
    post: (...args: unknown[]) => postMock(...args),
  },
  // Definida DENTRO da fábrica: `vi.mock` é içado para o topo do arquivo e
  // não enxerga variável de módulo.
  ApiError: class ApiError extends Error {
    status: number
    constructor(message: string, status: number) {
      super(message)
      this.status = status
    }
  },
}))

const toastMock = { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }
vi.mock('../../../components/ui/Toast/useToast', () => ({ useToast: () => toastMock }))

vi.mock('../../../services/propagationService', () => ({
  propagationService: { listJobs: () => Promise.resolve([]) },
}))

const FRAMES = [
  { id: 'frame-1', filename: 'f1.jpg', url: null, camera_id: null, created_at: '2026-09-05T10:00:00Z' },
  { id: 'frame-2', filename: 'f2.jpg', url: null, camera_id: null, created_at: '2026-09-05T10:00:01Z' },
]

/** Uma caixa de proposta pendente no frame 1 — V/X só agem com proposta. */
const PROPOSTA = {
  id: 'ann-1', class_id: 0, class_name: 'helmet',
  x_center: 0.5, y_center: 0.5, width: 0.2, height: 0.2,
  // `source: 'ai'` é o que vira `isProposal` no `rawToBox` — sem isso V/X
  // são no-op silencioso e o teste mediria nada.
  source: 'ai', confidence: 0.8,
}

function montar() {
  return render(
    <AnnotationStudio frames={FRAMES as never} initialIndex={0} onExit={vi.fn()} />,
  )
}

// jsdom não implementa scrollIntoView (a fila lateral do estúdio chama).
Element.prototype.scrollIntoView = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  getMock.mockImplementation((path: string) => {
    if (path.includes('/frames/frame-1/annotations')) {
      return Promise.resolve({ success: true, annotations: [PROPOSTA], version: 'v-frame-1' })
    }
    if (path.includes('/annotations')) {
      return Promise.resolve({ success: true, annotations: [], version: 'v-frame-2' })
    }
    return Promise.resolve({ success: true, data: { classes: [] } })
  })
  postMock.mockResolvedValue({ success: true, saved: 0, version: 'v-nova' })
})

async function estudioPronto() {
  await waitFor(() => expect(screen.getByText(/1 de 2/)).toBeTruthy())
}

describe('#788 — tecla não avança o frame quando o backend recusa', () => {
  it('F (em dúvida) com 403 NÃO avança e diz que foi permissão', async () => {
    postMock.mockRejectedValue(new ApiError('Sem permissão', 403))
    montar()
    await estudioPronto()

    fireEvent.keyDown(window, { key: 'f' })

    await waitFor(() => expect(toastMock.error).toHaveBeenCalled())
    expect(screen.getByText(/1 de 2/)).toBeTruthy()
    const frase = String(toastMock.error.mock.calls[0][0])
    expect(frase).toContain('permite')
    expect(frase).not.toContain('403')
  })

  it('F com 200 avança normalmente', async () => {
    montar()
    await estudioPronto()

    fireEvent.keyDown(window, { key: 'f' })

    await waitFor(() => expect(screen.getByText(/2 de 2/)).toBeTruthy())
    expect(postMock).toHaveBeenCalledWith(
      '/training/frames/curation',
      expect.objectContaining({ frame_ids: ['frame-1'], status: 'duvida' }),
    )
  })

  it('V (aprovar proposta) com 403 NÃO avança', async () => {
    postMock.mockRejectedValue(new ApiError('Sem permissão', 403))
    montar()
    await estudioPronto()

    fireEvent.keyDown(window, { key: 'v' })

    await waitFor(() => expect(toastMock.error).toHaveBeenCalled())
    expect(screen.getByText(/1 de 2/)).toBeTruthy()
    expect(postMock).toHaveBeenCalledWith('/training/frames/frame-1/accept-suggestions')
  })

  it('V com 200 avança', async () => {
    montar()
    await estudioPronto()
    fireEvent.keyDown(window, { key: 'v' })
    await waitFor(() => expect(screen.getByText(/2 de 2/)).toBeTruthy())
  })

  it('X (rejeitar proposta) com 403 NÃO avança', async () => {
    postMock.mockRejectedValue(new ApiError('Sem permissão', 403))
    montar()
    await estudioPronto()

    fireEvent.keyDown(window, { key: 'x' })

    await waitFor(() => expect(toastMock.error).toHaveBeenCalled())
    expect(screen.getByText(/1 de 2/)).toBeTruthy()
  })

  it('X com 200 avança', async () => {
    montar()
    await estudioPronto()
    fireEvent.keyDown(window, { key: 'x' })
    await waitFor(() => expect(screen.getByText(/2 de 2/)).toBeTruthy())
  })
})

describe('#801 — o save carrega a versão que este navegador leu', () => {
  /** Copiar do frame anterior (C) é o caminho de teclado que suja o frame
   * sem depender de desenhar caixa no canvas. */
  async function sujarFrame2ComCopia() {
    montar()
    await estudioPronto()
    fireEvent.keyDown(window, { key: 'd' })          // vai pro frame 2
    await waitFor(() => expect(screen.getByText(/2 de 2/)).toBeTruthy())
    fireEvent.keyDown(window, { key: 'c' })          // copia a caixa do frame 1
  }

  function salvamentosDeAnotacao() {
    return postMock.mock.calls.filter(
      ([path]) => typeof path === 'string' && path.endsWith('/annotations'),
    )
  }

  it('POST de anotação leva a version do GET daquele frame', async () => {
    await sujarFrame2ComCopia()

    await waitFor(() => expect(salvamentosDeAnotacao().length).toBeGreaterThan(0), {
      timeout: 3000,
    })
    const [path, corpo] = salvamentosDeAnotacao()[0]
    expect(path).toBe('/training/frames/frame-2/annotations')
    expect((corpo as { version?: string }).version).toBe('v-frame-2')
  })

  it('409 avisa para recarregar e NÃO descarta as caixas locais', async () => {
    postMock.mockRejectedValue(
      new ApiError('Ana salvou anotações neste frame há 2 minutos.', 409),
    )
    await sujarFrame2ComCopia()

    await waitFor(
      () => {
        const avisos = toastMock.error.mock.calls.map(c => String(c[0]))
        expect(avisos.some(a => a.toLowerCase().includes('recarregue o frame'))).toBe(true)
      },
      { timeout: 3000 },
    )
    // A caixa copiada continua na tela — nada do trabalho do anotador some.
    expect(screen.getByText(/2 de 2/)).toBeTruthy()
  })
})
