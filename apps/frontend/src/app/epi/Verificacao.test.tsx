/**
 * EPI Verificação — o que este arquivo protege, e por quê.
 *
 * Duas coisas, e as duas já custaram caro:
 *
 *  1. **A FILA POR INCERTEZA** (delta §2 item 9). Se alguém "simplificar" para
 *     ordem cronológica, a tela continua funcionando, continua bonita e passa a
 *     desperdiçar o clique do operador nos casos que o modelo já acerta. Não há
 *     erro na tela — só um flywheel de treino que anda devagar sem ninguém
 *     saber. Por isso a ordem é asserção, não detalhe.
 *
 *  2. **O AVANÇO DA FILA** (PRs 496, 500, 487). A fila local é APPEND-ONLY e o
 *     "próximo" é índice sobre ela. Os três testes de regressão aqui são os três
 *     defeitos medidos: reordenar sob os olhos do operador, perder linha no
 *     reabastecimento, e o listener com closure velha carimbando veredito no
 *     item errado.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../services/api'

import { Verificacao, incertezaDe, ordenarPorIncerteza, type ItemVerificacao } from './Verificacao'

// ── Dublês ──────────────────────────────────────────────────────────────────

const get = vi.fn()
const post = vi.fn()
const patch = vi.fn()
// `ApiError` também é dublê: a tela distingue o 409 ("outra pessoa já julgou")
// pelo STATUS, não pela mensagem — um `Error` cru cairia no toast de erro
// genérico e o operador clicaria de novo no que já está resolvido.
vi.mock('../../services/api', () => ({
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
    patch: (...a: unknown[]) => patch(...a),
  },
  ApiError: class ApiErrorDuble extends Error {
    status: number
    constructor(message: string, status: number) {
      super(message)
      this.name = 'ApiError'
      this.status = status
    }
  },
}))

// jsdom não implementa PointerEvent: sem isto o fireEvent cai num Event cru e
// clientX/clientY chegam undefined — a conversão daria NaN e os testes de
// pan/correção de caixa passariam a medir nada (mesmo stub de EventoDetalhe.test.tsx).
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

let permissoes = new Set(['verification:read', 'verification:write'])
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ can: (p: string) => permissoes.has(p) }),
}))

const toastErro = vi.fn()
const toastInfo = vi.fn()
vi.mock('../../components/ui/Toast/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: toastErro, warning: vi.fn(), info: toastInfo }),
}))

// ── Dados (formato real do payload: alerts.* + camera_name do JOIN) ─────────

function item(
  id: string,
  classe: string,
  confidence: number | undefined,
  extra: Partial<ItemVerificacao> = {},
): ItemVerificacao {
  return {
    id,
    camera_id: `cam-${id}`,
    camera_name: `CAM-${id.toUpperCase()}`,
    class_name: classe,
    confidence,
    violations: confidence === undefined ? [{ class: classe }] : [{ class: classe, confidence }],
    created_at: '2026-08-27T14:32:08Z',
    ...extra,
  }
}

const A = item('a', 'no_helmet', 0.9) //  incerteza 0,40
const B = item('b', 'no_vest', 0.52) //   incerteza 0,02  ← o mais duvidoso
const C = item('c', 'no_glasses', 0.7) // incerteza 0,20
const D = item('d', 'no_gloves', undefined) // sem confiança → 1,0 (fim da fila)

/** `success({items, count, total})` — o envelope real de `verification/routes.py`.
 *  `total` default = `itens.length`: nos testes que não mexem com ele, o
 *  total "do servidor" coincide com o lote local — casos que PRECISAM
 *  divergir passam `total` explícito (ver describe "N restantes"). */
const fila = (itens: ItemVerificacao[], total = itens.length) => ({
  success: true,
  message: 'OK',
  data: { items: itens, count: itens.length, total },
})

/** `fireEvent` porque este repo não tem `user-event` — o teclado é a interface
 *  principal desta tela, e é ele que os testes de fila exercitam. */
const tecla = (key: string) => fireEvent.keyDown(window, { key })
const clicar = (el: HTMLElement) => fireEvent.click(el)

function montar() {
  return render(
    <MemoryRouter>
      <Verificacao />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  get.mockReset()
  post.mockReset()
  patch.mockReset()
  toastErro.mockReset()
  toastInfo.mockReset()
  permissoes = new Set(['verification:read', 'verification:write'])
  post.mockResolvedValue({ success: true, data: {} })
})

afterEach(() => {
  vi.useRealTimers()
})

// ── 1 · Fila por incerteza ──────────────────────────────────────────────────

describe('fila por incerteza (delta §2 item 9)', () => {
  it('mede a distância da confiança a 0,5 — o ponto de dúvida do modelo', () => {
    expect(incertezaDe(B)).toBeCloseTo(0.02)
    expect(incertezaDe(C)).toBeCloseTo(0.2)
    expect(incertezaDe(A)).toBeCloseTo(0.4)
  })

  it('MIN sobre as propostas: basta UMA duvidosa para o recorte valer a revisão', () => {
    const misto = item('m', 'no_helmet', 0.99)
    misto.violations = [
      { class: 'no_helmet', confidence: 0.99 },
      { class: 'no_vest', confidence: 0.51 },
    ]
    expect(incertezaDe(misto)).toBeCloseTo(0.01)
  })

  it('sem confiança nenhuma → 1,0, o COALESCE do backend: vai para o FIM', () => {
    // Pôr no começo o que não se sabe medir seria ordem arbitrária vestida de
    // prioridade — a mesma decisão está comentada em _INCERTEZA_SQL.
    expect(incertezaDe(D)).toBe(1)
    expect(ordenarPorIncerteza([D, A, B]).map((i) => i.id)).toEqual(['b', 'a', 'd'])
  })

  it('empate mantém a ordem do servidor — desempatar seria mexer na fila à toa', () => {
    const x = item('x', 'no_vest', 0.6)
    const y = item('y', 'no_vest', 0.4) // mesma distância a 0,5
    expect(ordenarPorIncerteza([x, y]).map((i) => i.id)).toEqual(['x', 'y'])
    expect(ordenarPorIncerteza([y, x]).map((i) => i.id)).toEqual(['y', 'x'])
  })

  it('a tela abre no mais duvidoso, não no mais recente', async () => {
    // Rodada 4: quem ordena por incerteza é o SERVIDOR agora — o mock já
    // chega pré-ordenado (B, C, A — a ordem que `get_human_queue` devolveria
    // para este trio, sem rajada). Se a tela mostrasse por `created_at`
    // (ordem crua de cadastro, A/B/C), o operador gastaria o clique onde o
    // modelo já acerta.
    get.mockResolvedValue(fila([B, C, A]))
    montar()
    expect(await screen.findByText('Sem colete')).toBeTruthy()
  })

  it('a ordem renderizada é a ordem que o SERVIDOR devolveu — o cliente não reordena mais', async () => {
    // Teste de mutação (rodada 4): se `ordenarPorIncerteza(itens)` voltar a
    // ser chamado em `carregar`, este teste fica VERMELHO. O mock devolve A
    // primeiro DE PROPÓSITO — A é o MENOS incerto (0,40) dos três; por
    // incerteza ascendente o cliente mostraria B (0,02) primeiro. Aqui tem
    // de ser A, porque é `itens[0]` do servidor e o cliente não reordena.
    get.mockResolvedValue(fila([A, C, B]))
    montar()
    expect(await screen.findByText('Sem capacete')).toBeTruthy() // A, item[0] do servidor
    expect(screen.queryByText('Sem colete')).toBeNull() // B (mais incerto) NÃO é o primeiro
  })
})

