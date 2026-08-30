/**
 * Shape REAL de `GET /v1/admin/users` (`Paginated<AdminUser>`) e de
 * `POST /v1/admin/users/<id>/reset-password` (`{email, temp_password}`,
 * `routes.py` — mesma rota que `AdminUsersPage.tsx` antigo usa, não
 * `force-password-reset`). "first_access_token" de `POST /v1/admin/users`
 * NÃO tem rota que o consuma (grep confirmado) — por isso não vira "link
 * copiável", vira a mesma tela de senha-uma-vez do reset.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getUsers = vi.fn()
const getTenants = vi.fn()
const createUser = vi.fn()
const resetPassword = vi.fn()
const deactivateUser = vi.fn()
const reactivateUser = vi.fn()
vi.mock('../../modules/admin/services/adminService', () => ({
  adminService: {
    getUsers: (...a: unknown[]) => getUsers(...a),
    getTenants: (...a: unknown[]) => getTenants(...a),
    createUser: (...a: unknown[]) => createUser(...a),
    resetPassword: (...a: unknown[]) => resetPassword(...a),
    deactivateUser: (...a: unknown[]) => deactivateUser(...a),
    reactivateUser: (...a: unknown[]) => reactivateUser(...a),
  },
}))

import { Usuarios } from './Usuarios'

const USERS_REAL = {
  items: [
    { id: 'u1', email: 'carlos.m@rvb.com.br', name: 'Carlos M.', role: 'operator', tenant_id: 't-rvb', tenant_name: 'RVB Isolantes', is_active: true, login_count: 12, force_password_reset: false, created_at: '2026-01-01T00:00:00Z', last_login_at: '2026-08-20T10:00:00Z' },
    { id: 'u2', email: 'sandra.l@rvb.com.br', role: 'analyst', tenant_id: 't-rvb', tenant_name: 'RVB Isolantes', is_active: false, login_count: 3, force_password_reset: false, created_at: '2026-01-01T00:00:00Z' },
  ],
  total: 2,
}
const TENANTS_REAL = [{ id: 't-rvb', name: 'RVB Isolantes' }]

function montar() {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <Usuarios />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getUsers.mockReset().mockResolvedValue(USERS_REAL)
  getTenants.mockReset().mockResolvedValue(TENANTS_REAL)
  createUser.mockReset()
  resetPassword.mockReset()
  deactivateUser.mockReset().mockResolvedValue({ deactivated: true })
  reactivateUser.mockReset().mockResolvedValue({ reactivated: true })
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})
afterEach(() => vi.clearAllMocks())

describe('Usuarios', () => {
  it('loading → LogikosLoader', () => {
    getUsers.mockReturnValue(new Promise(() => {}))
    montar()
    expect(screen.getByRole('status')).toBeTruthy()
    expect(screen.getByText('CARREGANDO USUÁRIOS')).toBeTruthy()
  })

  it('erro → mensagem técnica + retry', async () => {
    getUsers.mockRejectedValue(new Error('offline'))
    montar()
    expect(await screen.findByText('Não foi possível carregar os usuários')).toBeTruthy()
    expect(screen.getByText('GET /v1/admin/users')).toBeTruthy()
  })

  it('vazio → EmptyState honesto', async () => {
    getUsers.mockResolvedValue({ items: [], total: 0 })
    montar()
    expect(await screen.findByText('Nenhum usuário encontrado')).toBeTruthy()
  })

  it('shape real → nome (fallback email), papel, tenant (nunca UUID), e-mail, último acesso', async () => {
    montar()
    expect(await screen.findByText('Carlos M.')).toBeTruthy()
    // u2 não tem `name` — cai no email (aparece 2x: nome e coluna e-mail),
    // nunca no tenant_id cru.
    expect(screen.getAllByText('sandra.l@rvb.com.br').length).toBe(2)
    expect(screen.getAllByText('RVB ISOLANTES').length).toBe(2)
    expect(screen.getByText('Operador')).toBeTruthy()
    expect(screen.getByText('Analista')).toBeTruthy()
  })

  it('resetar senha: chama resetPassword(id) e mostra a temporária UMA vez, com copiar', async () => {
    resetPassword.mockResolvedValue({ email: 'carlos.m@rvb.com.br', temp_password: 'LK-9T4M-QZ2V' })
    montar()
    await screen.findByText('Carlos M.')

    fireEvent.click(screen.getAllByText('Resetar senha')[0])
    await waitFor(() => expect(resetPassword).toHaveBeenCalledWith('u1'))

    // Exibida agora...
    expect(await screen.findByText('LK-9T4M-QZ2V')).toBeTruthy()

    // ...e some ao fechar — não fica pendurada na tela (não é "sempre visível").
    fireEvent.click(screen.getByRole('button', { name: 'Fechar' }))
    expect(screen.queryByText('LK-9T4M-QZ2V')).toBeNull()
  })

  it('desativar chama deactivateUser (não reactivateUser) para usuário ativo', async () => {
    montar()
    await screen.findByText('Carlos M.')
    // Carlos (u1) está ativo → botão "Desativar" → deactivateUser.
    const linhaCarlos = screen.getByText('carlos.m@rvb.com.br').closest('tr') as HTMLElement
    fireEvent.click(within(linhaCarlos).getByText('Desativar'))
    await waitFor(() => expect(deactivateUser).toHaveBeenCalledWith('u1'))
    expect(reactivateUser).not.toHaveBeenCalled()
  })

  it('reativar chama reactivateUser (não deactivateUser) para usuário inativo', async () => {
    montar()
    await screen.findByText('Carlos M.')
    // Sandra (u2) está inativa → botão "Reativar" → reactivateUser.
    const linhaSandra = screen.getAllByText('sandra.l@rvb.com.br')[0].closest('tr') as HTMLElement
    fireEvent.click(within(linhaSandra).getByText('Reativar'))
    await waitFor(() => expect(reactivateUser).toHaveBeenCalledWith('u2'))
    expect(deactivateUser).not.toHaveBeenCalled()
  })

  it('Convidar usuário: cria e mostra a senha temporária uma vez (sem link de convite)', async () => {
    createUser.mockResolvedValue({
      user: { id: 'u3', email: 'novo@rvb.com.br' },
      temp_password: 'LK-AAAA-BBBB',
      first_access_token: 'tok-morto-sem-rota',
    })
    montar()
    await screen.findByText('Carlos M.')

    fireEvent.click(screen.getByRole('button', { name: 'Convidar usuário' }))
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'novo@rvb.com.br' } })
    fireEvent.change(screen.getByLabelText('Tenant'), { target: { value: 't-rvb' } })
    fireEvent.click(screen.getByRole('button', { name: 'Criar usuário' }))

    expect(await screen.findByText('LK-AAAA-BBBB')).toBeTruthy()
    // O token "de convite" não é exibido como link — é infra morta (ver cabeçalho do arquivo).
    expect(screen.queryByText('tok-morto-sem-rota')).toBeNull()
  })
})
