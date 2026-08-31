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

import { Verificacao, incertezaDe, ordenarPorIncerteza, type ItemVerificacao } from './Verificacao'

// ── Dublês ──────────────────────────────────────────────────────────────────

const get = vi.fn()
const post = vi.fn()
vi.mock('../../services/api', () => ({
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
  },
}))

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
    // O servidor devolve por created_at DESC. Se a tela só repetir essa ordem,
    // o operador gasta o clique onde o modelo já acerta.
    get.mockResolvedValue(fila([A, B, C]))
    montar()
    expect(await screen.findByText('Sem colete')).toBeTruthy()
  })
})

// ── 2 · Avanço da fila ──────────────────────────────────────────────────────

describe('avanço da fila (PRs 496, 500, 487)', () => {
  it('veredito vai para o alerta na tela e avança para o próximo da ordem', async () => {
    get.mockResolvedValue(fila([A, B, C]))
    montar()
    await screen.findByText('Sem colete') // B, o mais duvidoso

    clicar(screen.getByRole('button', { name: /Confirmar/ }))

    expect(post).toHaveBeenCalledWith('/verification/b/review', { verdict: 'approve' })
    expect(await screen.findByText('Sem óculos')).toBeTruthy() // C, o seguinte
  })

  it('a tecla C decide o item CORRENTE, não o do primeiro render (ref atrasado)', async () => {
    // PR 496: listener registrado uma vez fica preso à closure do primeiro
    // render. O operador vê C na tela, aperta C, e o veredito cai em B.
    get.mockResolvedValue(fila([A, B, C]))
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

  it('a tecla R rejeita', async () => {
    get.mockResolvedValue(fila([B]))
    montar()
    await screen.findByText('Sem colete')

    tecla('r')
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/verification/b/review', { verdict: 'reject' }),
    )
  })

  it('reabastecimento ANEXA — não reordena a fila sob os olhos do operador', async () => {
    // PRs 487 e 500: o item decidido some do filtro `needs_human` no servidor, então
    // a leitura seguinte é OUTRO conjunto. Se o novo lote substituísse a fila (ou
    // fosse reordenado por incerteza junto com ela), a ordem mudaria sozinha no
    // meio da decisão.
    vi.useFakeTimers()
    get.mockResolvedValueOnce(fila([A, B])) //      ordem local: B, A
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
    get.mockResolvedValue(fila([A, B])) // as MESMAS duas linhas, de novo
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
    get.mockResolvedValue(fila([A, B]))
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
    get.mockResolvedValue(fila([A, B, C]))
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
    get.mockResolvedValueOnce(fila([A, B, C])) // ordem local: B, C, A
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
    get.mockResolvedValue({ success: true, message: 'OK', data: { items: [A, B], count: 2 } })
    montar()
    await screen.findByText('Sem colete')
    expect(screen.getByText('2 RESTANTES')).toBeTruthy()
  })

  it('decisão local desconta do total do servidor na hora, antes do próximo poll', async () => {
    // O servidor só sabe da minha decisão no PRÓXIMO sync (até 15s depois) —
    // sem descontar local, "N RESTANTES" ficaria travado no valor antigo por
    // até 15s após cada clique, mesmo com feedback visual de "Confirmado".
    get.mockResolvedValue(fila([A, B, C], 50)) // servidor diz 50, só 3 vieram no lote
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
