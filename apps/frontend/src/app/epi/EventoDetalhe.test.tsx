/**
 * O que esta tela não pode perder na migração — e o que ela não pode afirmar.
 *
 * Os dois primeiros blocos são o contrato do `DELTA-PRE-MIGRACAO.md §2`: o
 * **badge de procedência** (item 2, ADR-0066) e o **motivo do veredito**
 * (item 5) chegaram na develop dias antes do handoff fechar, custaram caro, e
 * a migração é exatamente o momento em que somem sem ninguém notar — a tela
 * nova "fica linda" e o campo simplesmente não existe mais.
 *
 * O terceiro é a ADR-0067: violação nasce de julgamento POSITIVO de ausência.
 * `GET /api/alerts/:id` não devolve `event_kind`, então a tela não tem como
 * saber se o evento é violação ou conformidade — e por isso NÃO pode escrever
 * a palavra. Um teste, porque "o desenho manda" é justamente o argumento que
 * reintroduz a afirmação errada no próximo PR.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// `vi.hoisted`: o `vi.mock` é ICADO acima das constantes do módulo, então um
// `const` normal ainda não existe quando a fábrica roda.
const { get, post, patch, pode } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  pode: vi.fn(),
}))

vi.mock('../../services/api', async () => {
  // `ApiError` fica REAL: a tela distingue 404 (vazio) de qualquer outro
  // status (erro) por `instanceof`, e um dublê quebraria essa distinção.
  const real = await vi.importActual<Record<string, unknown>>('../../services/api')
  return { ...real, api: { get, post, put: vi.fn(), patch, delete: vi.fn() } }
})

// jsdom não implementa PointerEvent: sem isto o fireEvent cai num Event cru e
// clientX/clientY chegam undefined — a conversão daria NaN e o teste passaria
// a medir nada. Herdar de MouseEvent é o mínimo que preserva as coordenadas.
if (!('PointerEvent' in window)) {
  class PointerEventStub extends MouseEvent {
    pointerId: number
    constructor(tipo: string, init: PointerEventInit = {}) {
      super(tipo, init)
      this.pointerId = init.pointerId ?? 1
    }
  }
  Object.defineProperty(window, 'PointerEvent', { value: PointerEventStub, configurable: true })
}
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => ({ can: pode }) }))
vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<Record<string, unknown>>('react-router-dom')
  return { ...real, useParams: () => ({ id: 'e1' }) }
})

import { ApiError } from '../../services/api'
import { EventoDetalhe, caixaEmPorcento, procedenciaDeclarada } from './EventoDetalhe'

/** Formato real de `GET /api/alerts/:id` (RVB Isolantes — CAM-04 Expedição). */
const EVENTO = {
  id: 'e1e2e3e4-1111-2222-3333-444455556666',
  camera_id: 'c1',
  camera_name: 'CAM-04 Expedição',
  violations: [
    { class: 'no_helmet', confidence: 0.87, bbox: [100, 50, 200, 400] as [number, number, number, number], bbox_unidade: 'pixels_xywh_frame_original' },
  ],
  acknowledged: false,
  captured_at: '2026-08-25T14:32:08Z',
  created_at: '2026-08-25T14:32:10Z',   // 2s de atraso → contemporâneo
  evidence_url: 'https://r2.example/frame.jpg',
  verification_verdict: null as string | null,
  verified_at: null as string | null,
  correcao_ultima: null as { por: string | null; por_nome?: string | null; em: string | null } | null,
}

const montar = () => render(<MemoryRouter><EventoDetalhe /></MemoryRouter>)

/** A tela devolve o alerta e, no refetch pós-veredito, o mesmo alerta mudado. */
const responde = (alert: unknown) => get.mockResolvedValue({ data: { alert } })

/**
 * jsdom não baixa a imagem nem faz layout: forjamos naturalWidth/Height (frame
 * ORIGINAL) e o rect EXIBIDO. Fator 2 exato de propósito — é o que pega quem
 * confundir `getBoundingClientRect()` com `naturalWidth` na conversão.
 */
