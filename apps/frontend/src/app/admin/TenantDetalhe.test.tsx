/**
 * Shape REAL de `GET /v1/admin/tenants/<id>` (`routes.py:370-450`): sem
 * contagem de câmeras nem `max_users`/`max_cameras` efetivos — por isso o
 * numerador de câmeras vem de `/overview` (`cameras: [...]`) e o limite vem
 * de `contract_cameras` ?? `plans.max_cameras` (casado por slug).
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const navigateMock = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...real, useNavigate: () => navigateMock, useParams: () => ({ tenantId: 't-rvb' }) }
})

const getTenant = vi.fn()
const getTenantOverview = vi.fn()
const getPlans = vi.fn()
const getModulesCatalog = vi.fn()
const getTenantBranding = vi.fn()
const updateTenant = vi.fn()
const updateTenantBranding = vi.fn()
const suspendTenant = vi.fn()
const reactivateTenant = vi.fn()
vi.mock('../../modules/admin/services/adminService', () => ({
  adminService: {
    getTenant: (...a: unknown[]) => getTenant(...a),
    getTenantOverview: (...a: unknown[]) => getTenantOverview(...a),
    getPlans: (...a: unknown[]) => getPlans(...a),
    getModulesCatalog: (...a: unknown[]) => getModulesCatalog(...a),
    getTenantBranding: (...a: unknown[]) => getTenantBranding(...a),
    updateTenant: (...a: unknown[]) => updateTenant(...a),
    updateTenantBranding: (...a: unknown[]) => updateTenantBranding(...a),
    suspendTenant: (...a: unknown[]) => suspendTenant(...a),
    reactivateTenant: (...a: unknown[]) => reactivateTenant(...a),
  },
}))

vi.mock('../../services/tenantContext', () => ({
  assumeTenantContext: vi.fn().mockResolvedValue(undefined),
}))

import { TenantDetalhe } from './TenantDetalhe'

const TENANT_REAL = {
  id: 't-rvb',
  slug: 'rvb-isolantes',
  name: 'RVB Isolantes',
  plan: 'standard',
  schema_name: 'rvb_isolantes',
  is_active: true,
  modules_enabled: ['epi'],
  created_at: '2026-03-01T00:00:00Z',
  contract_cameras: 10,
  seats_in_use: 14,
  max_seats: 25,
}

function montar() {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter>
        <TenantDetalhe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getTenant.mockReset().mockResolvedValue(TENANT_REAL)
  getTenantOverview.mockReset().mockResolvedValue({ cameras: [{ id: 1 }, { id: 2 }, { id: 3 }] })
  getPlans.mockReset().mockResolvedValue([{ id: 'p1', slug: 'standard', name: 'Standard', max_cameras: 10, max_users: 25 }])
  getModulesCatalog.mockReset().mockResolvedValue([{ code: 'epi', label: 'EPI', description: '', status: 'active' }])
  getTenantBranding.mockReset().mockResolvedValue({ product_name: 'x', color_primary: '#00E5FF', color_secondary: '#000', logo_url: null, favicon_url: null })
  updateTenant.mockReset().mockResolvedValue({ updated: true })
  updateTenantBranding.mockReset().mockResolvedValue({ updated: true, branding: {} })
  suspendTenant.mockReset().mockResolvedValue({ suspended: true })
  reactivateTenant.mockReset().mockResolvedValue({ reactivated: true })
})
afterEach(() => vi.clearAllMocks())

describe('TenantDetalhe', () => {
  it('loading → LogikosLoader', () => {
    getTenant.mockReturnValue(new Promise(() => {}))
    montar()
    expect(screen.getByRole('status')).toBeTruthy()
    expect(screen.getByText('CARREGANDO TENANT')).toBeTruthy()
  })

  it('erro → mensagem técnica + retry', async () => {
    getTenant.mockRejectedValue(new Error('offline'))
    montar()
    expect(await screen.findByText('Não foi possível carregar este tenant')).toBeTruthy()
    expect(screen.getByText('GET /v1/admin/tenants/t-rvb')).toBeTruthy()
  })

  it('limites do plano: câmeras vêm do /overview, usuários de seats_in_use/max_seats', async () => {
    montar()
    expect(await screen.findByText('RVB Isolantes')).toBeTruthy()
    // 3 câmeras (overview) / 10 (contract_cameras)
    expect(await screen.findByText('3/10')).toBeTruthy()
    // 14 (seats_in_use) / 25 (max_seats)
    expect(screen.getByText('14/25')).toBeTruthy()
  })

  it('toggle de módulo chama PATCH updateTenant com modules_enabled', async () => {
    montar()
    const item = await screen.findByText('EPI')
    fireEvent.click(item.closest('button') as HTMLElement)
    await waitFor(() => expect(updateTenant).toHaveBeenCalledWith('t-rvb', { modules_enabled: [] }))
  })

  it('Suspender chama suspendTenant com o motivo do prompt', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('inadimplência')
    montar()
    const botao = await screen.findByText('Suspender')
    fireEvent.click(botao)
    await waitFor(() => expect(suspendTenant).toHaveBeenCalledWith('t-rvb', 'inadimplência'))
  })

  it('prévia da marca usa corDeMarcaUsavel: cor sem contraste suficiente é CLAREADA, não usada crua', async () => {
    // Azul-marinho escuro — falha o piso de 4.5:1 contra o shell escuro e
    // tem de ser clareado pelo clamp real (contraste.ts), não usado como veio.
    getTenantBranding.mockResolvedValue({ product_name: 'x', color_primary: '#0a1a3a', color_secondary: '#000', logo_url: null, favicon_url: null })
    montar()
    await screen.findByText('RVB Isolantes')

    const botaoPrimario = await screen.findByText('Botão primário')
    const corRenderizada = (botaoPrimario as HTMLElement).style.background
    expect(corRenderizada.toLowerCase()).not.toBe('rgb(10, 26, 58)') // #0a1a3a cru
    expect(await screen.findByText(/Cor ajustada automaticamente/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Salvar marca' }))
    await waitFor(() => expect(updateTenantBranding).toHaveBeenCalled())
    const [, payload] = updateTenantBranding.mock.calls[0] as [string, { color_primary: string }]
    // O que é ENVIADO ao backend é a cor ajustada, nunca a crua.
    expect(payload.color_primary.toLowerCase()).not.toBe('#0a1a3a')
  })
})
