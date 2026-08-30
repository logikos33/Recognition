/**
 * Revisão Qualidade — o que este arquivo protege.
 *
 * Três coisas, e as três são armadilhas medidas no backend:
 *
 *  1. **A INVERSÃO DO FEEDBACK.** `rejected` = rejeitar o ALARME = peça
 *     CONFORME; `confirmed` = confirmar o NOK = peça NÃO CONFORME. Quem
 *     "arrumar" isso lendo o nome do status inverte o julgamento da fila
 *     inteira sem que nada quebre na tela — e o dado de treino sai espelhado.
 *     Por isso o status enviado é asserção, não detalhe.
 *
 *  2. **O RATE LIMIT DA EVIDÊNCIA** (60 URLs assinadas por usuário por HORA,
 *     compartilhadas com o clipe). O desenho mostra uma miniatura por linha;
 *     buscá-las queima o teto em poucos refreshes e devolve 429 justamente para
 *     quem está revisando. A fila NÃO pode pedir imagem — e é isso que o teste
 *     trava.
 *
 *  3. **AS LACUNAS COMO CONTROLE DESABILITADO.** Ponto de inspeção, estação,
 *     "foto inválida" e a classe da NC não têm rota. Se alguém devolver o
 *     clique a esses controles, eles passam a mentir. E se alguém apagá-los, a
 *     lacuna some do radar de quem decide o roadmap.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  RevisaoQualidade,
  formatarIdade,
  minutosDesde,
  rotuloDaClasse,
  type Inspecao,
} from './RevisaoQualidade'

// ── Dublês ──────────────────────────────────────────────────────────────────

const get = vi.fn()
const patch = vi.fn()
vi.mock('../../services/api', () => ({
  api: {
    get: (...a: unknown[]) => get(...a),
    patch: (...a: unknown[]) => patch(...a),
  },
}))

let permissoes = new Set(['verification:read', 'verification:write'])
let temModulo = true
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ can: (p: string) => permissoes.has(p), hasModule: () => temModulo }),
}))

const toastOk = vi.fn()
const toastErro = vi.fn()
vi.mock('../../components/ui/Toast/useToast', () => ({
  useToast: () => ({ success: toastOk, error: toastErro, warning: vi.fn(), info: vi.fn() }),
}))

// ── Dados: colunas reais de quality_inspections + camera_name do JOIN ───────

const AGORA = new Date('2026-08-29T12:00:00Z').getTime()

function inspecao(id: string, extra: Partial<Inspecao> = {}): Inspecao {
  return {
    id,
    camera_id: '0f6f2f1a-1111-4222-8333-444455556666',
    camera_name: 'Bancada A',
    result: 'nok',
    defect_class: 'defeito_visual',
    confidence: 0.78,
    evidence_r2_key: 'quality-frames/tenant/x.jpg',
    production_order: '2024-1186',
    product_type: 'ancora',
    shift: 'morning',
    feedback_status: 'pending',
    created_at: '2026-08-29T11:22:00Z', // 38 min
    ...extra,
  }
}

const A = inspecao('insp-a')
const B = inspecao('insp-b', {
  result: 'ok',
  defect_class: null,
  created_at: '2026-08-29T11:48:00Z', // 12 min
})

/** Envelope real: `success({inspections, total, page, per_page, pages})`. */
const listaDe = (itens: Inspecao[], total = itens.length) => ({
  success: true,
  data: { inspections: itens, total, page: 1, per_page: 100, pages: 1 },
})

const CLASSES = {
  data: {
    classes: [
      { class_id: '3', class_name: 'defeito_visual', display_name: 'Madeira exposta na alma' },
      { class_id: '4', class_name: 'defeito_bolha', display_name: 'Bolha no isolante' },
    ],
  },
}

const CAMERAS = {
  data: { cameras: [{ id: '0f6f2f1a-1111-4222-8333-444455556666', name: 'Bancada A' }] },
}