async function montarFrame(nat: [number, number], rect: [number, number]) {
  const img = (await screen.findByAltText('Frame da evidência')) as HTMLImageElement
  Object.defineProperty(img, 'naturalWidth', { value: nat[0], configurable: true })
  Object.defineProperty(img, 'naturalHeight', { value: nat[1], configurable: true })
  img.getBoundingClientRect = () => ({
    left: 0, top: 0, right: rect[0], bottom: rect[1],
    width: rect[0], height: rect[1], x: 0, y: 0, toJSON: () => ({}),
  }) as DOMRect
  fireEvent.load(img)
  return img
}

beforeEach(() => {
  get.mockReset()
  post.mockReset().mockResolvedValue({ data: {} })
  patch.mockReset().mockResolvedValue({
    data: {
      violations: [{ class: 'no_helmet', confidence: 0.87, bbox: [200, 100, 400, 200], bbox_unidade: 'pixels_xywh_frame_original' }],
      correcao_ultima: { por: 'u-1', em: '2026-08-24T10:00:00Z' },
    },
  })
  pode.mockReset().mockReturnValue(true)
  responde(EVENTO)
})

// ── item 2 do DELTA: badge de procedência (ADR-0066) ────────────────────────

describe('badge de procedência', () => {
  it('carimba "coleta retroativa" quando a gravação atrasou mais que o limiar', async () => {
    responde({ ...EVENTO, captured_at: '2026-08-25T14:32:08Z', created_at: '2026-08-25T15:10:00Z' })
    montar()
    expect(await screen.findByText(/coleta retroativa/i)).toBeTruthy()
  })

  it('NÃO carimba nada quando captura e gravação são contemporâneas', async () => {
    montar()
    // Ausência de badge = ausência de afirmação. Carimbar "AO VIVO" aqui
    // trocaria uma mentira por outra: `alerts.timestamp` ainda nasce com
    // DEFAULT NOW() igual ao created_at nas linhas antigas.
    await screen.findByText('CAM-04 Expedição')
    expect(screen.queryByText(/coleta retroativa/i)).toBeNull()
    expect(screen.queryByText(/ao vivo/i)).toBeNull()
  })

  it('não afirma nada quando falta uma das duas datas', async () => {
    responde({ ...EVENTO, created_at: null })
    montar()
    await screen.findByText('CAM-04 Expedição')
    expect(screen.queryByText(/coleta retroativa/i)).toBeNull()
  })
})

// ── procedência DECLARADA (v1, 05/09) ───────────────────────────────────────
// MEDIDO no DEV: 4.609 dos 5.174 eventos têm `violations[].origem =
// 'anotacao_humana'` — a caixa foi desenhada por PESSOA, no estúdio de
// anotação, e carregada em lote pelo `scripts/ops/eventos_acervo_rvb.py`. O
// badge temporal NUNCA acende nesses eventos (o script grava
// `created_at == timestamp`, atraso zero), então a tela ficava muda justamente
// onde tinha mais o que dizer — e o rótulo da caixa original ainda afirmava
// "ONDE A IA MARCOU" por cima de uma caixa humana. Duas mentiras, uma tela.

const V_HUMANA = {
  class: 'no_helmet',
  confidence: 1,
  bbox: [100, 50, 200, 400] as [number, number, number, number],
  bbox_unidade: 'pixels_xywh_frame_original',
  origem: 'anotacao_humana',
  anotacao_source: 'manual',
  lote: 'acervo-rvb-2026-09',
}
const V_MODELO = { ...V_HUMANA, origem: 'modelo_onnx', confidence: 0.87 }

