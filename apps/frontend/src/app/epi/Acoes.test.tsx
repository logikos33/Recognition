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
 *  · sem `alerts:feedback` não há botão de ação;
 *  · sem evento, vazio honesto — nunca cartão de exemplo;
 *  · nenhum campo sem backend aparece na tela.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Acoes } from './Acoes'

const get = vi.fn()
const post = vi.fn()
vi.mock('../../services/api', () => ({ api: { get: (p: string) => get(p), post: (p: string) => post(p) } }))

let permissoes: string[] = []
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ can: (p: string) => permissoes.includes(p) }),
}))

const evento = (id: string, acknowledged: boolean) => ({
  id,
  camera_id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
  camera_name: 'CAM-04',
  violations: [{ class: 'no_helmet' }],
  acknowledged,
  created_at: '2026-08-20T14:32:00Z',
})

/** Responde por recorte: o que a tela pedir com acknowledged=false vs true. */
function servir(abertas: unknown[], feitas: unknown[], totais = [abertas.length, feitas.length]) {
  get.mockImplementation((path: string) =>
    Promise.resolve(
      path.includes('acknowledged=false')
        ? { data: { alerts: abertas, total: totais[0] } }
        : { data: { alerts: feitas, total: totais[1] } },
    ),
  )
}

beforeEach(() => {
  get.mockReset()
  post.mockReset()
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
      expect(post).toHaveBeenCalledWith('/alerts/c1111111-0000-0000-0000-000000000000/acknowledge'),
    )
    await waitFor(() => expect(get).toHaveBeenCalledTimes(4))
  })

  it('sem alerts:feedback não há botão de ação', async () => {
    permissoes = ['alerts:read']
    servir([evento('d1111111-0000-0000-0000-000000000000', false)], [])
    render(<Acoes />)

    await screen.findByText('Sem capacete')
    expect(screen.queryByRole('button', { name: /marcar reconhecida/i })).toBeNull()
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
