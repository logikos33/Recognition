/**
 * Shape REAL de `GET /v1/admin/dashboard` (`routes.py:243-254`) — inclusive os
 * quatro campos hardcoded em 0 (`cameras_online`, `alerts_24h`, `tickets_open`,
 * `mrr_estimated`) que a tela deve OMITIR, não mostrar como medição.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getDashboard = vi.fn()
vi.mock('../../modules/admin/services/adminService', () => ({
  adminService: { getDashboard: (...a: unknown[]) => getDashboard(...a) },
}))

import { VisaoGeral } from './VisaoGeral'

const DASHBOARD_REAL = {
  tenants_active: 4,
  users_total: 62,
  cameras_online: 0,
  alerts_24h: 0,
  training_approvals_pending: 2,
  tickets_open: 0,
  mrr_estimated: 0,
  workers: { online: 7, fallback: 1, offline: 0 },
  recent_critical_events: [
    {
      id: 'e1',
      action: 'training_rejected',
      target_type: 'training_job',
      actor_role: 'superadmin',
      actor_email: 'ana@logikos.com',
      tenant_name: 'RVB Isolantes',
      created_at: '2026-08-29T14:00:00Z',
    },
  ],
  top_tenants_users: [
    { tenant_name: 'RVB Isolantes', user_count: 14 },
    { tenant_name: 'Roccatextil', user_count: 22 },
  ],
}

function montar() {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <VisaoGeral />
    </QueryClientProvider>,
  )
}

beforeEach(() => { getDashboard.mockReset() })
afterEach(() => vi.clearAllMocks())

describe('VisaoGeral', () => {
  it('loading → LogikosLoader (tile)', () => {
    getDashboard.mockReturnValue(new Promise(() => {})) // nunca resolve
    montar()
    expect(screen.getByRole('status')).toBeTruthy()
    expect(screen.getByText('CARREGANDO VISÃO GERAL')).toBeTruthy()
  })

  it('erro → mensagem técnica + Tentar novamente aciona novo fetch', async () => {
    getDashboard.mockRejectedValue(new Error('offline'))
    montar()
    expect(await screen.findByText('Não foi possível carregar a visão geral')).toBeTruthy()
    expect(screen.getByText('GET /v1/admin/dashboard')).toBeTruthy()

    getDashboard.mockResolvedValue(DASHBOARD_REAL)
    screen.getByRole('button', { name: 'Tentar novamente' }).click()
    expect(await screen.findByText('Visão geral')).toBeTruthy()
    expect(getDashboard).toHaveBeenCalledTimes(2)
  })

  it('shape real → KPIs com os campos que o backend TEM, e omite os hardcoded em 0', async () => {
    getDashboard.mockResolvedValue(DASHBOARD_REAL)
    montar()

    expect(await screen.findByText('Visão geral')).toBeTruthy()
    expect(screen.getByText('4')).toBeTruthy() // tenants_active
    expect(screen.getByText('62')).toBeTruthy() // users_total
    expect(screen.getByText('2')).toBeTruthy() // training_approvals_pending

    // Campos hardcoded em 0 no handler (routes.py) não viram card nenhum.
    expect(screen.queryByText(/câmeras online/i)).toBeNull()
    expect(screen.queryByText(/alertas/i)).toBeNull()
    expect(screen.queryByText(/tickets/i)).toBeNull()
    expect(screen.queryByText(/mrr/i)).toBeNull()

    // Painéis com dado real (top_tenants_users, recent_critical_events).
    expect(screen.getByText('RVB Isolantes')).toBeTruthy()
    expect(screen.getByText('Roccatextil')).toBeTruthy()
    expect(screen.getByText(/Treino rejeitado/)).toBeTruthy()
  })

  it('sem tenant e sem usuário → EmptyState honesto, não zero fingindo dado', async () => {
    getDashboard.mockResolvedValue({ ...DASHBOARD_REAL, tenants_active: 0, users_total: 0 })
    montar()
    expect(await screen.findByText('Nenhum tenant cadastrado ainda')).toBeTruthy()
  })
})