describe('procedência declarada no dado', () => {
  it('caixa de PESSOA não pode ser anunciada como "onde a IA marcou"', async () => {
    responde({ ...EVENTO, violations: [V_HUMANA] })
    montar()
    await montarFrame([1920, 1080], [960, 540])
    fireEvent.click(screen.getByText('Corrigir caixa'))
    expect(await screen.findByTestId('caixa-correcao')).toBeTruthy()
    expect(screen.queryByText(/ONDE A IA MARCOU/i)).toBeNull()
    expect(screen.getByText(/ONDE A PESSOA MARCOU/i)).toBeTruthy()
  })

  it('caixa do MODELO segue dizendo que é da IA', async () => {
    responde({ ...EVENTO, violations: [V_MODELO] })
    montar()
    await montarFrame([1920, 1080], [960, 540])
    fireEvent.click(screen.getByText('Corrigir caixa'))
    expect(await screen.findByText(/ONDE A IA MARCOU/i)).toBeTruthy()
  })

  it('o badge lê a ORIGEM, não a diferença de tempo — evento humano sem atraso acende', async () => {
    // captura == gravação: o badge TEMPORAL (5 min) fica calado, e é
    // exatamente esse o caso dos 4.609 eventos semeados.
    responde({
      ...EVENTO,
      violations: [V_HUMANA],
      captured_at: '2026-08-25T14:32:08Z',
      created_at: '2026-08-25T14:32:08Z',
    })
    montar()
    const badge = await screen.findByTestId('procedencia')
    expect(badge.textContent).toMatch(/anotação humana/i)
    expect(badge.textContent).toMatch(/demonstração/i)
  })

  it('evento sem origem declarada não ganha afirmação nenhuma', async () => {
    montar()   // EVENTO padrão: violação sem `origem`, vinda do edge
    await screen.findByText('CAM-04 Expedição')
    expect(screen.queryByTestId('procedencia')).toBeNull()
  })

  it('a função é pura e diz a verdade sobre cada origem', () => {
    expect(procedenciaDeclarada([V_HUMANA])?.origem).toBe('humana')
    expect(procedenciaDeclarada([V_MODELO])?.origem).toBe('modelo')
    expect(procedenciaDeclarada([V_MODELO])?.rotulo).toMatch(/modelo/i)
    // sem `lote` não existe demonstração para anunciar
    const { lote: _lote, ...semLote } = V_HUMANA
    expect(procedenciaDeclarada([semLote])?.rotulo).not.toMatch(/demonstração/i)
    expect(procedenciaDeclarada([{ class: 'no_helmet', confidence: 0.9 }])).toBeNull()
    expect(procedenciaDeclarada([])).toBeNull()
  })
})

// ── evidência que expirou (v1, 05/09) ───────────────────────────────────────

describe('evidência indisponível', () => {
  it('imagem que não carrega vira aviso honesto, não tela em branco', async () => {
    // MEDIDO: a URL assinada do R2 vale 1h (`ttl=3600` em alerts/routes.py) e
    // depois devolve HTTP 403 ExpiredRequest. Sem `onError` a <img> falhava em
    // silêncio e o palco ficava vazio — o operador via um retângulo preto e
    // concluía que o evento não tinha evidência.
    montar()
    const img = await screen.findByAltText('Frame da evidência')
    fireEvent.error(img)
    expect(await screen.findByText(/não foi possível carregar a imagem/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /link|tentar/i })).toBeTruthy()
  })

  it('o botão do aviso refaz o GET — é ele que assina uma URL nova', async () => {
    montar()
    fireEvent.error(await screen.findByAltText('Frame da evidência'))
    const antes = get.mock.calls.length
    fireEvent.click(await screen.findByRole('button', { name: /link|tentar/i }))
    await waitFor(() => expect(get.mock.calls.length).toBeGreaterThan(antes))
    // e a imagem volta: o estado de falha não gruda no próximo carregamento
    expect(await screen.findByAltText('Frame da evidência')).toBeTruthy()
  })
})

// ── item 5 do DELTA: motivo do veredito ─────────────────────────────────────

