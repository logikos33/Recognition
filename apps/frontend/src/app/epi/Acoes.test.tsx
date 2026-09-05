/**
 * O que se protege aqui é a HONESTIDADE da tela, não o layout.
 *
 * O desenho pede um controle de ações corretivas que o backend não tem. A
 * tentação óbvia — e o jeito de mentir para o cliente — é preencher
 * responsável/prazo/"Nova ação" com dado plausível. Estes testes travam isso:
 *
 *  · os recortes pedidos são os REAIS do ledger de reconhecimento;
 *  · a taxa vem do `total` do envelope, não do tamanho da página (com 50 por
 *    página, contar cartões daria 100% num tenant com 4.000 eventos abertos);
 *  · reconhecer chama o endpoint que existe e recarrega;
 *  · sem `alerts:feedback` não há botão de reconhecer;
 *  · sem evento, vazio honesto — nunca cartão de exemplo;
 *  · nenhum campo sem backend aparece na tela (só o selo de "aguarda backend");
 *
 * E o que esta rodada (contrato A5/T4) acrescenta:
 *
 *  · o cartão mostra a miniatura da evidência (mesma fonte do EventoDetalhe,
 *    pelo endpoint leve /snapshot) e nunca inventa imagem quando não há uma;
 *  · o cartão INTEIRO abre o evento — e abrir NUNCA chama /acknowledge nem
 *    /review sozinho, só navega;
 *  · Confirmar/Descartar chamam /verification/<id>/review com o verdict
 *    certo, e só aparecem com `verification:write`.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, navegar } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  navegar: vi.fn(),
}))

vi.mock('../../services/api', () => ({ api: { get: (p: string) => get(p), post: (p: string, b?: unknown) => post(p, b) } }))

vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<Record<string, unknown>>('react-router-dom')
  return { ...real, useNavigate: () => navegar }
})

let permissoes: string[] = []
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ can: (p: string) => permissoes.includes(p) }),
}))

import { Acoes } from './Acoes'

const evento = (
  id: string,
  acknowledged: boolean,
  extra: Partial<{
    evidence_key: string | null
    verification_verdict: string | null
    verified_by: string | null
    /** ux2/dedup: sobrescrever pra montar rajadas (mesma câmera+classe, gap
     *  específico) ou provar que gap > 60s NÃO agrupa. */
    created_at: string
    camera_id: string
  }> = {},
) => ({
  id,
  camera_id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
  camera_name: 'CAM-04',
  violations: [{ class: 'no_helmet' }],
  acknowledged,
  created_at: '2026-08-20T14:32:00Z',
  evidence_key: null,
  verification_verdict: null,
  verified_by: null,
  ...extra,
})

/** Responde por recorte: o snapshot de UM alerta, ou o que a tela pedir com
 *  acknowledged=false vs true vs o 3º pedido (união, sem `acknowledged`,
 *  QUEBRA 3 — fonte do denominador). `situacoes` (ux2/dedup) default =
 *  `totais` — sem passar nada, o comportamento é IDÊNTICO ao de antes desta
 *  rodada (situTotal === total, texto "N/M RECONHECIDAS" sem "SITUAÇÕES").
 *  `situacaoUniao` default = soma dos dois — só testes que provam o fix da
 *  QUEBRA 3 (rajada parcialmente reconhecida) passam um valor diferente da
 *  soma, de propósito. */
function servir(
  abertas: unknown[],
  feitas: unknown[],
  totais = [abertas.length, feitas.length],
  snapshots: Record<string, string | null> = {},
  situacoes: [number, number] = totais as [number, number],
  situacaoUniao = situacoes[0] + situacoes[1],
) {
  get.mockImplementation((path: string) => {
    const m = path.match(/^\/alerts\/([^/]+)\/snapshot$/)
    if (m) return Promise.resolve({ data: { snapshot_url: snapshots[m[1]] ?? null } })
    if (path.includes('acknowledged=false')) {
      return Promise.resolve({ data: { alerts: abertas, total: totais[0], total_situacoes: situacoes[0] } })
    }
    if (path.includes('acknowledged=true')) {
      return Promise.resolve({ data: { alerts: feitas, total: totais[1], total_situacoes: situacoes[1] } })
    }
    return Promise.resolve({
      data: { alerts: [], total: totais[0] + totais[1], total_situacoes: situacaoUniao },
    })
  })
}

beforeEach(() => {
  get.mockReset()
  post.mockReset()
  navegar.mockReset()
  permissoes = ['alerts:read', 'alerts:feedback']
})

