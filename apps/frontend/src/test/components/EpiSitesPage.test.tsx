/**
 * Testes de EpiSitesPage (task-093 — ADR-0046).
 *
 * Cobre: role-gating no frontend (defesa em profundidade — o backend já é
 * a fonte de verdade via has_permission('edge:manage')), PATCH otimista com
 * rollback em erro, e rótulos de apresentação do deployment_mode.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { EpiSitesPage } from '../../pages/epi/EpiSitesPage'
import { edgeService } from '../../services/edgeService'
import type { EdgeSite } from '../../types/edge'

vi.mock('../../services/edgeService')

const toastMocks = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }
vi.mock('../../components/ui/Toast/useToast', () => ({
  useToast: () => toastMocks,
}))

let mockIsAdmin = true
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ isAdmin: mockIsAdmin }),
}))

const mockSites: EdgeSite[] = [
  {
    id: 'site-1',
    tenant_id: 'tenant-a',
    name: 'Planta São Paulo',
    description: null,
    location: 'São Paulo, SP',
    deployment_mode: 'edge',
    status: 'active',
    created_at: '2026-01-01T00:00:00Z',
    created_by: 'user-1',
  },
  {
    id: 'site-2',
    tenant_id: 'tenant-a',
    name: 'Planta Campinas',
    description: null,
    location: null,
    deployment_mode: 'cloud',
    status: 'inactive',
    created_at: '2026-01-02T00:00:00Z',
    created_by: 'user-1',
  },
]

beforeEach(() => {
  vi.resetAllMocks()
  mockIsAdmin = true
})

describe('EpiSitesPage — role gating', () => {
  it('não chama listSites e mostra acesso restrito quando isAdmin=false', async () => {
    mockIsAdmin = false
    render(<EpiSitesPage />)

    expect(await screen.findByText(/acesso restrito/i)).toBeDefined()
    expect(edgeService.listSites).not.toHaveBeenCalled()
  })

  it('admin carrega e lista os sites do tenant', async () => {
    vi.mocked(edgeService.listSites).mockResolvedValue(mockSites)
    render(<EpiSitesPage />)

    expect(await screen.findByText('Planta São Paulo')).toBeDefined()
    expect(screen.getByText('Planta Campinas')).toBeDefined()
    expect(edgeService.listSites).toHaveBeenCalledTimes(1)
  })
})

describe('EpiSitesPage — troca de deployment_mode', () => {
  it('faz PATCH via edgeService.updateSite com o novo modo e mostra toast de sucesso', async () => {
    vi.mocked(edgeService.listSites).mockResolvedValue(mockSites)
    vi.mocked(edgeService.updateSite).mockResolvedValue({ ...mockSites[0], deployment_mode: 'hybrid' })
    render(<EpiSitesPage />)

    const select = await screen.findByLabelText(/modo de deployment do site planta são paulo/i)
    fireEvent.change(select, { target: { value: 'hybrid' } })

    await waitFor(() => {
      expect(edgeService.updateSite).toHaveBeenCalledWith('site-1', { deployment_mode: 'hybrid' })
    })
    await waitFor(() => expect(toastMocks.success).toHaveBeenCalled())
  })

  it('reverte a UI (optimistic rollback) e mostra toast de erro quando o PATCH falha', async () => {
    vi.mocked(edgeService.listSites).mockResolvedValue(mockSites)
    vi.mocked(edgeService.updateSite).mockRejectedValue(new Error('Site não encontrado'))
    render(<EpiSitesPage />)

    const select = await screen.findByLabelText<HTMLSelectElement>(/modo de deployment do site planta são paulo/i)
    fireEvent.change(select, { target: { value: 'cloud' } })

    await waitFor(() => expect(toastMocks.error).toHaveBeenCalledWith('Site não encontrado'))
    await waitFor(() => expect(select.value).toBe('edge')) // rollback para o valor original
  })

  it('exibe os rótulos de apresentação do ADR-0046 (edge/dual/cloud-only) mapeados dos valores persistidos', async () => {
    vi.mocked(edgeService.listSites).mockResolvedValue(mockSites)
    render(<EpiSitesPage />)

    const select = await screen.findByLabelText<HTMLSelectElement>(/modo de deployment do site planta são paulo/i)
    const optionLabels = Array.from(select.options).map(o => o.text)
    expect(optionLabels).toEqual(['Edge', 'Dual (edge + cloud)', 'Cloud-only'])
  })
})

describe('EpiSitesPage — estados de carregamento', () => {
  it('mostra estado vazio quando o tenant não tem sites', async () => {
    vi.mocked(edgeService.listSites).mockResolvedValue([])
    render(<EpiSitesPage />)

    expect(await screen.findByText(/nenhum site cadastrado/i)).toBeDefined()
  })

  it('mostra mensagem de erro quando listSites rejeita (ex.: 403/500)', async () => {
    vi.mocked(edgeService.listSites).mockRejectedValue(new Error('Acesso negado'))
    render(<EpiSitesPage />)

    expect(await screen.findByText(/erro ao carregar sites/i)).toBeDefined()
  })
})