/** Roteia por caminho — a tela dispara 4 GETs diferentes. */
function servir(sobre: Record<string, unknown> = {}, lista = listaDe([A, B])) {
  get.mockImplementation((path: string) => {
    for (const [chave, valor] of Object.entries(sobre)) {
      if (path.includes(chave)) {
        return valor instanceof Error ? Promise.reject(valor) : Promise.resolve(valor)
      }
    }
    if (path.startsWith('/v1/quality/inspections?')) return Promise.resolve(lista)
    if (path.includes('/quality/cameras')) return Promise.resolve(CAMERAS)
    if (path.includes('/modules/quality/classes')) return Promise.resolve(CLASSES)
    if (path.includes('/evidence-url')) {
      return Promise.resolve({ data: { url: 'https://r2.exemplo/assinada.jpg', expires_in: 900 } })
    }
    if (path.includes('/reference-snapshots/')) return Promise.resolve({ data: [] })
    return Promise.resolve({ data: {} })
  })
}

const clicar = (el: HTMLElement) => fireEvent.click(el)
const tecla = (key: string) => fireEvent.keyDown(window, { key })

async function abrirDetalhe(nome = /Madeira exposta na alma/) {
  render(<RevisaoQualidade />)
  clicar(await screen.findByRole('button', { name: nome }))
  return screen.findByRole('button', { name: /^CONFORME/ })
}

beforeEach(() => {
  get.mockReset()
  patch.mockReset()
  toastOk.mockReset()
  toastErro.mockReset()
  permissoes = new Set(['verification:read', 'verification:write'])
  temModulo = true
  patch.mockResolvedValue({ success: true, data: { inspection_id: 'insp-a', feedback_status: 'x' } })
  vi.spyOn(Date, 'now').mockReturnValue(AGORA)
  servir()
})

// ── módulo desligado (nota do cético do flip) ───────────────────────────────

it('sem o módulo quality, a fila bloqueia e não chama rota nenhuma', () => {
  get.mockReset()
  temModulo = false
  render(<RevisaoQualidade />)
  expect(screen.getByText('Módulo não habilitado')).toBeTruthy()
  expect(get).not.toHaveBeenCalled()
})

// ── 1 · A inversão ──────────────────────────────────────────────────────────

describe('semântica do feedback (a inversão que morde)', () => {
  it('CONFORME manda `rejected` — rejeitar o ALARME, não a peça', async () => {
    const botao = await abrirDetalhe()
    clicar(botao)
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith('/v1/quality/inspections/insp-a/feedback', {
        status: 'rejected',
      }),
    )
  })

  it('NÃO CONFORME manda `confirmed` — confirmar o NOK apontado pela IA', async () => {
    await abrirDetalhe()
    clicar(screen.getByRole('button', { name: /NÃO CONFORME/ }))
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith('/v1/quality/inspections/insp-a/feedback', {
        status: 'confirmed',
      }),
    )
  })

  it('A e N no teclado carimbam o mesmo veredito dos botões', async () => {
    await abrirDetalhe()
    await act(async () => {
      tecla('a')
    })
    expect(patch).toHaveBeenCalledWith('/v1/quality/inspections/insp-a/feedback', {
      status: 'rejected',
    })
  })

  it('decidido sai da fila — o filtro é `pending`, reapresentar seria rejulgar', async () => {
    await abrirDetalhe()
    clicar(screen.getByRole('button', { name: /^CONFORME/ }))
    await waitFor(() => expect(screen.queryByRole('button', { name: /^CONFORME/ })).toBeNull())
    expect(screen.queryByText('Madeira exposta na alma')).toBeNull()
  })

  it('não lê `data.inspection` da resposta do PATCH — o backend devolve {inspection_id, feedback_status}', async () => {
    // Se a tela lesse `res.data.inspection`, isto zeraria o estado e a fila
    // sumiria inteira em vez de perder um item.
    await abrirDetalhe()
    clicar(screen.getByRole('button', { name: /^CONFORME/ }))
    expect(await screen.findByText(/apontados OK/)).toBeTruthy()
    expect(toastOk).toHaveBeenCalled()
  })
})

// ── 2 · Rate limit da evidência ─────────────────────────────────────────────

