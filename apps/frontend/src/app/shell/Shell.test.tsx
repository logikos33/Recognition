/**
 * Shell — o que não pode regredir.
 *
 * O foco aqui é o que MACHUCA em produção, não a existência de `<div>`:
 * navegação que mostra o que o perfil não pode abrir, rótulo que some do leitor
 * de tela ao recolher a sidebar, e aviso de sessão disparado com prazo que não
 * existe.
 */
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const auth = vi.hoisted(() => ({
  can: vi.fn((_p: string) => true),
  isSuperAdmin: false,
  logout: vi.fn(),
}))
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => auth }))

// O sino (NotificationBell) monta na topbar do shell novo e busca alertas ao
// montar. Sem o dublê, todo teste deste arquivo faria rede de verdade.
const get = vi.fn()
vi.mock('../../services/api', () => ({ api: { get: (...a: unknown[]) => get(...a) } }))

const sessao = vi.hoisted(() => ({ exp: vi.fn<() => number | null>(() => null) }))
// O SeletorTenant, montado na topbar, também consome este módulo. O dublê
// precisa cobrir a superfície inteira: um export faltando aqui derruba o Shell
// por completo, e o erro aponta para o teste, não para a causa.
vi.mock('../../services/tenantContext', () => ({
  getSessionTokenExpMs: sessao.exp,
  isInTenantContext: () => true, // com contexto o seletor não aparece
  listAvailableTenants: vi.fn(async () => []),
  assumeTenantContext: vi.fn(),
}))

import { Shell } from './Shell'

/** Uma tela que estoura no render — o caso do ErrorBoundary. */
function TelaQueEstoura(): never {
  throw new Error('boom da tela')
}

function montar(rota = '/novo/epi/live', extras?: ReactNode) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter initialEntries={[rota]}>
        <Routes>
          <Route path="/novo" element={<Shell />}>
            <Route path="epi/live" element={<p>conteúdo da tela</p>} />
            <Route path="epi/dashboard" element={<p>painel de verdade</p>} />
            <Route path="epi/eventos" element={<p>tela NOVA de eventos</p>} />
            {extras}
          </Route>
          {/* O endereço do front ANTIGO existe de verdade no app. Se o sino
              mandar para cá, o teste mostra o nome desta tela. */}
          <Route path="/epi/alerts" element={<p>tela ANTIGA de alertas</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  auth.can.mockReset()
  auth.can.mockReturnValue(true)
  auth.logout.mockReset()
  sessao.exp.mockReset()
  sessao.exp.mockReturnValue(null)
  get.mockReset()
  get.mockResolvedValue({ data: { alerts: [], total: 0, total_situacoes: 0 } })
})

