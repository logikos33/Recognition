/**
 * Shell — o que não pode regredir.
 *
 * O foco aqui é o que MACHUCA em produção, não a existência de `<div>`:
 * navegação que mostra o que o perfil não pode abrir, rótulo que some do leitor
 * de tela ao recolher a sidebar, e aviso de sessão disparado com prazo que não
 * existe.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const auth = vi.hoisted(() => ({ can: vi.fn(() => true) }))
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => auth }))

const sessao = vi.hoisted(() => ({ exp: vi.fn<() => number | null>(() => null) }))
vi.mock('../../services/tenantContext', () => ({
  getSessionTokenExpMs: sessao.exp,
}))

import { Shell } from './Shell'

function montar(rota = '/novo/epi/live') {
  return render(
    <MemoryRouter initialEntries={[rota]}>
      <Routes>
        <Route path="/novo" element={<Shell />}>
          <Route path="epi/live" element={<p>conteúdo da tela</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  auth.can.mockReset()
  auth.can.mockReturnValue(true)
  sessao.exp.mockReset()
  sessao.exp.mockReturnValue(null)
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
    // com permissao: null.
    auth.can.mockReturnValue(false)
    montar()
    const nomes = screen.queryAllByRole('link').map((a) => a.textContent?.trim())
    expect(nomes).toEqual(['Dashboard'])
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
    expect(screen.getByRole('button', { name: /renovar/i })).toBeTruthy()
  })

  it('abre a paleta pelo botão da topbar', async () => {
    montar()
    fireEvent.click(screen.getByRole('button', { name: /buscar/i }))
    expect(screen.getByRole('dialog')).toBeTruthy()
  })
})