// ── 2 · Avanço da fila ──────────────────────────────────────────────────────

describe('avanço da fila (PRs 496, 500, 487)', () => {
  it('veredito vai para o alerta na tela e avança para o próximo da ordem', async () => {
    get.mockResolvedValue(fila([B, C, A])) // ordem do servidor — ver "fila por incerteza"
    montar()
    await screen.findByText('Sem colete') // B, o mais duvidoso

    clicar(screen.getByRole('button', { name: /Confirmar/ }))

    expect(post).toHaveBeenCalledWith('/verification/b/review', { verdict: 'approve' })
    expect(await screen.findByText('Sem óculos')).toBeTruthy() // C, o seguinte
  })

  it('a tecla C decide o item CORRENTE, não o do primeiro render (ref atrasado)', async () => {
    // PR 496: listener registrado uma vez fica preso à closure do primeiro
    // render. O operador vê C na tela, aperta C, e o veredito cai em B.
    get.mockResolvedValue(fila([B, C, A]))
    montar()
    await screen.findByText('Sem colete')

    tecla('ArrowRight')
    expect(await screen.findByText('Sem óculos')).toBeTruthy()
    tecla('c')

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    expect(post).toHaveBeenCalledWith('/verification/c/review', { verdict: 'approve' })
  })

  it('duas teclas C no mesmo tick carimbam UM veredito, não dois', async () => {
    // `enviando` só vale no próximo render: sem trava síncrona as duas leituras
    // veem `false` e saem dois POST. Veredito duplicado suja dado de treino.
    get.mockResolvedValue(fila([B, A]))
    montar()
    await screen.findByText('Sem colete')

    tecla('c')
    tecla('c')

    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(post).toHaveBeenCalledTimes(1)
  })

  it('a tecla R rejeita com o motivo escolhido', async () => {
    get.mockResolvedValue(fila([B]))
    montar()
    await screen.findByText('Sem colete')

    fireEvent.change(screen.getByLabelText(/Motivo/), { target: { value: 'epi_presente' } })
    tecla('r')
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/verification/b/review', {
        verdict: 'reject',
        reason: 'epi_presente',
      }),
    )
  })

  it('reabastecimento ANEXA — não reordena a fila sob os olhos do operador', async () => {
    // PRs 487 e 500: o item decidido some do filtro `needs_human` no servidor, então
    // a leitura seguinte é OUTRO conjunto. Se o novo lote substituísse a fila (ou
    // fosse reordenado por incerteza junto com ela), a ordem mudaria sozinha no
    // meio da decisão.
    vi.useFakeTimers()
    get.mockResolvedValueOnce(fila([B, A])) // ordem do servidor
    montar()
    await vi.waitFor(() => expect(screen.getByText('Sem colete')).toBeTruthy())

    clicar(screen.getByRole('button', { name: /Confirmar/ })) // decide B, avança pra A
    await vi.waitFor(() => expect(screen.getByText('Sem capacete')).toBeTruthy())

    // Segunda leitura: B (já meu) some do servidor, e z (mais duvidoso que tudo) entra.
    get.mockResolvedValue(fila([A, item('z', 'no_helmet', 0.5)]))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000)
    })

    // z entrou na fila, mas ATRÁS: o operador segue exatamente onde estava.
    expect(screen.getByText('Sem capacete')).toBeTruthy()
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('reabastecimento não duplica o que já está na fila (dedup por id, não OFFSET)', async () => {
    vi.useFakeTimers()
    get.mockResolvedValue(fila([B, A])) // as MESMAS duas linhas, de novo — ordem do servidor
    montar()
    await vi.waitFor(() => expect(screen.getByText('Sem colete')).toBeTruthy())

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000)
    })

    // 2 itens, não 4: se duplicasse, "Próximo" continuaria habilitado no fim.
    await act(async () => {
      screen.getByRole('button', { name: 'Próximo item' }).click()
    })
    expect(screen.getByRole('button', { name: 'Próximo item' })).toHaveProperty('disabled', true)
  })

  it('decidido NÃO sai da fila: ← volta e mostra o que foi decidido', async () => {
    // Remover o decidido encolheria o array sob o índice — o "próximo" viraria
    // o item errado e o ← do desenho não teria para onde voltar.
    get.mockResolvedValue(fila([B, A])) // ordem do servidor
    montar()
    await screen.findByText('Sem colete')

    clicar(screen.getByRole('button', { name: /Confirmar/ }))
    expect(await screen.findByText('Sem capacete')).toBeTruthy() // A

    tecla('ArrowLeft')
    expect(await screen.findByText('Sem colete')).toBeTruthy()
    expect(screen.getByText('Confirmado')).toBeTruthy()
  })

  it('falha no veredito não avança nem carimba — o item volta para a fila', async () => {
    get.mockResolvedValue(fila([B, A]))
    post.mockRejectedValue(new Error('500'))
    montar()
    await screen.findByText('Sem colete')

    clicar(screen.getByRole('button', { name: /Confirmar/ }))

    await waitFor(() => expect(toastErro).toHaveBeenCalled())
    expect(screen.getByText('Sem colete')).toBeTruthy()
    expect(screen.queryByText('Confirmado')).toBeNull()
  })
})

// ── 2.2 · Colisão multiusuário: 409 do backend ──────────────────────────────