describe('Shell', () => {
  it('renderiza a tela filha pelo Outlet', () => {
    montar()
    expect(screen.getByText('conteúdo da tela')).toBeTruthy()
  })

  it('esconde da navegação o que o perfil não pode abrir', () => {
    // Um viewer sem verification:read não pode receber atalho para a fila de
    // verificação: menu não é decoração, é superfície de acesso.
    auth.can.mockImplementation((p: string) => p !== 'verification:read')
    montar()
    expect(screen.queryByRole('link', { name: /verifica/i })).toBeNull()
  })

  it('sem permissão nenhuma, sobra só o que não exige permissão', () => {
    // Dashboard é a tela de pouso e não exige permissão (permissao: null);
    // todo o resto some. Se este número subir, alguém pôs uma tela sensível
    // com permissao: null. LOGIKOS é o logo do topbar (F5-LEVE item 1): link
    // para a home, sempre presente, independente de permissão.
    auth.can.mockReturnValue(false)
    montar()
    const nomes = screen.queryAllByRole('link').map((a) => a.textContent?.trim())
    expect(nomes).toEqual(['LOGIKOS', 'Dashboard'])
  })

  it('o logo é um link para a home do usuário', () => {
    // isSuperAdmin: false no dublê → home é a escolha de módulo.
    montar()
    expect(screen.getByRole('link', { name: 'LOGIKOS' }).getAttribute('href')).toBe(
      '/novo/modules',
    )
  })

  it('o menu do front novo aponta para DENTRO do prefixo', () => {
    // `/epi/dashboard` é rota válida nos DOIS fronts. Sem o prefixo, o menu do
    // front novo levaria calado para a tela antiga.
    montar()
    for (const link of screen.getAllByRole('link')) {
      expect(link.getAttribute('href')).toMatch(/^\/novo\//)
    }
  })

  it('ao recolher, o rótulo continua legível para leitor de tela', async () => {
    // A sidebar colapsada some com o TEXTO, não com a informação. Trocar por
    // `display:none` deixaria a navegação inteira anônima para quem usa leitor.
    montar()
    const antes = screen.getAllByRole('link')[0]
    const rotulo = antes.textContent
    fireEvent.click(screen.getByRole('button', { name: /recolher menu/i }))
    // Continua no DOM (escondido por clip-path), logo continua no nome
    // acessível do link. `display:none` faria este texto sumir.
    expect(screen.getAllByRole('link')[0].textContent).toContain(rotulo?.trim())
  })

  it('não avisa de expiração quando não há prazo legível no token', () => {
    // `getSessionTokenExpMs()` devolve null quando o JWT não decodifica.
    // Renderizar o aviso com prazo inventado ensinaria o operador a ignorá-lo.
    sessao.exp.mockReturnValue(null)
    montar()
    expect(screen.queryByText(/sess/i)).toBeNull()
  })

  it('avisa quando a sessão está perto de acabar', () => {
    sessao.exp.mockReturnValue(Date.now() + 60_000)
    montar()
    expect(screen.getByRole('button', { name: /entrar de novo/i })).toBeTruthy()
  })

  it('abre a paleta pelo botão da topbar', async () => {
    montar()
    fireEvent.click(screen.getByRole('button', { name: /buscar/i }))
    expect(screen.getByRole('dialog')).toBeTruthy()
  })
})


/**
 * (1) Tela branca. O `Suspense` do shell cobre o vão do `lazy()`, mas NÃO cobre
 * erro: um `throw` no render de qualquer tela do front novo, ou um pedaço que
 * não baixa (deploy no meio da sessão), sobe até a raiz e o React desmonta a
 * árvore INTEIRA — o usuário fica com a página em branco, sem topbar, sem menu,
 * sem nada em que clicar. Medido: o ErrorBoundary só envolvia o front ANTIGO.
 */
describe('tela que estoura não vira página em branco', () => {
  let erroDoConsole: ReturnType<typeof vi.spyOn>
  beforeEach(() => {
    // React grita o erro capturado pelo boundary; o teste espera o erro.
    erroDoConsole = vi.spyOn(console, 'error').mockImplementation(() => {})
  })
  afterEach(() => erroDoConsole.mockRestore())

  it('mostra a tela de erro e mantém o chrome do shell em pé', () => {
    montar('/novo/estoura', <Route path="estoura" element={<TelaQueEstoura />} />)
    // Não é branco: há uma tela de erro de verdade.
    expect(screen.getByText(/erro inesperado/i)).toBeTruthy()
    // E o caminho de volta continua na tela: logo (link pra home) e a nav.
    expect(screen.getByRole('link', { name: 'LOGIKOS' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /dashboard/i })).toBeTruthy()
  })

  it('navegar pela nav SAI da tela de erro — o boundary não vira beco sem saída', () => {
    // Sem reset por rota, `hasError` fica true para sempre: a URL muda, a tela
    // de erro não. O usuário só escapa dando F5.
    montar('/novo/estoura', <Route path="estoura" element={<TelaQueEstoura />} />)
    expect(screen.getByText(/erro inesperado/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('link', { name: /dashboard/i }))
    expect(screen.getByText('painel de verdade')).toBeTruthy()
    expect(screen.queryByText(/erro inesperado/i)).toBeNull()
  })
})

/**
 * (2) O aviso de sessão prometia "Renovar sessão" e chamava `location.reload()`
 * — recarregar com o MESMO token. Não existe rota de refresh no backend
 * (`services/api/app/api/v1/auth/routes.py`: register, login, me,
 * forgot-password, reset-password). Enquanto ela não existir (issue aberta), o
 * aviso diz a verdade.
 */
describe('aviso de sessão não promete renovação que não existe', () => {
  it('não oferece "Renovar sessão"', () => {
    sessao.exp.mockReturnValue(Date.now() + 60_000)
    montar()
    expect(screen.queryByRole('button', { name: /renovar/i })).toBeNull()
  })

  it('"Entrar de novo" derruba o token e leva ao login (não recarrega com o mesmo)', () => {
    sessao.exp.mockReturnValue(Date.now() + 60_000)
    montar()
    fireEvent.click(screen.getByRole('button', { name: /entrar de novo/i }))
    expect(auth.logout).toHaveBeenCalledTimes(1)
  })
})

/**
 * (3) O sino. Ele existe e faz dedup de rajada desde a ux2 — mas só era montado
 * na `TopBar` do layout ANTIGO. Quem usa o front novo não tinha sino nenhum.
 */
describe('sino de notificações no shell novo', () => {
  it('está na topbar de quem pode ler alertas', async () => {
    montar()
    expect(await screen.findByLabelText('Notificações')).toBeTruthy()
  })

  it('some para quem não tem alerts:read — sino que leva a 403 é pior que sino ausente', () => {
    auth.can.mockImplementation((p: string) => p !== 'alerts:read')
    montar()
    expect(screen.queryByLabelText('Notificações')).toBeNull()
  })

  it('clicar na notificação abre a tela NOVA de eventos, não a antiga', async () => {
    get.mockResolvedValue({
      data: {
        alerts: [{
          id: 'a1',
          camera_id: 'cam-expedicao',
          camera_name: 'Entrada Expedição',
          violations: [{ class: 'no_helmet', confidence: 0.9 }],
          acknowledged: false,
          created_at: '2026-09-05T13:39:00Z',
        }],
        total: 1,
        total_situacoes: 1,
      },
    })
    montar()
    fireEvent.click(await screen.findByLabelText('Notificações'))
    fireEvent.click(await screen.findByRole('button', { name: /Entrada Expedição/ }))
    // `/epi/alerts` é rota VÁLIDA no app: sem o prefixo, o sino do front novo
    // jogaria o usuário calado na tela antiga (mesmo pisão de RotasNovas.tsx).
    await waitFor(() => expect(screen.getByText('tela NOVA de eventos')).toBeTruthy())
    expect(screen.queryByText('tela ANTIGA de alertas')).toBeNull()
  })
})


/**
 * O front novo não tinha saída nenhuma: o único `logout()` da árvore `app/` era
 * o do aviso de sessão, que só aparece nos 5 minutos finais. Em máquina
 * compartilhada, entrar com a conta errada era um beco sem saída.
 */
describe('topbar tem saída', () => {
  it('o botão Sair derruba a sessão', () => {
    montar()
    fireEvent.click(screen.getByRole('button', { name: /^sair$/i }))
    expect(auth.logout).toHaveBeenCalledTimes(1)
  })
})
