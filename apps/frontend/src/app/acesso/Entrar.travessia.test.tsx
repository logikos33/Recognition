/**
 * A TRAVESSIA: senha temporária → produto, cruzando a fronteira HTTP.
 *
 * Por que este arquivo existe, tendo `Entrar.test.tsx` ao lado: aquele
 * arquivo mocka `useAuth().login`. Ele prova o que a TELA faz quando já lhe
 * entregam um `ApiError` com `code`. Não prova nada sobre quem entrega —
 * `api.ts` (que lê `error_code` do envelope) e `useAuth.login` (que
 * repassa o erro em vez de embrulhar) ficam ambos fora da medição. São
 * exatamente as duas peças no meio do caminho: se qualquer uma parar de
 * carregar o `error_code`, os 6 casos de lá seguem VERDES e a pessoa com
 * senha no papel volta a ficar presa na tela de login.
 *
 * Aqui só o `fetch` é dublê. Do clique em "Entrar" até o token no
 * armazenamento, é o código de produção inteiro — a mesma travessia que os
 * três acessos novos do RVB fazem na segunda-feira.
 *
 * Regra da casa: valor que o cliente vê precisa de teste que cruza a
 * fronteira HTTP.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Entrar } from './Entrar'

/** jsdom desta config expõe `localStorage` OCO — ver App.test.tsx. */
const armazenado = new Map<string, string>()
Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: {
    getItem: (k: string) => armazenado.get(k) ?? null,
    setItem: (k: string, v: string) => void armazenado.set(k, v),
    removeItem: (k: string) => void armazenado.delete(k),
    clear: () => armazenado.clear(),
  },
})

/** `useAuth.login` navega com `window.location.href` — jsdom não navega. */
const local = { href: '/novo/entrar' }
Object.defineProperty(window, 'location', { configurable: true, value: local })

type Chamada = { path: string; body: Record<string, unknown> }
const chamadas: Chamada[] = []

const json = (status: number, corpo: unknown) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(corpo) } as Response)

/** Envelope REAL do backend: `error()` de `app/core/responses.py`. */
const CORPO_403 = {
  success: false,
  error:
    'Sua senha é temporária e precisa ser trocada antes do primeiro acesso. '
    + 'Defina uma nova senha em POST /api/auth/change-password '
    + '(e-mail, senha atual e nova senha).',
  error_code: 'password_change_required',
}
const CORPO_LOGIN_OK = {
  success: true,
  data: { token: 'jwt-de-verdade', user: { id: 'u1', email: 'ana@rvb.com.br', role: 'operator' } },
}

/**
 * `fetch` no lugar da API: responde por rota + senha, como o backend responde.
 * A senha temporária MORRE na troca (o backend limpa o hash antigo) — sem
 * isso o dublê aceitaria para sempre a senha do papel e o teste não veria a
 * diferença entre "trocou" e "fingiu que trocou".
 */
let senhaValida = 'senha-do-papel'
let trocaPendente = true

const apiFalsa = vi.fn((url: string, init?: RequestInit) => {
  const path = String(url).replace('/api', '')
  const body = JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown>
  chamadas.push({ path, body })

  if (path === '/auth/change-password') {
    if (body.current_password !== senhaValida) return json(401, { success: false, error: 'Credenciais inválidas' })
    if (String(body.new_password ?? '').length < 6) return json(400, { success: false, error: 'Senha: mínimo 6 caracteres' })
    senhaValida = String(body.new_password)
    trocaPendente = false
    return json(200, { success: true, message: 'Senha alterada. Faça login com a nova senha.' })
  }
  if (path === '/auth/login') {
    if (body.password !== senhaValida) return json(401, { success: false, error: 'Credenciais inválidas' })
    if (trocaPendente) return json(403, CORPO_403)
    return json(200, CORPO_LOGIN_OK)
  }
  return json(404, { success: false, error: 'Rota não encontrada' })
})