describe('dois operadores no mesmo alerta (bloco 4)', () => {
  /** O backend recusa o segundo veredito (`verification_verdict IS NULL OR
   *  verified_by = <eu>` no UPDATE) e responde 409 com quem julgou e quando.
   *  Antes da guarda ele respondia 200 e o segundo veredito SOBRESCREVIA o
   *  primeiro — a tela não tinha como saber, e não sabia. */
  const conflito = () =>
    new ApiError('Maria Silva já avaliou este alerta há 2 minutos.', 409)

  it('mostra QUEM julgou e QUANDO — não "Erro ao registrar o veredito"', async () => {
    get.mockResolvedValue(fila([B, A]))
    post.mockRejectedValue(conflito())
    montar()
    await screen.findByText('Sem colete')

    clicar(screen.getByRole('button', { name: /Confirmar/ }))

    await waitFor(() => expect(toastInfo).toHaveBeenCalled())
    expect(toastInfo.mock.calls[0][1]).toContain('Maria Silva')
    expect(toastInfo.mock.calls[0][1]).toContain('há 2 minutos')
    // 409 não é falha do operador: nada de toast vermelho.
    expect(toastErro).not.toHaveBeenCalled()
  })

  it('AVANÇA para o próximo — o trabalho dele não para no item alheio', async () => {
    get.mockResolvedValue(fila([B, A]))
    post.mockRejectedValue(conflito())
    montar()
    await screen.findByText('Sem colete')

    clicar(screen.getByRole('button', { name: /Confirmar/ }))

    expect(await screen.findByText('Sem capacete')).toBeTruthy()
  })

  it('carimba "Revisado por outro" — NUNCA "Confirmado" (a decisão não foi dele)', async () => {
    get.mockResolvedValue(fila([B, A]))
    post.mockRejectedValue(conflito())
    montar()
    await screen.findByText('Sem colete')

    clicar(screen.getByRole('button', { name: /Confirmar/ }))
    await screen.findByText('Sem capacete')

    tecla('ArrowLeft')
    expect(await screen.findByText('Sem colete')).toBeTruthy()
    expect(screen.getByText('Revisado por outro')).toBeTruthy()
    expect(screen.queryByText('Confirmado')).toBeNull()
  })

  it('não reenvia o veredito recusado: o item alheio sai do trabalho pendente', async () => {
    // "N RESTANTES" desconta a decisão feita depois do último sync. Um item
    // resolvido por outra pessoa TAMBÉM saiu da fila do servidor — deixá-lo
    // contando como pendente é a família do "Fila zerada" mentindo, ao
    // contrário.
    get.mockResolvedValue(fila([B, A], 2))
    post.mockRejectedValue(conflito())
    montar()
    await screen.findByText('Sem colete')

    clicar(screen.getByRole('button', { name: /Confirmar/ }))
    await screen.findByText('Sem capacete')

    expect(await screen.findByText('1 RESTANTES')).toBeTruthy()
  })

  it('erro que NÃO é 409 continua vermelho e sem carimbo', async () => {
    // Teste de mutação: se o `catch` tratar QUALQUER falha como conflito, o
    // 500 passa a carimbar o item e a fila avança por cima de trabalho não
    // gravado.
    get.mockResolvedValue(fila([B, A]))
    post.mockRejectedValue(new ApiError('Erro ao revisar alerta', 500))
    montar()
    await screen.findByText('Sem colete')

    clicar(screen.getByRole('button', { name: /Confirmar/ }))

    await waitFor(() => expect(toastErro).toHaveBeenCalled())
    expect(screen.getByText('Sem colete')).toBeTruthy()
    expect(screen.queryByText('Revisado por outro')).toBeNull()
  })
})

// ── 2.1 · Motivo estruturado do veredito (contrato B2) ──────────────────────

describe('motivo do veredito (contrato B2)', () => {
  it('rejeitar sem motivo NÃO envia — o motivo alimenta a calibração e não pode faltar', async () => {
    get.mockResolvedValue(fila([B]))
    montar()
    await screen.findByText('Sem colete')

    clicar(screen.getByRole('button', { name: /Rejeitar/ }))

    expect(post).not.toHaveBeenCalled()
    expect(toastErro).toHaveBeenCalled()
    expect(screen.getByText('Selecione um motivo para rejeitar.')).toBeTruthy()
  })

  it('motivo escolhido chega ao backend no POST que já aceita `reason`', async () => {
    get.mockResolvedValue(fila([B]))
    montar()
    await screen.findByText('Sem colete')

    fireEvent.change(screen.getByLabelText(/Motivo/), {
      target: { value: 'nao_da_pra_ver' },
    })
    clicar(screen.getByRole('button', { name: /Rejeitar/ }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/verification/b/review', {
        verdict: 'reject',
        reason: 'nao_da_pra_ver',
      }),
    )
  })

  it('confirmar sem motivo funciona — motivo é opcional pra aprovar', async () => {
    get.mockResolvedValue(fila([B]))
    montar()
    await screen.findByText('Sem colete')

    clicar(screen.getByRole('button', { name: /Confirmar/ }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/verification/b/review', { verdict: 'approve' }),
    )
  })

  it('motivo do item decidido não vaza pro próximo item da fila', async () => {
    get.mockResolvedValue(fila([B, A]))
    montar()
    await screen.findByText('Sem colete')

    fireEvent.change(screen.getByLabelText(/Motivo/), { target: { value: 'epi_presente' } })
    clicar(screen.getByRole('button', { name: /Rejeitar/ }))
    expect(await screen.findByText('Sem capacete')).toBeTruthy() // avançou pra A

    expect(screen.getByLabelText<HTMLSelectElement>(/Motivo/).value).toBe('')
  })

  it('motivo escolhido e NÃO decidido some ao navegar pra "Próximo item" — não vaza pro veredito de outro alerta', async () => {
    // O teste acima só cobre o vazamento via `decidir()` (que já limpa o
    // motivo no sucesso). Aqui é NAVEGAÇÃO sem decidir — o operador escolhe um
    // motivo em B, muda de ideia e vai para A com ← →, sem clicar em
    // Rejeitar/Confirmar. Sem o efeito que reseta por `atual?.id`, o motivo de
    // B viaja no POST de A: dado de calibração gravado no alerta errado.
    get.mockResolvedValue(fila([B, A]))
    montar()
    await screen.findByText('Sem colete')

    fireEvent.change(screen.getByLabelText(/Motivo/), { target: { value: 'epi_presente' } })
    clicar(screen.getByRole('button', { name: 'Próximo item' }))
    expect(await screen.findByText('Sem capacete')).toBeTruthy() // A, sem decidir B

    expect(screen.getByLabelText<HTMLSelectElement>(/Motivo/).value).toBe('')

    clicar(screen.getByRole('button', { name: /Confirmar/ }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/verification/a/review', { verdict: 'approve' }),
    )
  })
})

// ── 3 · Estados de rota ─────────────────────────────────────────────────────

describe('estados', () => {
  it('fila vazia diz "Fila zerada" — vazio honesto, com saída', async () => {
    get.mockResolvedValue(fila([]))
    montar()
    expect(await screen.findByText('Fila zerada')).toBeTruthy()
    expect(screen.getByRole('link', { name: /Voltar ao dashboard/ })).toBeTruthy()
  })

  it('erro na primeira carga mostra o endereço real e oferece retry', async () => {
    get.mockRejectedValueOnce(new Error('Timeout na requisicao'))
    montar()
    expect(await screen.findByText('Não foi possível carregar a fila')).toBeTruthy()
    expect(screen.getByText(/GET \/api\/verification\/queue/)).toBeTruthy()

    get.mockResolvedValue(fila([B]))
    clicar(screen.getByRole('button', { name: 'Tentar novamente' }))
    expect(await screen.findByText('Sem colete')).toBeTruthy()
  })

  it('falha de um poll com fila na mão NÃO apaga o que se está julgando', async () => {
    vi.useFakeTimers()
    get.mockResolvedValueOnce(fila([B]))
    get.mockRejectedValue(new Error('502'))
    montar()
    await vi.waitFor(() => expect(screen.getByText('Sem colete')).toBeTruthy())

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000)
    })
    expect(screen.getByText('Sem colete')).toBeTruthy()
    expect(screen.queryByText('Não foi possível carregar a fila')).toBeNull()
  })

  it('sem verification:read não abre a fila nem chama a API', async () => {
    permissoes = new Set()
    montar()
    expect(await screen.findByText('Sem permissão')).toBeTruthy()
    expect(get).not.toHaveBeenCalled()
  })

  it('sem verification:write o veredito fica visível e desabilitado, com o porquê', async () => {
    permissoes = new Set(['verification:read'])
    get.mockResolvedValue(fila([B]))
    montar()
    await screen.findByText('Sem colete')

    const confirmar = screen.getByRole('button', { name: /Confirmar/ })
    expect(confirmar).toHaveProperty('disabled', true)
    expect(confirmar.getAttribute('title')).toContain('verification:write')
  })
})

