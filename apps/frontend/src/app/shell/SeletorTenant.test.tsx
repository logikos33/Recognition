/**
 * O caso real: superadmin abre o front novo, cai no tenant dele, e a tela de
 * Eventos vem vazia porque os dados estão em OUTRO cliente. Sem este controle
 * não havia como sair dali sem voltar para o front antigo.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const auth = vi.hoisted(() => ({ isSuperAdmin: true }))
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => auth }))

const ctx = vi.hoisted(() => ({
  listar: vi.fn(),
  assumir: vi.fn(),
  emContexto: vi.fn(() => false),
}))
vi.mock('../../services/tenantContext', () => ({
  listAvailableTenants: ctx.listar,
  assumeTenantContext: ctx.assumir,
  isInTenantContext: ctx.emContexto,
}))

import { SeletorTenant } from './SeletorTenant'

const TENANTS = [
  { id: 't-dev', name: 'Desenvolvimento — Recognition Dev', slug: 'dev' },
  { id: 't-rvb', name: 'RVB Isolantes para Transformadores', slug: 'rvb' },
]

beforeEach(() => {
  auth.isSuperAdmin = true
  ctx.listar.mockReset().mockResolvedValue(TENANTS)
  ctx.assumir.mockReset().mockResolvedValue(undefined)
  ctx.emContexto.mockReset().mockReturnValue(false)
})

describe('escolher o cliente', () => {
  it('oferece a saída quando o superadmin está fora de qualquer cliente', async () => {
    render(<SeletorTenant />)
    const botao = await screen.findByRole('button', { name: /escolher cliente/i })
    fireEvent.click(botao)
    expect(screen.getByRole('menuitem', { name: /RVB Isolantes/i })).toBeTruthy()
  })

  it('entrar no cliente delega ao serviço que já é dono do token', async () => {
    // Trocar o token aqui dentro criaria um segundo dono dele — foi o que
    // custou caro no congelamento do live view.
    render(<SeletorTenant />)
    fireEvent.click(await screen.findByRole('button', { name: /escolher cliente/i }))
    fireEvent.click(screen.getByRole('menuitem', { name: /RVB Isolantes/i }))
    // E volta para a MESMA rota: o padrão do serviço é '/', que devolveria o
    // usuário no front ANTIGO — justo quando a tela ia finalmente ter dado.
    await waitFor(() =>
      expect(ctx.assumir).toHaveBeenCalledWith('t-rvb', expect.stringMatching(/^\//)),
    )
  })

  it('some quando já há contexto — quem manda ali é o banner global', async () => {
    ctx.emContexto.mockReturnValue(true)
    const { container } = render(<SeletorTenant />)
    await waitFor(() => expect(container.textContent).toBe(''))
    expect(ctx.listar).not.toHaveBeenCalled()
  })

  it('não aparece para quem não é superadmin', async () => {
    auth.isSuperAdmin = false
    const { container } = render(<SeletorTenant />)
    await waitFor(() => expect(container.textContent).toBe(''))
  })

  it('resposta sem a lista não derruba a topbar', async () => {
    // O caso que quebrou o CI: envelope válido, `data.tenants` ausente. O
    // componente mora na topbar — estourar aqui tira a aplicação inteira do ar,
    // não só o seletor.
    ctx.listar.mockResolvedValue(undefined as never)
    const { container } = render(<SeletorTenant />)
    await waitFor(() => expect(container.textContent).toBe(''))
  })

  it('falha ao listar não derruba a topbar', async () => {
    ctx.listar.mockRejectedValue(new Error('rede'))
    const { container } = render(<SeletorTenant />)
    await waitFor(() => expect(container.textContent).toBe(''))
  })
})