describe('motivo do veredito', () => {
  it('o campo existe e vai ao backend como `reason`', async () => {
    montar()
    const campo = await screen.findByLabelText('Motivo do veredito')
    fireEvent.change(campo, { target: { value: 'a caixa pegou a luva do outro' } })
    fireEvent.click(screen.getByRole('button', { name: /descartar/i }))

    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/verification/e1/review', {
      verdict: 'reject',
      reason: 'a caixa pegou a luva do outro',
    })
  })

  it('motivo em branco NÃO manda `reason` — NULL de verdade, não string vazia', async () => {
    montar()
    fireEvent.click(await screen.findByRole('button', { name: /confirmar/i }))
    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/verification/e1/review', { verdict: 'approve' })
  })

  it('só espaços também não viram motivo', async () => {
    montar()
    fireEvent.change(await screen.findByLabelText('Motivo do veredito'), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: /confirmar/i }))
    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/verification/e1/review', { verdict: 'approve' })
  })

  it('o campo limpa depois do veredito, para o próximo não herdar o motivo alheio', async () => {
    montar()
    const campo = await screen.findByLabelText('Motivo do veredito') as HTMLInputElement
    fireEvent.change(campo, { target: { value: 'pessoa de costas' } })
    fireEvent.click(screen.getByRole('button', { name: /confirmar/i }))
    await waitFor(() => expect(campo.value).toBe(''))
  })

  it('falha do POST vira aviso na tela, não silêncio', async () => {
    post.mockRejectedValue(new Error('boom'))
    montar()
    fireEvent.click(await screen.findByRole('button', { name: /confirmar/i }))
    expect(await screen.findByRole('alert')).toBeTruthy()
  })
})

// ── ADR-0065 / 0067: o que a tela não pode afirmar ──────────────────────────

describe('veredito exibido', () => {
  it('sem veredito diz a palavra, não só a cor', async () => {
    montar()
    expect(await screen.findByText(/AGUARDA VEREDITO/)).toBeTruthy()
  })

  it('approve vira CONFIRMADO — SEM a palavra "violação" (ADR-0067)', async () => {
    responde({ ...EVENTO, verification_verdict: 'approve', verified_at: '2026-08-25T15:00:00Z' })
    montar()
    expect(await screen.findByText(/CONFIRMADO/)).toBeTruthy()
    // O desenho carimba "VIOLAÇÃO CONFIRMADA". `GET /alerts/:id` não devolve
    // `event_kind`, então a polaridade é desconhecida — e violação nunca nasce
    // do silêncio. Enquanto o campo não vier, a palavra não entra.
    expect(screen.queryByText(/VIOLA[ÇC][ÃA]O/i)).toBeNull()
  })

  it('reject vira DESCARTADO', async () => {
    responde({ ...EVENTO, verification_verdict: 'reject' })
    montar()
    expect(await screen.findByText(/DESCARTADO/)).toBeTruthy()
  })

  it('sem verification:write não mostra botão de veredito nenhum', async () => {
    pode.mockReturnValue(false)
    montar()
    await screen.findByText('CAM-04 Expedição')
    expect(screen.queryByRole('button', { name: /confirmar/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /descartar/i })).toBeNull()
    expect(pode).toHaveBeenCalledWith('verification:write')
  })
})

// ── evidência ───────────────────────────────────────────────────────────────