// ── 4 · O que o desenho exige ───────────────────────────────────────────────

const AQUI = path.dirname(fileURLToPath(import.meta.url))
const CSS = fs.readFileSync(path.join(AQUI, 'Verificacao.css.ts'), 'utf-8')

describe('contrato do desenho', () => {
  it('botão de veredito usa o piso de 56px desta tela, não o de 48px', () => {
    // README do handoff: "botões de veredito ≥48px (verificação ≥56px)". É o
    // único lugar onde o piso sobe — decisão repetida em alvo pequeno vira
    // clique errado, e clique errado aqui carimba dado de treino errado.
    expect(CSS).toContain('lk.medida.vereditoVerificacao')
    expect(CSS).not.toMatch(/lk\.medida\.veredito\b/)

    const tokens = fs.readFileSync(path.join(AQUI, '..', 'tokens', 'lk.css.ts'), 'utf-8')
    expect(tokens).toContain("vereditoVerificacao: '56px'")
  })

  it('progresso e restantes saem do estado real da fila, não de constante', async () => {
    get.mockResolvedValue(fila([B, C, A])) // ordem do servidor
    montar()
    await screen.findByText('Sem colete')

    expect(screen.getByText('3 RESTANTES')).toBeTruthy()
    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('0')

    clicar(screen.getByRole('button', { name: /Confirmar/ }))
    expect(await screen.findByText('2 RESTANTES')).toBeTruthy()
    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('33')
  })

  it('"enviar para anotação" fica no lugar do desenho, desabilitado e dizendo por quê', async () => {
    // Não há rota, em nenhuma das 421 do contrato, que leve um ALERTA para a
    // fila do Estúdio. Botão que não faz nada em silêncio é pior que ausente.
    get.mockResolvedValue(fila([B]))
    montar()
    await screen.findByText('Sem colete')

    const anotar = screen.getByRole('button', { name: /Enviar para anotação/ })
    expect(anotar).toHaveProperty('disabled', true)
    expect(anotar.getAttribute('title')).toMatch(/endpoint/i)
    // E o atalho "A" NÃO é anunciado: tecla prometida que não age é mentira.
    expect(screen.queryByText('ANOTAR')).toBeNull()
  })

  it('evidência: pede a URL assinada do alerta e projeta a caixa em pixels', async () => {
    get.mockImplementation((rota: string) =>
      rota.includes('/snapshot')
        ? Promise.resolve({ data: { snapshot_url: 'https://r2.example/evid.jpg' } })
        : Promise.resolve(
            fila([
              item('e', 'no_helmet', 0.51, {
                evidence_key: 'tenant/e.jpg',
                violations: [
                  {
                    class: 'no_helmet',
                    confidence: 0.51,
                    bbox: [100, 50, 200, 400],
                    bbox_unidade: 'pixels_xywh_frame_original',
                  },
                ],
              }),
            ]),
          ),
    )
    montar()
    const img = (await screen.findByAltText(/Evidência de/)) as HTMLImageElement
    expect(img.src).toBe('https://r2.example/evid.jpg')
    expect(get).toHaveBeenCalledWith('/alerts/e/snapshot')

    Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
    Object.defineProperty(img, 'naturalHeight', { value: 1000, configurable: true })
    await act(async () => {
      img.dispatchEvent(new Event('load'))
    })

    const caixa = screen.getByTestId('caixa-violacao')
    expect(caixa.getAttribute('style')).toContain('left: 10%')
    expect(caixa.getAttribute('style')).toContain('width: 20%')
  })

  it('caixa em unidade desconhecida não é projetada — e a tela DIZ isso', async () => {
    get.mockImplementation((rota: string) =>
      rota.includes('/snapshot')
        ? Promise.resolve({ data: { snapshot_url: 'https://r2.example/e.jpg' } })
        : Promise.resolve(
            fila([
              item('u', 'no_vest', 0.5, {
                evidence_key: 'tenant/u.jpg',
                violations: [
                  { class: 'no_vest', confidence: 0.5, bbox: [0, 0, 1, 1], bbox_unidade: 'normalizado_cxcywh' },
                ],
              }),
            ]),
          ),
    )
    montar()
    await screen.findByAltText(/Evidência de/)
    expect(screen.getByText(/sem unidade de caixa conhecida/)).toBeTruthy()
    expect(screen.queryByTestId('caixa-violacao')).toBeNull()
  })
})


// ── 5 · Alerta que outra pessoa já revisou ──────────────────────────────────