beforeEach(() => {
  armazenado.clear()
  chamadas.length = 0
  senhaValida = 'senha-do-papel'
  trocaPendente = true
  local.href = '/novo/entrar'
  vi.stubGlobal('fetch', apiFalsa)
})

const entrarCom = (senha: string) => {
  fireEvent.change(screen.getByPlaceholderText('voce@empresa.com.br'), {
    target: { value: 'ana@rvb.com.br' },
  })
  fireEvent.change(screen.getByPlaceholderText('••••••••'), { target: { value: senha } })
  fireEvent.click(screen.getByRole('button', { name: 'Entrar' }))
}

const trocarPara = async (nova: string, repetida = nova) => {
  fireEvent.change(await screen.findByLabelText('Nova senha'), { target: { value: nova } })
  fireEvent.change(screen.getByLabelText('Repita a nova senha'), { target: { value: repetida } })
  fireEvent.click(screen.getByRole('button', { name: 'Salvar e entrar' }))
}

describe('senha temporária — a travessia inteira, sem mockar o caminho', () => {
  it('403 do servidor vira formulário de nova senha, e a troca entrega o produto', async () => {
    render(<MemoryRouter><Entrar /></MemoryRouter>)
    entrarCom('senha-do-papel')

    // 1. O 403 com `error_code` atravessou api.ts e useAuth e virou tela.
    expect(await screen.findByLabelText('Nova senha')).toBeTruthy()
    // Nada de tripa de protocolo na tela de quem opera a fábrica.
    expect(screen.queryByText(/POST \/api/)).toBeNull()
    expect(screen.queryByText(/403/)).toBeNull()

    await trocarPara('minha-senha-nova')

    // 2. Terminou DENTRO do produto: token guardado e navegação disparada.
    await waitFor(() => expect(localStorage.getItem('token')).toBe('jwt-de-verdade'))
    expect(local.href).toBe('/novo/')

    // 3. A ordem real das três chamadas — a do meio é a que faltava no produto.
    expect(chamadas.map((c) => c.path)).toEqual([
      '/auth/login', '/auth/change-password', '/auth/login',
    ])
    expect(chamadas[1].body).toEqual({
      email: 'ana@rvb.com.br',
      current_password: 'senha-do-papel',
      new_password: 'minha-senha-nova',
    })
    // O 2º login usa a senha NOVA: a temporária já não vale no servidor.
    expect(chamadas[2].body).toEqual({ email: 'ana@rvb.com.br', password: 'minha-senha-nova' })
  })

  it('enquanto a troca não acontece, NENHUM token é emitido — não há atalho', async () => {
    render(<MemoryRouter><Entrar /></MemoryRouter>)
    entrarCom('senha-do-papel')
    await screen.findByLabelText('Nova senha')

    // A porta do produto é o token. Com a troca pendente ele não existe, e
    // por isso não há URL a digitar: sem token o App inteiro é a tela de
    // login (o `path="*"` deslogado de App.tsx).
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
    expect(local.href).toBe('/novo/entrar')
  })

  it('senha nova recusada pelo servidor não emite token nem inventa sucesso', async () => {
    render(<MemoryRouter><Entrar /></MemoryRouter>)
    entrarCom('senha-do-papel')
    // O backend recusa `new_password` com menos de 6 (auth/routes.py) — aqui
    // a recusa vem do servidor, não do `minLength` do input.
    await trocarPara('123')

    expect(await screen.findByText('Senha: mínimo 6 caracteres')).toBeTruthy()
    expect(localStorage.getItem('token')).toBeNull()
    expect(local.href).toBe('/novo/entrar')
  })

  it('contraprova: 401 de senha errada NÃO abre a troca (o desvio é do error_code, não do status)', async () => {
    render(<MemoryRouter><Entrar /></MemoryRouter>)
    entrarCom('chutei')
    expect(await screen.findByText('Credenciais inválidas')).toBeTruthy()
    expect(screen.queryByLabelText('Nova senha')).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
  })
})