describe('rate limit de 60 URLs assinadas por hora', () => {
  it('a FILA não pede nenhuma URL de evidência', async () => {
    render(<RevisaoQualidade />)
    await screen.findByText('Madeira exposta na alma')
    expect(get.mock.calls.filter((c) => String(c[0]).includes('evidence-url'))).toEqual([])
  })

  it('a URL é pedida uma vez ao abrir, e o reabrir usa o cache', async () => {
    await abrirDetalhe()
    await waitFor(() => expect(screen.getByAltText(/Evidência/)).toBeTruthy())
    clicar(screen.getByRole('button', { name: /← Fila/ }))
    clicar(await screen.findByRole('button', { name: /Madeira exposta na alma/ }))
    await screen.findByRole('button', { name: /^CONFORME/ })
    const pedidos = get.mock.calls.filter((c) => String(c[0]).includes('evidence-url'))
    expect(pedidos).toHaveLength(1)
  })

  it('429 vira explicação na tela, não imagem quebrada', async () => {
    servir({ 'evidence-url': new Error('HTTP 429') })
    await abrirDetalhe()
    expect(await screen.findByText(/Limite de 60 URLs assinadas por hora/)).toBeTruthy()
  })
})

// ── 3 · Lacunas: controle no lugar, desabilitado, com motivo ────────────────

describe('lacunas do desenho sem rota', () => {
  it('ponto de inspeção e estação ficam desabilitados e dizem por quê', async () => {
    render(<RevisaoQualidade />)
    await screen.findByText('Madeira exposta na alma')
    const ponto = screen.getByLabelText('Ponto de inspeção')
    const estacao = screen.getByLabelText('Estação')
    expect((ponto as HTMLSelectElement).disabled).toBe(true)
    expect((estacao as HTMLSelectElement).disabled).toBe(true)
    expect(ponto.getAttribute('title')).toMatch(/validation_type/)
    expect(estacao.getAttribute('title')).toMatch(/nunca a preenche/)
  })

  it('"Foto inválida" fica desabilitado citando os status aceitos', async () => {
    await abrirDetalhe()
    const botao = screen.getByRole('button', { name: 'Foto inválida' })
    expect((botao as HTMLButtonElement).disabled).toBe(true)
    expect(botao.getAttribute('title')).toMatch(/retrain_requested/)
  })

  it('a faixa de classes da NC aparece, com as classes REAIS do tenant, desabilitada', async () => {
    await abrirDetalhe()
    const chip = screen.getByRole('button', { name: 'Bolha no isolante' })
    expect((chip as HTMLButtonElement).disabled).toBe(true)
    expect(chip.getAttribute('title')).toMatch(/feedback_notes/)
  })

  it('não promete que a decisão vira anotação de treino — porque não vira', async () => {
    // A frase do desenho ("vira anotação de treino automaticamente") é falsa:
    // o feedback só cria quality_retrain_suggestions em retrain_requested /
    // false_negative, e sugestão não é anotação.
    await abrirDetalhe()
    const texto = document.body.textContent ?? ''
    expect(texto).toMatch(/não.{0,3}vira anotação de treino/)
    expect(texto).not.toMatch(/anotação de treino automaticamente/)
  })

  it('o histórico da peça diz que piece_id não é gravado, em vez de inventar linhas', async () => {
    await abrirDetalhe()
    expect(screen.getByText(/piece_id/)).toBeTruthy()
  })

  it('o painel ESPECIFICADO explica que a rota devolve r2_key sem URL assinada', async () => {
    servir({
      'reference-snapshots/': {
        data: [{ id: 'snap-1', production_order: '2024-1186', captured_at: '2026-08-29T08:00:00Z' }],
      },
    })
    await abrirDetalhe()
    expect(await screen.findByText(/r2_key/)).toBeTruthy()
  })
})

// ── 4 · Nada inventado na tela ──────────────────────────────────────────────