describe('dois revisores ao mesmo tempo', () => {
  it('item julgado por outro SOME da fila; o meu fica com o estado; a contagem reflete o servidor', async () => {
    // O achado (paridade §3): a fila mentia sobre o que falta julgar — item
    // que outro operador revisou nunca saía, seguia contando em "N RESTANTES"
    // e era apresentado de novo para julgar, sobrescrevendo em silêncio o
    // veredito alheio. Dado de auditoria trocado sem ninguém saber, e com dois
    // revisores isso acontecia no primeiro dia.
    vi.useFakeTimers()
    get.mockResolvedValueOnce(fila([B, C, A])) // ordem do servidor
    montar()
    await vi.waitFor(() => expect(screen.getByText('Sem colete')).toBeTruthy()) // B
    expect(screen.getByText('3 RESTANTES')).toBeTruthy()

    clicar(screen.getByRole('button', { name: /Confirmar/ })) // EU decido B
    await vi.waitFor(() => expect(screen.getByText('Sem óculos')).toBeTruthy()) // avança pra C

    // Segunda leitura: só A sobra no servidor. B sumiu porque EU decidi (não
    // conta contra ninguém); C sumiu porque OUTRA PESSOA revisou por fora —
    // veio abaixo do limite, então dá para concluir isso com segurança.
    get.mockResolvedValueOnce(fila([A]))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000)
    })
    await vi.waitFor(() => expect(get).toHaveBeenCalledTimes(2))

    // C (do outro revisor) sumiu — nem sequer é mostrado de novo — e o
    // operador foi avisado, sem precisar clicar em nada para descobrir.
    expect(screen.queryByText('Sem óculos')).toBeNull()
    expect(toastInfo).toHaveBeenCalled()
    // A contagem já não mente: só A falta julgar.
    expect(screen.getByText('Sem capacete')).toBeTruthy()
    expect(screen.getByText('1 RESTANTES')).toBeTruthy()

    // B (o meu) continua na fila com o estado — ← ainda volta pra ele.
    tecla('ArrowLeft')
    await vi.waitFor(() => expect(screen.getByText('Sem colete')).toBeTruthy())
    expect(screen.getByText('Confirmado')).toBeTruthy()
    vi.useRealTimers()
  })

  it('lote CHEIO não remove ninguém: o que faltou pode estar além do corte', async () => {
    // O endpoint corta em `limit` e não pagina. Se o lote voltou COM o tamanho
    // do limite, o que não veio pode estar apenas além do corte — concluir ali
    // "outra pessoa resolveu" seria mentira, e tiraria da tela alertas que
    // ainda precisam de veredito. É o caso que faz `carregar` errar para o
    // lado caro: preservar trabalho legítimo em vez de escondê-lo.
    vi.useFakeTimers()
    const cheio = Array.from({ length: 50 }, (_, i) => item(`x${i}`, 'no_helmet', 0.6))
    get.mockResolvedValueOnce(fila(cheio))
    montar()
    await vi.waitFor(() => expect(get).toHaveBeenCalledTimes(1))

    // Segundo lote: também CHEIO, e sem nenhum dos anteriores. Um lote cheio
    // não autoriza conclusão nenhuma sobre quem não veio.
    const outros = Array.from({ length: 50 }, (_, i) => item(`y${i}`, 'no_vest', 0.6))
    get.mockResolvedValueOnce(fila(outros))
    await vi.advanceTimersByTimeAsync(15_000)
    await vi.waitFor(() => expect(get).toHaveBeenCalledTimes(2))

    // x0 continua julgável: o veredito TEM de ir.
    post.mockClear()
    toastInfo.mockClear()
    tecla('c')
    await vi.waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    expect(toastInfo).not.toHaveBeenCalled()
    vi.useRealTimers()
  })
})

// ── 6 · "N RESTANTES" é o total do servidor, não `fila.length` ─────────────

describe('"N RESTANTES" usa a verdade do servidor (bug: "Fila zerada" com centenas no banco)', () => {
  it('total do servidor MAIOR que o lote local aparece — não o tamanho do array', async () => {
    // O array local é só o LIMITE (50) mais incerto; o banco pode ter muito
    // mais. Antes deste contador, "N RESTANTES" era `fila.length`-based e
    // mentia exatamente aqui.
    get.mockResolvedValue(fila([A], 366))
    montar()
    await screen.findByText('Sem capacete')
    expect(screen.getByText('366 RESTANTES')).toBeTruthy()
  })

  it('sem `total` na resposta (backend antigo/mock parcial), cai para a contagem local', async () => {
    get.mockResolvedValue({ success: true, message: 'OK', data: { items: [B, A], count: 2 } })
    montar()
    await screen.findByText('Sem colete')
    expect(screen.getByText('2 RESTANTES')).toBeTruthy()
  })

  it('decisão local desconta do total do servidor na hora, antes do próximo poll', async () => {
    // O servidor só sabe da minha decisão no PRÓXIMO sync (até 15s depois) —
    // sem descontar local, "N RESTANTES" ficaria travado no valor antigo por
    // até 15s após cada clique, mesmo com feedback visual de "Confirmado".
    get.mockResolvedValue(fila([B, C, A], 50)) // servidor diz 50, só 3 vieram no lote
    montar()
    await screen.findByText('Sem colete')
    expect(screen.getByText('50 RESTANTES')).toBeTruthy()

    clicar(screen.getByRole('button', { name: /Confirmar/ }))
    expect(await screen.findByText('49 RESTANTES')).toBeTruthy()
  })

  it('total do servidor zerado mostra "Fila zerada" mesmo com item ainda no array local', async () => {
    // Não deve acontecer no fluxo real (lista e total vêm da MESMA leitura),
    // mas se acontecer, a verdade do servidor é o que decide o estado vazio.
    get.mockResolvedValue(fila([A], 0))
    montar()
    expect(await screen.findByText('Fila zerada')).toBeTruthy()
  })
})

// ── 7 · Contrato B1 — lupa (pan+zoom) e correção de caixa ───────────────────

/** Item com evidência — helper local (os `item()` de cima não trazem bbox). */
function itemComEvidencia(id: string, extra: Partial<ItemVerificacao> = {}): ItemVerificacao {
  return item(id, 'no_helmet', 0.6, { evidence_key: `tenant/${id}.jpg`, ...extra })
}

const respostaEvidencia = (url: string) => Promise.resolve({ data: { snapshot_url: url } })

describe('lupa: pan respeita o limite (contrato B1)', () => {
  it('arrasto além do limite não desloca além do clamp calculado — só zoom não bastava', async () => {
    // Código ANTES deste contrato: zoom era só `transform: scale(zoom)`, sem
    // pan nenhum — não havia `translate()` para clampar, e este teste falhava
    // (não existia `data-testid="camada-zoom"` nem arrasto que movesse nada).
    get.mockImplementation((rota: string) =>
      rota.includes('/snapshot') ? respostaEvidencia('https://r2.example/p.jpg') : Promise.resolve(fila([itemComEvidencia('p')])),
    )
    montar()
    await screen.findByAltText(/Evidência de/)

    const palco = screen.getByRole('group')
    Object.defineProperty(palco, 'getBoundingClientRect', {
      configurable: true,
      value: () => ({
        left: 0, top: 0, right: 800, bottom: 600, width: 800, height: 600, x: 0, y: 0, toJSON: () => ({}),
      }),
    })

    // Zoom in (duplo clique = fator 2, ancorado no ponto clicado).
    fireEvent.doubleClick(palco, { clientX: 400, clientY: 300 })

    // Arrasto bem além do limite de pan possível nesta escala.
    fireEvent.pointerDown(palco, { clientX: 0, clientY: 0, pointerId: 1 })
    fireEvent.pointerMove(palco, { clientX: 5000, clientY: 0, pointerId: 1 })
    fireEvent.pointerUp(palco, { clientX: 5000, clientY: 0, pointerId: 1 })

    const camada = screen.getByTestId('camada-zoom')
    // limitePan(2, 800) = 800*(2-1)/2 = 400 — o arrasto de 5000px é MORDIDO ali,
    // nunca refletido cru na tela (senão a imagem sumiria da vista).
    expect(camada.style.transform).toContain('translate(400px, 0px)')
    expect(camada.style.transform).toContain('scale(2)')
  })

  it('em escala 1 (sem zoom) o pan fica em 0 — arrastar não desloca nada', async () => {
    get.mockImplementation((rota: string) =>
      rota.includes('/snapshot') ? respostaEvidencia('https://r2.example/p2.jpg') : Promise.resolve(fila([itemComEvidencia('p2')])),
    )
    montar()
    await screen.findByAltText(/Evidência de/)
    const palco = screen.getByRole('group')
    Object.defineProperty(palco, 'getBoundingClientRect', {
      configurable: true,
      value: () => ({ left: 0, top: 0, right: 800, bottom: 600, width: 800, height: 600, x: 0, y: 0, toJSON: () => ({}) }),
    })

    fireEvent.pointerDown(palco, { clientX: 0, clientY: 0, pointerId: 1 })
    fireEvent.pointerMove(palco, { clientX: 300, clientY: 200, pointerId: 1 })
    fireEvent.pointerUp(palco, { clientX: 300, clientY: 200, pointerId: 1 })

    expect(screen.getByTestId('camada-zoom').style.transform).toContain('translate(0px, 0px)')
  })
})