describe('caixa da evidência', () => {
  it('projeta pixels do frame original em % — o mapa da caixa', () => {
    expect(caixaEmPorcento([192, 108, 384, 216], 1920, 1080)).toEqual({
      left: '10%', top: '10%', width: '20%', height: '20%',
    })
  })

  // As duas travas abaixo são as negativas que a AlertDeepLink.test.tsx
  // original provava sobre `boxStyle` (arquivada em
  // archive/front-antigo-epi-lote1-2026-08-30) — a mesma matemática, só
  // renomeada para `caixaEmPorcento` (ver comentário na definição).
  it('não usa a convenção de centro: [x,y] é canto, não centro', () => {
    // Com [cx,cy,w,h] o left seria (100−40/2)/800 = 10% e o top (50−30/2)/600 = 5,8333%.
    const box = caixaEmPorcento([100, 50, 40, 30], 800, 600)
    expect(box.left).not.toBe('10%')
    expect(box.top).not.toBe('5.8333%')
  })

  it('não trata bbox como normalizado 0..1', () => {
    const comoSeNormalizado = caixaEmPorcento([0.5, 0.5, 0.2, 0.4], 800, 600)
    // A convenção 0..1 produziria exatamente isto — se voltar, este teste quebra.
    expect(comoSeNormalizado).not.toEqual({
      left: '40%', top: '30%', width: '20%', height: '40%',
    })
    // Números 0..1 lidos como pixels dão caixa degenerada (sub-pixel), não plausível.
    expect(parseFloat(comoSeNormalizado.width)).toBeLessThan(0.1)
    expect(parseFloat(comoSeNormalizado.height)).toBeLessThan(0.1)
  })

  it('não desenha caixa antes da imagem carregar', async () => {
    responde(EVENTO)
    montar()
    await screen.findByAltText('Frame da evidência')
    expect(screen.queryByTestId('caixa-violacao')).toBeNull()
  })

  it('bbox de unidade desconhecida não é desenhada, e a tela diz isso', async () => {
    responde({
      ...EVENTO,
      violations: [{ class: 'no_helmet', confidence: 0.9, bbox: [0.1, 0.1, 0.2, 0.2], bbox_unidade: 'normalizado_cxcywh' }],
    })
    montar()
    expect(await screen.findByText(/origem desconhecida/i)).toBeTruthy()
    expect(screen.queryAllByTestId('caixa-violacao')).toHaveLength(0)
  })

  it('evento sem coordenadas mostra o frame e avisa que não há marcação', async () => {
    responde({ ...EVENTO, violations: [{ class: 'no_helmet', confidence: 0.9 }] })
    montar()
    expect(await screen.findByText(/sem coordenadas gravadas/i)).toBeTruthy()
  })

  it('sem evidência a tela continua contando o acontecido', async () => {
    responde({ ...EVENTO, evidence_url: null })
    montar()
    expect(await screen.findByText(/sem imagem de evidência/i)).toBeTruthy()
    expect(screen.getByText('CAM-04 Expedição')).toBeTruthy()
  })
})

// ── os quatro estados da rota (handoff: carregado / loading / vazio / erro) ──

describe('estados', () => {
  it('404 é evento não encontrado — não é erro de carga', async () => {
    get.mockRejectedValue(new ApiError('Alerta não encontrado', 404))
    montar()
    expect(await screen.findByText('Evento não encontrado')).toBeTruthy()
    expect(screen.queryByText(/tentar novamente/i)).toBeNull()
  })

  it('500 é falha de carga, com retry que refaz o GET', async () => {
    get.mockRejectedValueOnce(new ApiError('Erro interno', 500))
    montar()
    // Em `erro` o evento também é null: com a ordem dos branches invertida a
    // tela dizia "Evento não encontrado" para uma falha de rede — mentira que
    // manda o operador embora em vez de oferecer o retry.
    expect(await screen.findByText('Falha ao carregar o evento')).toBeTruthy()
    expect(screen.queryByText('Evento não encontrado')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /tentar novamente/i }))
    responde(EVENTO)
    expect(await screen.findByText('CAM-04 Expedição')).toBeTruthy()
  })

  it('resposta sem alerta cai no vazio, não em tela quebrada', async () => {
    get.mockResolvedValue({ data: {} })
    montar()
    expect(await screen.findByText('Evento não encontrado')).toBeTruthy()
  })
})

// ── correção de caixa (migrada de AlertDetailRevisao.test.tsx — a tela ──────
// antiga vai ser demolida, esta cobertura não pode se perder junto).

