/**
 * Shape REAL de `GET /v1/admin/tenants` (`routes.py:263-291`) — sem contagem
 * de câmeras (só `id,slug,name,plan,schema_name,is_active,modules_enabled,
 * created_at,suspended_at,user_count`), por isso a lista não tem coluna
 * "câmeras" (ver divergência no cabeçalho de `Tenants.tsx`).
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const navigateMock = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...real, useNavigate: () => navigateMock }
})

const getTenants = vi.fn()
const getModulesCatalog = vi.fn()
const createTenant = vi.fn()
vi.mock('../../modules/admin/services/adminService', () => ({
  adminService: {
    getTenants: (...a: unknown[]) => getTenants(...a),
    getModulesCatalog: (...a: unknown[]) => getModulesCatalog(...a),
    createTenant: (...a: unknown[]) => createTenant(...a),
  },
}))

const listAvailableTenants = vi.fn()
const assumeTenantContext = vi.fn()
vi.mock('../../services/tenantContext', () => ({
  listAvailableTenants: (...a: unknown[]) => listAvailableTenants(...a),
  assumeTenantContext: (...a: unknown[]) => assumeTenantContext(...a),
}))

import { Tenants } from './Tenants'

const TENANTS_REAL = [
  { id: 't-rvb', slug: 'rvb-isolantes', name: 'RVB Isolantes', plan: 'standard', schema_name: 'rvb_isolantes', is_active: true, modules_enabled: ['epi', 'quality'], created_at: '2026-03-01T00:00:00Z', user_count: 14 },
  { id: 't-rct', slug: 'roccatextil', name: 'Roccatextil', plan: 'standard', schema_name: 'roccatextil', is_active: false, modules_enabled: ['epi'], created_at: '2026-04-01T00:00:00Z', user_count: 22 },
]

function montar() {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter>
        <Tenants />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getTenants.mockReset()
  getModulesCatalog.mockReset().mockResolvedValue([])
  createTenant.mockReset()
  listAvailableTenants.mockReset().mockResolvedValue([{ id: 't-rvb', name: 'RVB Isolantes', slug: 'rvb-isolantes' }])
  assumeTenantContext.mockReset().mockResolvedValue(undefined)
  navigateMock.mockReset()
})
afterEach(() => vi.clearAllMocks())

describe('Tenants', () => {
  it('loading → LogikosLoader', () => {
    getTenants.mockReturnValue(new Promise(() => {}))
    montar()
    expect(screen.getByRole('status')).toBeTruthy()
    expect(screen.getByText('CARREGANDO TENANTS')).toBeTruthy()
  })

  it('erro → mensagem técnica + retry refaz o fetch', async () => {
    getTenants.mockRejectedValue(new Error('offline'))
    montar()
    expect(await screen.findByText('Não foi possível carregar os tenants')).toBeTruthy()
    expect(screen.getByText('GET /v1/admin/tenants')).toBeTruthy()

    getTenants.mockResolvedValue(TENANTS_REAL)
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    expect(await screen.findByText('RVB Isolantes')).toBeTruthy()
  })

  it('vazio → EmptyState honesto', async () => {
    getTenants.mockResolvedValue([])
    montar()
    expect(await screen.findByText('Nenhum tenant cadastrado ainda')).toBeTruthy()
  })

  it('shape real → nome, módulos, usuários, status; "Ver como tenant" só para tenant elegível', async () => {
    getTenants.mockResolvedValue(TENANTS_REAL)
    montar()

    expect(await screen.findByText('RVB Isolantes')).toBeTruthy()
    expect(screen.getByText('Roccatextil')).toBeTruthy()
    expect(screen.getAllByText('EPI').length).toBe(2)
    expect(screen.getByText('QUALITY')).toBeTruthy()
    expect(screen.getByText('Ativo')).toBeTruthy()
    expect(screen.getByText('Suspenso')).toBeTruthy()

    // só t-rvb está em listAvailableTenants — só ele ganha o botão.
    await waitFor(() => expect(screen.getAllByText('Ver como tenant').length).toBe(1))
  })

  it('"Ver como tenant" assume o contexto do tenant certo', async () => {
    getTenants.mockResolvedValue(TENANTS_REAL)
    montar()
    const botao = await screen.findByText('Ver como tenant')
    fireEvent.click(botao)
    await waitFor(() => expect(assumeTenantContext).toHaveBeenCalledWith('t-rvb'))
  })

  it('clicar no nome do tenant navega para o detalhe via rotaNova', async () => {
    getTenants.mockResolvedValue(TENANTS_REAL)
    montar()
    const nome = await screen.findByText('RVB Isolantes')
    fireEvent.click(nome)
    expect(navigateMock).toHaveBeenCalledWith('/novo/admin/tenants/t-rvb')
  })

  it('Novo tenant: cria e mostra a senha temporária uma vez, com copiar', async () => {
    getTenants.mockResolvedValue(TENANTS_REAL)
    createTenant.mockResolvedValue({
      tenant: { id: 't-novo', slug: 'nova-empresa', name: 'Nova Empresa' },
      admin_email: 'admin@nova-empresa.epimonitor.local',
      temp_password: 'LK-9T4M-QZ2V',
    })
    montar()
    await screen.findByText('RVB Isolantes')

    fireEvent.click(screen.getByRole('button', { name: 'Novo tenant' }))
    fireEvent.change(screen.getByLabelText('Nome da empresa'), { target: { value: 'Nova Empresa' } })
    fireEvent.change(screen.getByLabelText('Slug (ex: empresa-abc)'), { target: { value: 'nova-empresa' } })

    fireEvent.click(screen.getByRole('button', { name: 'Criar tenant' }))
    expect(await screen.findByText('admin@nova-empresa.epimonitor.local')).toBeTruthy()
    expect(screen.getByText('LK-9T4M-QZ2V')).toBeTruthy()
  })
})