describe('correção de caixa: salva e volta do servidor (contrato B1)', () => {
  beforeEach(() => {
    permissoes.add('alerts:feedback')
  })

  it('botão só aparece com alerts:feedback', async () => {
    permissoes.delete('alerts:feedback')
    get.mockImplementation((rota: string) =>
      rota.includes('/snapshot') ? respostaEvidencia('https://r2.example/n.jpg') : Promise.resolve(fila([itemComEvidencia('n')])),
    )
    montar()
    await screen.findByAltText(/Evidência de/)
    expect(screen.queryByRole('button', { name: /Corrigir caixa/i })).toBeNull()
  })

  it('arrasto grava bbox em PIXELS do frame ORIGINAL e a tela mostra a caixa que o SERVIDOR devolveu', async () => {
    // Código ANTES deste contrato: não havia botão "Corrigir caixa" nem PATCH
    // nenhum — este teste falhava por `getByRole('button', {name: /Corrigir/})`
    // não existir.
    get.mockImplementation((rota: string) =>
      rota.includes('/snapshot')
        ? respostaEvidencia('https://r2.example/c.jpg')
        : Promise.resolve(
            fila([
              itemComEvidencia('cx', {
                violations: [
                  { class: 'no_helmet', confidence: 0.6, bbox: [100, 50, 200, 400], bbox_unidade: 'pixels_xywh_frame_original' },
                ],
              }),
            ]),
          ),
    )
    // O servidor CARIMBA a unidade e devolve a caixa CORRIGIDA + autoria —
    // a tela não pode continuar mostrando o rascunho local, tem que refletir
    // o que voltou da rota.
    patch.mockResolvedValue({
      data: {
        violations: [
          { class: 'no_helmet', confidence: 0.6, bbox: [200, 100, 400, 200], bbox_unidade: 'pixels_xywh_frame_original' },
        ],
        correcao_ultima: { por: 'u-1', por_nome: 'Ana Souza', em: '2026-08-30T10:00:00Z' },
      },
    })
    montar()

    const img = (await screen.findByAltText(/Evidência de/)) as HTMLImageElement
    Object.defineProperty(img, 'naturalWidth', { value: 1920, configurable: true })
    Object.defineProperty(img, 'naturalHeight', { value: 1080, configurable: true })
    img.getBoundingClientRect = () => ({
      left: 0, top: 0, right: 960, bottom: 540, width: 960, height: 540, x: 0, y: 0, toJSON: () => ({}),
    }) as DOMRect
    fireEvent.load(img)

    fireEvent.click(screen.getByRole('button', { name: /Corrigir caixa/i }))
    const palco = screen.getByRole('group')
    fireEvent.pointerDown(palco, { clientX: 100, clientY: 50, pointerId: 1 })
    fireEvent.pointerMove(palco, { clientX: 300, clientY: 150, pointerId: 1 })
    fireEvent.pointerUp(palco, { clientX: 300, clientY: 150, pointerId: 1 })

    fireEvent.click(screen.getByRole('button', { name: /Salvar caixa/i }))
    await waitFor(() => expect(patch).toHaveBeenCalled())
    // 100→200, 50→100, 300→300 vira largura 400, 150→150 vira altura 200:
    // fator 2 do rect exibido (960×540) para o natural (1920×1080). Só o
    // bbox vai ao servidor — nem classe, nem confiança, nem `bbox_unidade`.
    expect(patch).toHaveBeenCalledWith('/alerts/cx/violations', {
      correcoes: [{ index: 0, bbox: [200, 100, 400, 200] }],
    })

    // Volta ao modo de leitura com a caixa e a autoria que o SERVIDOR mandou —
    // não com o rascunho local (o servidor pode corrigir/clampar o valor).
    const badge = await screen.findByTestId('badge-autoria')
    expect(badge.textContent).toContain('Ana Souza')
    const caixa = screen.getByTestId('caixa-violacao')
    expect(caixa.getAttribute('style')).toContain('left: 10.4167%') // 200/1920
  })

  it('falha do PATCH mostra erro e mantém o modo de correção — nada se perde em silêncio', async () => {
    get.mockImplementation((rota: string) =>
      rota.includes('/snapshot')
        ? respostaEvidencia('https://r2.example/e.jpg')
        : Promise.resolve(
            fila([
              itemComEvidencia('e', {
                violations: [
                  { class: 'no_helmet', confidence: 0.6, bbox: [10, 10, 20, 20], bbox_unidade: 'pixels_xywh_frame_original' },
                ],
              }),
            ]),
          ),
    )
    patch.mockRejectedValue(new Error('500'))
    montar()
    const img = (await screen.findByAltText(/Evidência de/)) as HTMLImageElement
    Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
    Object.defineProperty(img, 'naturalHeight', { value: 1000, configurable: true })
    fireEvent.load(img)

    fireEvent.click(screen.getByRole('button', { name: /Corrigir caixa/i }))
    fireEvent.click(screen.getByRole('button', { name: /Salvar caixa/i }))

    await waitFor(() => expect(patch).toHaveBeenCalled())
    expect(screen.getByText(/Não foi possível salvar a caixa/i)).toBeTruthy()
    // Continua em modo de correção — "Salvar caixa" ainda visível, o rascunho não sumiu.
    expect(screen.getByRole('button', { name: /Salvar caixa/i })).toBeTruthy()
  })

  it('Escape cancela a correção sem chamar o servidor', async () => {
    get.mockImplementation((rota: string) =>
      rota.includes('/snapshot')
        ? respostaEvidencia('https://r2.example/esc.jpg')
        : Promise.resolve(
            fila([
              itemComEvidencia('esc', {
                violations: [
                  { class: 'no_helmet', confidence: 0.6, bbox: [10, 10, 20, 20], bbox_unidade: 'pixels_xywh_frame_original' },
                ],
              }),
            ]),
          ),
    )
    montar()
    const img = (await screen.findByAltText(/Evidência de/)) as HTMLImageElement
    Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
    Object.defineProperty(img, 'naturalHeight', { value: 1000, configurable: true })
    fireEvent.load(img)

    fireEvent.click(screen.getByRole('button', { name: /Corrigir caixa/i }))
    expect(screen.getByRole('button', { name: /Salvar caixa/i })).toBeTruthy()

    tecla('Escape')
    expect(screen.queryByRole('button', { name: /Salvar caixa/i })).toBeNull()
    expect(screen.getByRole('button', { name: /Corrigir caixa/i })).toBeTruthy()
    expect(patch).not.toHaveBeenCalled()
  })

  it('em modo de correção, C/R/← → ficam mudos — só Escape cancela', async () => {
    // Editar é modo EXPLÍCITO: um "C" digitado no meio de um arrasto não pode
    // carimbar veredito e abandonar a correção em curso.
    get.mockImplementation((rota: string) =>
      rota.includes('/snapshot')
        ? respostaEvidencia('https://r2.example/k.jpg')
        : Promise.resolve(
            fila([
              itemComEvidencia('k', {
                violations: [
                  { class: 'no_helmet', confidence: 0.6, bbox: [10, 10, 20, 20], bbox_unidade: 'pixels_xywh_frame_original' },
                ],
              }),
            ]),
          ),
    )
    montar()
    const img = (await screen.findByAltText(/Evidência de/)) as HTMLImageElement
    Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
    Object.defineProperty(img, 'naturalHeight', { value: 1000, configurable: true })
    fireEvent.load(img)

    fireEvent.click(screen.getByRole('button', { name: /Corrigir caixa/i }))
    tecla('c')
    tecla('r')
    tecla('ArrowRight')

    expect(post).not.toHaveBeenCalled()
    // Ainda em modo de correção — a fila não avançou.
    expect(screen.getByRole('button', { name: /Salvar caixa/i })).toBeTruthy()
  })

  it('Anterior/Próximo desabilitam durante a correção — navegar não pode descartar o rascunho em silêncio', async () => {
    // O teclado já é mudo em modo de correção (teste acima) — mas o MOUSE
    // não tinha guarda nenhuma: Anterior/Próximo só desabilitavam pela
    // POSIÇÃO na fila (índice 0 / último item), nunca por `emCorrecao`. Fila
    // de 3 pra ficar no meio (Y, índice 1), onde NENHUM dos dois já estaria
    // desabilitado por posição — só o modo de correção pode explicar.
    const X = itemComEvidencia('x', {
      violations: [{ class: 'no_helmet', confidence: 0.6, bbox: [10, 10, 20, 20], bbox_unidade: 'pixels_xywh_frame_original' }],
    })
    const Y = itemComEvidencia('y', {
      violations: [{ class: 'no_helmet', confidence: 0.6, bbox: [50, 50, 100, 100], bbox_unidade: 'pixels_xywh_frame_original' }],
    })
    const Z = itemComEvidencia('z', {
      violations: [{ class: 'no_helmet', confidence: 0.6, bbox: [80, 80, 120, 120], bbox_unidade: 'pixels_xywh_frame_original' }],
    })
    get.mockImplementation((rota: string) =>
      rota.includes('/snapshot') ? respostaEvidencia('https://r2.example/xyz2.jpg') : Promise.resolve(fila([X, Y, Z])),
    )
    montar()
    const carregaImagem = async () => {
      const img = (await screen.findByAltText(/Evidência de/)) as HTMLImageElement
      Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
      Object.defineProperty(img, 'naturalHeight', { value: 1000, configurable: true })
      fireEvent.load(img)
    }
    await carregaImagem()

    fireEvent.click(screen.getByRole('button', { name: 'Próximo item' })) // X → Y, índice 1
    await carregaImagem()
    // Fora do modo de correção, os dois estão HABILITADOS nesta posição.
    expect(screen.getByRole('button', { name: 'Item anterior' })).toHaveProperty('disabled', false)
    expect(screen.getByRole('button', { name: 'Próximo item' })).toHaveProperty('disabled', false)

    fireEvent.click(screen.getByRole('button', { name: /Corrigir caixa/i }))
    expect(screen.getByRole('button', { name: 'Item anterior' })).toHaveProperty('disabled', true)
    expect(screen.getByRole('button', { name: 'Próximo item' })).toHaveProperty('disabled', true)

    // Clique num botão desabilitado não dispara nada (nem o jsdom entrega o
    // evento) — a tela segue em correção, o rascunho não foi descartado.
    fireEvent.click(screen.getByRole('button', { name: 'Próximo item' }))
    expect(screen.getByRole('button', { name: /Salvar caixa/i })).toBeTruthy()
  })

  it('PATCH em voo grava por ID, não por posição: a fila pode reordenar enquanto o servidor responde', async () => {
    // Achado do revisor cético (contrato B1): `salvarCaixa` carimbava a
    // resposta do PATCH pelo ÍNDICE congelado antes do `await`. Fila [X,Y,Z],
    // operador corrige Y (índice 1); enquanto o PATCH está em voo, outro
    // revisor decide X por fora (poll de 15s) — X sai, Y desce pro índice 0,
    // Z desce pro 1. Com índice cru, a resposta de Y era escrita em Z: caixa
    // errada e autoria de alguém que nunca tocou naquele alerta.
    vi.useFakeTimers()
    const X = itemComEvidencia('x', {
      violations: [{ class: 'no_helmet', confidence: 0.6, bbox: [10, 10, 20, 20], bbox_unidade: 'pixels_xywh_frame_original' }],
    })
    const Y = itemComEvidencia('y', {
      violations: [{ class: 'no_helmet', confidence: 0.6, bbox: [100, 50, 200, 400], bbox_unidade: 'pixels_xywh_frame_original' }],
    })
    const Z = itemComEvidencia('z', {
      violations: [{ class: 'no_helmet', confidence: 0.6, bbox: [50, 50, 100, 100], bbox_unidade: 'pixels_xywh_frame_original' }],
    })
    get.mockImplementation((rota: string) =>
      rota.includes('/snapshot')
        ? respostaEvidencia('https://r2.example/xyz.jpg')
        : Promise.resolve(fila([X, Y, Z])),
    )

    let liberarPatch: (v: unknown) => void = () => {}
    patch.mockImplementation(() => new Promise((resolve) => { liberarPatch = resolve }))

    // Sob `vi.useFakeTimers()`, `waitFor`/`findBy*` do testing-library ficam
    // presos (dependem de timers reais) — o resto do arquivo já usa
    // `vi.waitFor` + `getBy*` neste regime (ver "reabastecimento ANEXA" etc.).
    const disparaLoad = async () => {
      await vi.waitFor(() => expect(screen.getByAltText(/Evidência de/)).toBeTruthy())
      const img = screen.getByAltText(/Evidência de/) as HTMLImageElement
      Object.defineProperty(img, 'naturalWidth', { value: 1920, configurable: true })
      Object.defineProperty(img, 'naturalHeight', { value: 1080, configurable: true })
      fireEvent.load(img)
      return img
    }

    montar()
    await disparaLoad() // X, índice 0

    await act(async () => {
      screen.getByRole('button', { name: 'Próximo item' }).click()
    })
    await disparaLoad() // Y, índice 1 — onde o operador corrige

    fireEvent.click(screen.getByRole('button', { name: /Corrigir caixa/i }))
    fireEvent.click(screen.getByRole('button', { name: /Salvar caixa/i }))
    expect(patch).toHaveBeenCalledWith('/alerts/y/violations', expect.anything())

    // PATCH de Y em voo. Outro revisor decide X por fora: no próximo poll,
    // X some, Y desce pro índice 0, Z desce pro índice 1 — o índice ONDE Y
    // ESTAVA quando o PATCH partiu.
    get.mockImplementation((rota: string) =>
      rota.includes('/snapshot')
        ? respostaEvidencia('https://r2.example/xyz.jpg')
        : Promise.resolve(fila([Y, Z])),
    )
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000)
    })
    // `get` também serve o `/snapshot` de cada item — conta só os polls da fila.
    const chamadasDaFila = () => get.mock.calls.filter((c) => String(c[0]).includes('/verification/queue')).length
    await vi.waitFor(() => expect(chamadasDaFila()).toBe(2))

    // Só agora o PATCH de Y responde.
    await act(async () => {
      liberarPatch({
        data: {
          violations: [
            { class: 'no_helmet', confidence: 0.6, bbox: [800, 100, 200, 400], bbox_unidade: 'pixels_xywh_frame_original' },
          ],
          correcao_ultima: { por: 'u-1', por_nome: 'Ana Souza', em: '2026-08-30T10:00:00Z' },
        },
      })
    })
    await vi.waitFor(() => expect(screen.queryByRole('button', { name: /Salvar caixa/i })).toBeNull())

    // A tela voltou pro Y (recalculado por ID no poll, regra 1 do docblock) —
    // a correção e a autoria têm que estar NELE.
    await disparaLoad()
    await vi.waitFor(() => expect(screen.getByTestId('badge-autoria')).toBeTruthy())
    expect(screen.getByTestId('badge-autoria').textContent).toContain('Ana Souza')
    expect(screen.getByTestId('caixa-violacao').getAttribute('style')).toContain('left: 41.6667%') // 800/1920

    // Z — que ninguém corrigiu — não pode ter ganho a caixa nem a autoria de Y.
    await act(async () => {
      screen.getByRole('button', { name: 'Próximo item' }).click()
    })
    await disparaLoad()
    expect(screen.queryByTestId('badge-autoria')).toBeNull()
    expect(screen.getByTestId('caixa-violacao').getAttribute('style')).toContain('left: 2.6042%') // 50/1920, bbox original de Z
  })
})

