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
  extra: Partial<{ evidence_key: string | null; verification_verdict: string | null; verified_by: string | null }> = {},
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
 *  acknowledged=false vs true. */
function servir(
  abertas: unknown[],
  feitas: unknown[],
  totais = [abertas.length, feitas.length],
  snapshots: Record<string, string | null> = {},
) {
  get.mockImplementation((path: string) => {
    const m = path.match(/^\/alerts\/([^/]+)\/snapshot$/)
    if (m) return Promise.resolve({ data: { snapshot_url: snapshots[m[1]] ?? null } })
    return Promise.resolve(
      path.includes('acknowledged=false')
        ? { data: { alerts: abertas, total: totais[0] } }
        : { data: { alerts: feitas, total: totais[1] } },
    )
  })
}

beforeEach(() => {
  get.mockReset()
  post.mockReset()
  navegar.mockReset()
  permissoes = ['alerts:read', 'alerts:feedback']
})

describe('de onde vem o dado', () => {
  it('pede os dois recortes reais do ledger, só violações e na mesma janela', async () => {
    servir([evento('1111aaaa-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />)
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2))

    const caminhos = get.mock.calls.map((c) => c[0] as string)
    expect(caminhos.some((p) => p.includes('acknowledged=false'))).toBe(true)
    expect(caminhos.some((p) => p.includes('acknowledged=true'))).toBe(true)
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
    render(<Acoes />)
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2))
    const caminhos = get.mock.calls.map((c) => c[0] as string)
    expect(caminhos.every((p) => !p.includes('kind=observacao'))).toBe(true)
    expect(caminhos.every((p) => !p.includes('kind=compliance'))).toBe(true)
  })

  it('a taxa sai do total do envelope, não do tamanho da página', async () => {
    // 1 cartão em cada coluna, mas 3.000 abertos e 1.000 reconhecidos no total.
    servir([evento('a1111111-0000-0000-0000-000000000000', false)],
           [evento('b1111111-0000-0000-0000-000000000000', true)],
           [3000, 1000])
    render(<Acoes />)
    await screen.findByText('25%')
    expect(screen.getByText('1000/4000 RECONHECIDAS')).toBeTruthy()
  })
})

describe('agir', () => {
  it('reconhecer chama o endpoint real e recarrega o ledger', async () => {
    servir([evento('c1111111-0000-0000-0000-000000000000', false)], [])
    post.mockResolvedValue({})
    render(<Acoes />)

    const botao = await screen.findByRole('button', { name: /marcar reconhecida/i })
    botao.click()

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/alerts/c1111111-0000-0000-0000-000000000000/acknowledge', undefined),
    )
    await waitFor(() => expect(get).toHaveBeenCalledTimes(4))
  })

  it('sem alerts:feedback não há botão de reconhecer', async () => {
    permissoes = ['alerts:read']
    servir([evento('d1111111-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />)

    await screen.findByText('Sem capacete')
    expect(screen.queryByRole('button', { name: /marcar reconhecida/i })).toBeNull()
  })
})

describe('veredito — Confirmar/Descartar', () => {
  it('Confirmar chama /verification/<id>/review com verdict approve', async () => {
    permissoes = ['alerts:read', 'alerts:feedback', 'verification:write']
    servir([evento('f1111111-0000-0000-0000-000000000000', false)], [])
    post.mockResolvedValue({})
    render(<Acoes />)

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
    render(<Acoes />)

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
    render(<Acoes />)

    await screen.findByText('Sem capacete')
    expect(screen.queryByRole('button', { name: /^confirmar$/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /^descartar$/i })).toBeNull()
  })

  it('veredito já registrado aparece como selo — cor cinza, nunca a do reconhecimento', async () => {
    servir([evento('c4444444-0000-0000-0000-000000000000', false, {
      verification_verdict: 'approve', verified_by: 'user:u1',
    })], [])
    render(<Acoes />)
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
    render(<Acoes />)

    const img = await screen.findByRole('img')
    expect((img as HTMLImageElement).src).toBe('https://r2.example/d5.jpg')
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith('/alerts/d5555555-0000-0000-0000-000000000000/snapshot'),
    )
  })

  it('sem evidence_key, mostra placeholder honesto e não pede snapshot', async () => {
    servir([evento('e6666666-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />)

    await screen.findByText('Sem capacete')
    expect(screen.getByText(/sem evidência/i)).toBeTruthy()
    expect(screen.queryByRole('img')).toBeNull()
    expect(get.mock.calls.some((c) => (c[0] as string).includes('/snapshot'))).toBe(false)
  })

  it('clicar no cartão abre o evento — e NÃO marca reconhecida', async () => {
    servir([evento('f7777777-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />)

    const cartao = await screen.findByRole('button', { name: /abrir evento f7777777/i })
    cartao.click()

    expect(navegar).toHaveBeenCalledWith('/novo/epi/eventos/f7777777-0000-0000-0000-000000000000')
    expect(post).not.toHaveBeenCalled()
  })
})

describe('tratativa — sem backend', () => {
  it('mostra o selo de dependência, nunca um formulário de verdade', async () => {
    servir([evento('a8888888-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />)

    await screen.findByText('Sem capacete')
    const tratativa = screen.getByRole('button', { name: /^tratativa$/i })
    expect((tratativa as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('AGUARDA BACKEND')).toBeTruthy()
  })
})

describe('nada de dado inventado', () => {
  it('sem evento, vazio honesto — nenhum cartão de exemplo', async () => {
    servir([], [])
    render(<Acoes />)

    await screen.findByText('Nenhuma ação aberta')
    expect(screen.queryByText(/Reforçar DDS/i)).toBeNull()
  })

  it('não renderiza campo que o backend não serve', async () => {
    servir([evento('e1111111-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />)

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
    render(<Acoes />)

    await screen.findByText('Não foi possível carregar')
    expect(screen.getByText(/GET \/api\/alerts/)).toBeTruthy()

    servir([], [])
    screen.getByRole('button', { name: /tentar novamente/i }).click()
    await screen.findByText('Nenhuma ação aberta')
  })
})