describe('de onde vem o dado', () => {
  it('pede os TRÊS recortes reais do ledger (aberto/feito/união), só violações e na mesma janela', async () => {
    servir([evento('1111aaaa-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />, { wrapper: MemoryRouter })
    await waitFor(() => expect(get).toHaveBeenCalledTimes(3))

    const caminhos = get.mock.calls.map((c) => c[0] as string)
    expect(caminhos.some((p) => p.includes('acknowledged=false'))).toBe(true)
    expect(caminhos.some((p) => p.includes('acknowledged=true'))).toBe(true)
    // QUEBRA 3: 3º pedido sem `acknowledged` — fonte do denominador de
    // situações (não soma os dois recortes isolados, pede a união pronta).
    expect(caminhos.some((p) => !p.includes('acknowledged='))).toBe(true)
    // ADR-0065: conformidade é telemetria — não se age sobre quem está certo.
    expect(caminhos.every((p) => p.startsWith('/alerts?') && p.includes('kind=violation'))).toBe(true)
    expect(caminhos.every((p) => p.includes('start_date='))).toBe(true)
  })

  it('QUEBRA 3 — fila de ação não pede a classe indecidida por padrão (decisão registrada)', async () => {
    // Contrato A1 também tira 'observacao' (classe indecidida) da fila —
    // decisão escrita no topo de Acoes.tsx: o backend não tem um `kind`
    // "violação + indecidida, sem conformidade", e trocar para '' (todos)
    // reabriria a fila de AÇÃO com conformidade dentro de novo. O indecidido
    // não some do produto — tem filtro próprio em /epi/eventos.
    servir([evento('1111aaaa-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />, { wrapper: MemoryRouter })
    await waitFor(() => expect(get).toHaveBeenCalledTimes(3))
    const caminhos = get.mock.calls.map((c) => c[0] as string)
    expect(caminhos.every((p) => !p.includes('kind=observacao'))).toBe(true)
    expect(caminhos.every((p) => !p.includes('kind=compliance'))).toBe(true)
  })

  it('a taxa sai do total do envelope, não do tamanho da página', async () => {
    // 1 cartão em cada coluna, mas 3.000 abertos e 1.000 reconhecidos no total.
    servir([evento('a1111111-0000-0000-0000-000000000000', false)],
           [evento('b1111111-0000-0000-0000-000000000000', true)],
           [3000, 1000])
    render(<Acoes />, { wrapper: MemoryRouter })
    await screen.findByText('25%')
    expect(screen.getByText('1000/4000 RECONHECIDAS')).toBeTruthy()
  })
})

describe('agir', () => {
  it('reconhecer chama o endpoint real e recarrega o ledger', async () => {
    servir([evento('c1111111-0000-0000-0000-000000000000', false)], [])
    post.mockResolvedValue({})
    render(<Acoes />, { wrapper: MemoryRouter })

    const botao = await screen.findByRole('button', { name: /marcar reconhecida/i })
    botao.click()

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/alerts/c1111111-0000-0000-0000-000000000000/acknowledge', undefined),
    )
    await waitFor(() => expect(get).toHaveBeenCalledTimes(6))
  })

  it('sem alerts:feedback não há botão de reconhecer', async () => {
    permissoes = ['alerts:read']
    servir([evento('d1111111-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />, { wrapper: MemoryRouter })

    await screen.findByText('Sem capacete')
    expect(screen.queryByRole('button', { name: /marcar reconhecida/i })).toBeNull()
  })
})

describe('veredito — Confirmar/Descartar', () => {
  it('Confirmar chama /verification/<id>/review com verdict approve', async () => {
    permissoes = ['alerts:read', 'alerts:feedback', 'verification:write']
    servir([evento('f1111111-0000-0000-0000-000000000000', false)], [])
    post.mockResolvedValue({})
    render(<Acoes />, { wrapper: MemoryRouter })

    const botao = await screen.findByRole('button', { name: /^confirmar$/i })
    botao.click()

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/verification/f1111111-0000-0000-0000-000000000000/review',
        { verdict: 'approve' },
      ),
    )
    // Veredito é eixo próprio: não chama /acknowledge.
    expect(post).not.toHaveBeenCalledWith(expect.stringContaining('/acknowledge'), expect.anything())
  })

  it('Descartar chama /verification/<id>/review com verdict reject', async () => {
    permissoes = ['alerts:read', 'alerts:feedback', 'verification:write']
    servir([evento('a2222222-0000-0000-0000-000000000000', false)], [])
    post.mockResolvedValue({})
    render(<Acoes />, { wrapper: MemoryRouter })

    const botao = await screen.findByRole('button', { name: /^descartar$/i })
    botao.click()

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/verification/a2222222-0000-0000-0000-000000000000/review',
        { verdict: 'reject' },
      ),
    )
  })

  it('sem verification:write não há Confirmar/Descartar', async () => {
    permissoes = ['alerts:read', 'alerts:feedback']
    servir([evento('b3333333-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />, { wrapper: MemoryRouter })

    await screen.findByText('Sem capacete')
    expect(screen.queryByRole('button', { name: /^confirmar$/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /^descartar$/i })).toBeNull()
  })

  it('veredito já registrado aparece como selo — cor cinza, nunca a do reconhecimento', async () => {
    servir([evento('c4444444-0000-0000-0000-000000000000', false, {
      verification_verdict: 'approve', verified_by: 'user:u1',
    })], [])
    render(<Acoes />, { wrapper: MemoryRouter })
    await screen.findByText('Procedente')
  })
})

describe('evidência — miniatura e abrir o evento', () => {
  it('com evidence_key, pede o snapshot e mostra a miniatura', async () => {
    servir(
      [evento('d5555555-0000-0000-0000-000000000000', false, { evidence_key: 'frames/d5.jpg' })],
      [],
      undefined,
      { 'd5555555-0000-0000-0000-000000000000': 'https://r2.example/d5.jpg' },
    )
    render(<Acoes />, { wrapper: MemoryRouter })

    const img = await screen.findByRole('img')
    expect((img as HTMLImageElement).src).toBe('https://r2.example/d5.jpg')
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith('/alerts/d5555555-0000-0000-0000-000000000000/snapshot'),
    )
  })

  it('sem evidence_key, mostra placeholder honesto e não pede snapshot', async () => {
    servir([evento('e6666666-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />, { wrapper: MemoryRouter })

    await screen.findByText('Sem capacete')
    expect(screen.getByText(/sem evidência/i)).toBeTruthy()
    expect(screen.queryByRole('img')).toBeNull()
    expect(get.mock.calls.some((c) => (c[0] as string).includes('/snapshot'))).toBe(false)
  })

  it('clicar no cartão abre o evento — e NÃO marca reconhecida', async () => {
    servir([evento('f7777777-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />, { wrapper: MemoryRouter })

    const cartao = await screen.findByRole('button', { name: /abrir evento f7777777/i })
    cartao.click()

    expect(navegar).toHaveBeenCalledWith('/novo/epi/eventos/f7777777-0000-0000-0000-000000000000')
    expect(post).not.toHaveBeenCalled()
  })
})

describe('tratativa — sem backend', () => {
  it('mostra o selo de dependência, nunca um formulário de verdade', async () => {
    servir([evento('a8888888-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />, { wrapper: MemoryRouter })

    await screen.findByText('Sem capacete')
    const tratativa = screen.getByRole('button', { name: /^tratativa$/i })
    expect((tratativa as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('AGUARDA BACKEND')).toBeTruthy()
  })
})

describe('nada de dado inventado', () => {
  it('sem evento, vazio honesto — nenhum cartão de exemplo', async () => {
    servir([], [])
    render(<Acoes />, { wrapper: MemoryRouter })

    await screen.findByText('Nenhuma ação aberta')
    expect(screen.queryByText(/Reforçar DDS/i)).toBeNull()
  })

  it('não renderiza campo que o backend não serve', async () => {
    servir([evento('e1111111-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />, { wrapper: MemoryRouter })

    await screen.findByText('Sem capacete')
    // A nota é o ÚNICO lugar onde essas palavras podem aparecer — e lá elas
    // estão dizendo que o campo não existe, não fingindo um valor.
    const nota = screen.getByText(/ainda não existe no backend/i)
    for (const inventado of [/respons[áa]vel/i, /prazo/i, /vencid/i, /nova a[çc][ãa]o/i, /minhas a[çc][õo]es/i]) {
      expect(screen.queryAllByText(inventado).filter((el) => el !== nota)).toEqual([])
    }
  })

  it('erro mostra o endpoint REAL e deixa tentar de novo', async () => {
    get.mockRejectedValue(new Error('timeout'))
    render(<Acoes />, { wrapper: MemoryRouter })

    await screen.findByText('Não foi possível carregar')
    expect(screen.getByText(/GET \/api\/alerts/)).toBeTruthy()

    servir([], [])
    screen.getByRole('button', { name: /tentar novamente/i }).click()
    await screen.findByText('Nenhuma ação aberta')
  })
})

// ---------------------------------------------------------------------------
// ux2/dedup — "cartões repetem a mesma cena; o contador ('1/66
// reconhecidas') tem de contar situações, não linhas".
// ---------------------------------------------------------------------------

describe('rajada (ux2/dedup) — cartão não repete a mesma cena', () => {
  it('2 eventos da MESMA câmera+classe (mesmo minuto) viram 1 cartão + alternador "+1 repetição"', async () => {
    servir(
      [
        evento('11111111-0000-0000-0000-000000000001', false),
        evento('11111111-0000-0000-0000-000000000002', false),
      ],
      [],
    )
    render(<Acoes />, { wrapper: MemoryRouter })
    await screen.findByText(/\+1 repetiç/)
    // Só 1 cartão de verdade na tela, não 2 — "EVENTO <id>" só aparece 1x.
    expect(screen.getAllByText(/^EVENTO 1{8}/)).toHaveLength(1)
  })

  it('expandir revela a repetição, e ela mantém a PRÓPRIA ação de reconhecer', async () => {
    servir(
      [
        evento('22222222-0000-0000-0000-000000000001', false),
        evento('22222222-0000-0000-0000-000000000002', false),
      ],
      [],
    )
    render(<Acoes />, { wrapper: MemoryRouter })
    const alternador = await screen.findByText(/\+1 repetiç/)
    alternador.click()
    // Representante ("Marcar reconhecida") + repetição ("Reconhecer", sem o
    // texto "Marcar") — as DUAS ações continuam disponíveis, nada escondido.
    await waitFor(() => expect(screen.getByRole('button', { name: /^reconhecer$/i })).toBeTruthy())
    expect(screen.getByRole('button', { name: /marcar reconhecida/i })).toBeTruthy()
  })

  it('gap > 60s NÃO agrupa — cada evento continua com o próprio cartão', async () => {
    servir(
      [
        evento('44444444-0000-0000-0000-000000000001', false, { created_at: '2026-08-25T13:00:00Z' }),
        evento('44444444-0000-0000-0000-000000000002', false, { created_at: '2026-08-25T13:05:00Z' }),
      ],
      [],
    )
    render(<Acoes />, { wrapper: MemoryRouter })
    await screen.findAllByText(/^EVENTO 44444444/)
    expect(screen.getAllByText(/^EVENTO 44444444/)).toHaveLength(2)
    expect(screen.queryByText(/repetiç/)).toBeNull()
  })

  it('badge da coluna e taxa contam SITUAÇÕES (total_situacoes), não linhas', async () => {
    servir(
      [evento('33333333-0000-0000-0000-000000000001', false)],
      [evento('33333333-0000-0000-0000-000000000002', true)],
      [66, 10],
      {},
      [2, 1],
    )
    render(<Acoes />, { wrapper: MemoryRouter })
    await screen.findByText('1/3 SITUAÇÕES RECONHECIDAS · 10/76 eventos')
  })

  it('QUEBRA 3 — rajada parcialmente reconhecida NÃO infla o denominador (soma ≠ união)', async () => {
    // aberto=2 situações, feito=2 situações — SE o denominador fosse a soma
    // (bug antigo), daria 4. A união real (3º pedido) é 3: uma das rajadas
    // atravessa os dois estados (parte reconhecida, parte não) e conta 1 vez
    // só ali. O texto tem de usar 3, nunca 4.
    servir(
      [evento('66666666-0000-0000-0000-000000000001', false)],
      [evento('66666666-0000-0000-0000-000000000002', true)],
      [5, 5],
      {},
      [2, 2],
      3,
    )
    render(<Acoes />, { wrapper: MemoryRouter })
    await screen.findByText('2/3 SITUAÇÕES RECONHECIDAS · 5/10 eventos')
    expect(screen.queryByText(/2\/4 SITUAÇÕES/)).toBeNull()
  })

  it('sem total_situacoes no payload (backend/mock antigo), cai pro texto de linhas de sempre', async () => {
    get.mockImplementation((path: string) =>
      Promise.resolve(
        path.includes('acknowledged=false')
          ? { data: { alerts: [evento('55555555-0000-0000-0000-000000000001', false)], total: 1 } }
          : { data: { alerts: [], total: 0 } },
      ),
    )
    render(<Acoes />, { wrapper: MemoryRouter })
    await screen.findByText('0/1 RECONHECIDAS')
    expect(screen.queryByText(/SITUAÇÕES/)).toBeNull()
  })
})