// ── ux2/dedup — avisa sem decidir ───────────────────────────────────────────
//
// A fila JÁ reordena por rajada (bloco 1 acima) — o que esta rodada acrescenta
// é só o AVISO visível ("Rajada de N"), nunca uma mudança de comportamento:
// zero filtro, zero reordenação nova, zero propagação de veredito entre
// irmãos (decisão pendente, ver docblock de verification_service.py).

const R1 = item('r1', 'no_helmet', 0.9, { camera_id: 'cam-rajada', created_at: '2026-08-25T13:39:00Z' })
const R2 = item('r2', 'no_helmet', 0.91, { camera_id: 'cam-rajada', created_at: '2026-08-25T13:39:20Z' })

describe('rajada (ux2/dedup) — avisa sem decidir', () => {
  it('item com irmão de câmera+classe em <60s mostra "Rajada de 2"', async () => {
    get.mockResolvedValue(fila([R1, R2]))
    montar()
    await screen.findByText(/Rajada de 2/)
  })

  it('sem irmão de rajada, não mostra aviso nenhum', async () => {
    get.mockResolvedValue(fila([A]))
    montar()
    await screen.findByText('Sem capacete')
    expect(screen.queryByText(/Rajada de/)).toBeNull()
  })

  it('expandir revela os horários das N repetições — nunca esconde o dado', async () => {
    get.mockResolvedValue(fila([R1, R2]))
    montar()
    await screen.findByText(/Rajada de 2/)
    // <details> não esconde de verdade — o conteúdo já está no DOM, pronto
    // para expandir (regra de produto: nunca esconder de verdade).
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
  })

  it('julgar o item atual NÃO decide o irmão — cada rajada continua individual (decisão pendente)', async () => {
    get.mockResolvedValue(fila([R1, R2]))
    montar()
    await screen.findByText(/Rajada de 2/)
    tecla('c') // confirma r1 (item[0] do servidor) — atalho já testado no bloco 1
    await waitFor(() => expect(post).toHaveBeenCalledWith('/verification/r1/review', { verdict: 'approve' }))
    expect(post).not.toHaveBeenCalledWith('/verification/r2/review', expect.anything())
  })
})