describe('correção de caixa', () => {
  it('sem alerts:feedback não mostra o botão de correção', async () => {
    pode.mockImplementation((permissao: string) => permissao !== 'alerts:feedback')
    montar()
    await screen.findByText('CAM-04 Expedição')
    expect(screen.queryByText('Corrigir caixa')).toBeNull()
    expect(pode).toHaveBeenCalledWith('alerts:feedback')
  })

  it('arrasto grava bbox em PIXELS do frame ORIGINAL, não do frame exibido', async () => {
    montar()
    await montarFrame([1920, 1080], [960, 540])
    fireEvent.click(screen.getByText('Corrigir caixa'))

    const palco = screen.getByRole('group')
    fireEvent.pointerDown(palco, { clientX: 100, clientY: 50, pointerId: 1 })
    fireEvent.pointerMove(palco, { clientX: 300, clientY: 150, pointerId: 1 })
    fireEvent.pointerUp(palco, { clientX: 300, clientY: 150, pointerId: 1 })

    fireEvent.click(screen.getByText('Salvar caixa'))
    await waitFor(() => expect(patch).toHaveBeenCalled())
    // 100→200, 50→100, 300→300 vira largura 400, 150→150 vira altura 200:
    // fator 2 do rect exibido (960×540) para o natural (1920×1080). Gravar o
    // rect cru daria a caixa deslocada e pequena demais.
    expect(patch).toHaveBeenCalledWith('/alerts/e1/violations', {
      correcoes: [{ index: 0, bbox: [200, 100, 400, 200] }],
    })
  })

  it('mostra a caixa de correção (sólida, ciano) assim que o modo abre', async () => {
    montar()
    await montarFrame([1920, 1080], [960, 540])
    expect(screen.queryByTestId('caixa-correcao')).toBeNull()
    fireEvent.click(screen.getByText('Corrigir caixa'))
    expect(await screen.findByTestId('caixa-correcao')).toBeTruthy()
  })

  it('arrasto pequeno demais (clique acidental) NÃO degenera a caixa: rascunho volta à gravada', async () => {
    montar()
    await montarFrame([1920, 1080], [960, 540])
    fireEvent.click(screen.getByText('Corrigir caixa'))
    const palco = screen.getByRole('group')
    fireEvent.pointerDown(palco, { clientX: 100, clientY: 50, pointerId: 1 })
    fireEvent.pointerMove(palco, { clientX: 101, clientY: 50, pointerId: 1 })
    fireEvent.pointerUp(palco, { clientX: 101, clientY: 50, pointerId: 1 })
    fireEvent.click(screen.getByText('Salvar caixa'))
    await waitFor(() => expect(patch).toHaveBeenCalled())
    expect(patch).toHaveBeenCalledWith('/alerts/e1/violations', {
      correcoes: [{ index: 0, bbox: [100, 50, 200, 400] }],
    })
  })

  it('caminho de teclado: digitar coordenada em px grava o mesmo bbox', async () => {
    montar()
    await montarFrame([1920, 1080], [960, 540])
    fireEvent.click(screen.getByText('Corrigir caixa'))
    fireEvent.change(screen.getByLabelText('X'), { target: { value: '77' } })
    fireEvent.click(screen.getByText('Salvar caixa'))
    await waitFor(() => expect(patch).toHaveBeenCalled())
    expect(patch).toHaveBeenCalledWith('/alerts/e1/violations', {
      correcoes: [{ index: 0, bbox: [77, 50, 200, 400] }],
    })
  })

  it('ESC cancela a correção', async () => {
    montar()
    await montarFrame([1920, 1080], [960, 540])
    fireEvent.click(screen.getByText('Corrigir caixa'))
    expect(screen.getByText('Salvar caixa')).toBeTruthy()
    fireEvent.keyDown(screen.getByRole('group'), { key: 'Escape' })
    expect(screen.queryByText('Salvar caixa')).toBeNull()
    expect(screen.getByText('Corrigir caixa')).toBeTruthy()
  })

  it('mostra o NOME de quem corrigiu a caixa, nunca o UUID cru', async () => {
    responde({ ...EVENTO, correcao_ultima: { por: 'u-9', por_nome: 'Ana Souza', em: '2026-08-24T10:00:00Z' } })
    montar()
    // "Ana Souza" mora num <strong> aninhado — getByText não concatena texto
    // através de elemento filho, daí ler o textContent inteiro do bloco.
    const badge = await screen.findByTestId('badge-autoria')
    expect(badge.textContent).toContain('Caixa corrigida por')
    expect(badge.textContent).toContain('Ana Souza')
    expect(badge.textContent).not.toContain('u-9')
  })

  it('entrada antiga do ledger (sem por_nome) mostra travessão, nunca o UUID de por', async () => {
    responde({ ...EVENTO, correcao_ultima: { por: 'u-9', em: '2026-08-24T10:00:00Z' } })
    montar()
    const badge = await screen.findByTestId('badge-autoria')
    expect(badge.textContent).toContain('—')
    expect(badge.textContent).not.toContain('u-9')
  })
})