describe('só dado servido', () => {
  it('nenhum UUID cru na tela — camera_id vira nome', async () => {
    render(<RevisaoQualidade />)
    await screen.findByText('Madeira exposta na alma')
    expect(document.body.textContent).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    )
    expect(screen.getAllByText(/Bancada A/).length).toBeGreaterThan(0)
  })

  it('chips contam ok/nok reais — não "suspeita de NC" e "dúvida", que não existem', async () => {
    render(<RevisaoQualidade />)
    expect(await screen.findByText(/1 apontados NOK/)).toBeTruthy()
    expect(screen.getByText(/1 apontados OK/)).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/dúvida/i)
  })

  it('classe sem correspondência no catálogo mostra o nome cru, não um rótulo bonito', () => {
    expect(rotuloDaClasse('defeito_visual', { defeito_visual: 'Madeira exposta' })).toBe(
      'Madeira exposta',
    )
    expect(rotuloDaClasse('classe_nova', {})).toBe('classe_nova')
    expect(rotuloDaClasse(null, {})).toBeNull()
  })

  it('a idade máxima só aparece quando a fila INTEIRA veio', async () => {
    servir({}, listaDe([A, B], 2))
    const { unmount } = render(<RevisaoQualidade />)
    expect(await screen.findByText(/mais antigo há/)).toBeTruthy()
    unmount()

    // Truncada: o mais antigo real está numa página que não foi lida.
    servir({}, listaDe([A, B], 240))
    render(<RevisaoQualidade />)
    await screen.findByText('Madeira exposta na alma')
    expect(screen.queryByText(/mais antigo há/)).toBeNull()
    expect(screen.getByText(/Mostrando os 2 mais recentes de 240/)).toBeTruthy()
  })

  it('idade sai de created_at, em minutos e horas', () => {
    expect(minutosDesde('2026-08-29T11:22:00Z', AGORA)).toBe(38)
    expect(minutosDesde(null)).toBeNull()
    expect(minutosDesde('nada disso')).toBeNull()
    expect(formatarIdade(38)).toBe('38 min')
    expect(formatarIdade(95)).toBe('1h35')
    expect(formatarIdade(null)).toBe('—')
  })
})

// ── 5 · Os quatro estados ───────────────────────────────────────────────────

describe('estados da tela', () => {
  it('sem permissão de leitura, diz qual chave falta e não chama a API', async () => {
    permissoes = new Set()
    render(<RevisaoQualidade />)
    expect(await screen.findByText('Sem permissão')).toBeTruthy()
    expect(get).not.toHaveBeenCalled()
  })

  it('erro mostra a ROTA e oferece nova tentativa', async () => {
    servir({ '/v1/quality/inspections?': new Error('HTTP 500') })
    render(<RevisaoQualidade />)
    expect(await screen.findByText(/GET \/api\/v1\/quality\/inspections/)).toBeTruthy()
    expect(screen.getByText(/HTTP 500/)).toBeTruthy()

    servir()
    clicar(screen.getByRole('button', { name: 'Tentar novamente' }))
    expect(await screen.findByText('Madeira exposta na alma')).toBeTruthy()
  })

  it('fila vazia é vazio honesto, não zero fingindo métrica', async () => {
    servir({}, listaDe([]))
    render(<RevisaoQualidade />)
    expect(await screen.findByText('Fila vazia')).toBeTruthy()
  })

  it('sem permissão de escrita, os vereditos ficam desabilitados dizendo a chave', async () => {
    permissoes = new Set(['verification:read'])
    await abrirDetalhe()
    const conforme = screen.getByRole('button', { name: /^CONFORME/ }) as HTMLButtonElement
    expect(conforme.disabled).toBe(true)
    expect(conforme.getAttribute('title')).toMatch(/verification:write/)
  })

  it('o filtro de turno usa os valores REAIS do backend', async () => {
    render(<RevisaoQualidade />)
    await screen.findByText('Madeira exposta na alma')
    fireEvent.change(screen.getByLabelText('Turno'), { target: { value: 'afternoon' } })
    await waitFor(() =>
      expect(
        get.mock.calls.some((c) => String(c[0]).includes('shift=afternoon')),
      ).toBe(true),
    )
  })
})