// ── 12 · Procedência: quem desenhou a caixa que estou julgando ──────────────
// Issue #670, buraco achado na revisão do PR #713. Esta é a tela onde o
// operador JULGA, e era a única das CINCO superfícies que consomem o mesmo
// `violations` sem dizer quem desenhou a caixa. 4.609 dos 5.174 eventos do
// DEV são acervo semeado com caixa de PESSOA e chegam aqui pela fila
// (`get_human_queue` faz `SELECT a.*`, o JSONB vem cru): sem esta linha o
// operador dá veredito sobre encenação achando que julga o modelo.

const SEMEADO = item('s1', 'no_helmet', 0.61, {
  violations: [{ class: 'no_helmet', confidence: 0.61, origem: 'anotacao_humana', lote: 'acervo_rvb_2026_08' }],
})
const DO_MODELO = item('m1', 'no_helmet', 0.61, {
  violations: [{ class: 'no_helmet', confidence: 0.61, origem: 'modelo_onnx' }],
})

describe('a fila diz QUEM desenhou a caixa que se está julgando', () => {
  it('caixa desenhada por PESSOA no acervo semeado é anunciada como tal', async () => {
    get.mockResolvedValue(fila([SEMEADO]))
    montar()
    const selo = await screen.findByTestId('procedencia')
    expect(selo.textContent).toContain('anotação humana')
    expect(selo.textContent).toContain('demonstração')
  })

  it('caixa do MODELO é dita como do modelo, sem a ressalva de demonstração', async () => {
    get.mockResolvedValue(fila([DO_MODELO]))
    montar()
    const selo = await screen.findByTestId('procedencia')
    expect(selo.textContent).toContain('detecção do modelo')
    expect(selo.textContent).not.toContain('demonstração')
  })

  it('sem origem declarada, a tela não afirma nada — nenhuma linha de procedência', async () => {
    get.mockResolvedValue(fila([A]))
    montar()
    await screen.findByText('Sem capacete')
    expect(screen.queryByTestId('procedencia')).toBeNull()
  })
})
