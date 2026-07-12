import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AdminPlansPage } from './AdminPlansPage'
import { adminService } from '../services/adminService'
import type { ModuleRegistryEntry, Plan } from '../types/admin'

vi.mock('../services/adminService', () => ({
  adminService: {
    getPlans: vi.fn(),
    getModulesRegistry: vi.fn(),
    createPlan: vi.fn(),
    updatePlan: vi.fn(),
  },
}))

const mockRegistry: ModuleRegistryEntry[] = [
  {
    module_code: 'epi',
    label: 'EPI Monitor',
    features: [
      { key: 'vms', label: 'Monitoramento ao vivo (VMS)' },
      { key: 'alerts', label: 'Alertas' },
    ],
  },
  {
    module_code: 'basic',
    label: 'Básico',
    features: [{ key: 'vms', label: 'Monitoramento ao vivo (VMS)' }],
  },
]

const mockPlan: Plan = {
  id: 'p1',
  slug: 'standard',
  name: 'Standard',
  modules_allowed: ['epi'],
  max_cameras: 20,
  max_users: null,
  video_retention_days: 15,
  requires_training_approval: false,
  price_per_camera: { epi: 280 },
  module_features: { epi: ['vms'] },
  api_rate_per_minute: 120,
  active: true,
  tenant_count: 3,
}

const mocked = vi.mocked(adminService)

beforeEach(() => {
  vi.clearAllMocks()
  mocked.getPlans.mockResolvedValue([mockPlan])
  mocked.getModulesRegistry.mockResolvedValue(mockRegistry)
  mocked.updatePlan.mockResolvedValue({ updated: true })
  mocked.createPlan.mockResolvedValue(mockPlan)
})

describe('AdminPlansPage', () => {
  it('renderiza planos com contagem de clientes e módulos por label', async () => {
    render(<AdminPlansPage />)
    expect(await screen.findByText('Standard')).toBeDefined()
    expect(screen.getByText('3 clientes')).toBeDefined()
    expect(screen.getByText('EPI Monitor')).toBeDefined()
    expect(screen.getByText('Usuários: Ilimitado')).toBeDefined()
  })

  it('edição: slug é read-only', async () => {
    render(<AdminPlansPage />)
    fireEvent.click(await screen.findByText('Standard'))
    const slugInput = await screen.findByLabelText<HTMLInputElement>('Slug')
    expect(slugInput.readOnly).toBe(true)
    expect(slugInput.disabled).toBe(true)
  })

  it('criação: slug inválido mostra erro de validação e bloqueia salvar', async () => {
    render(<AdminPlansPage />)
    await screen.findByText('Standard')
    fireEvent.click(screen.getByText('Novo Plano'))

    const nameInput = await screen.findByLabelText<HTMLInputElement>('Nome')
    fireEvent.change(nameInput, { target: { value: 'Plano Teste' } })

    const slugInput = screen.getByLabelText<HTMLInputElement>('Slug')
    expect(slugInput.readOnly).toBe(false)
    fireEvent.change(slugInput, { target: { value: 'Slug Inválido!' } })
    fireEvent.blur(slugInput)

    expect(
      await screen.findByText(/Use 2-50 caracteres/),
    ).toBeDefined()

    fireEvent.click(screen.getByText('Salvar'))
    await waitFor(() => expect(mocked.createPlan).not.toHaveBeenCalled())
  })

  it('salvar edição envia module_features e price_per_camera sem slug', async () => {
    render(<AdminPlansPage />)
    fireEvent.click(await screen.findByText('Standard'))
    await screen.findByLabelText('Nome')

    fireEvent.click(screen.getByText('Salvar'))

    await waitFor(() => expect(mocked.updatePlan).toHaveBeenCalledTimes(1))
    const [id, payload] = mocked.updatePlan.mock.calls[0]
    expect(id).toBe('p1')
    expect(payload.module_features).toEqual({ epi: ['vms'] })
    expect(payload.price_per_camera).toEqual({ epi: 280 })
    expect(payload.max_users).toBeNull()
    expect('slug' in payload).toBe(false)
  })

  it('criação: default de retenção é 7 dias', async () => {
    render(<AdminPlansPage />)
    await screen.findByText('Standard')
    fireEvent.click(screen.getByText('Novo Plano'))
    const retention = await screen.findByLabelText<HTMLInputElement>('Retenção de vídeo (dias)')
    expect(retention.value).toBe('7')
  })

  it('erro do modal é limpo ao reabrir', async () => {
    mocked.updatePlan.mockRejectedValueOnce(new Error('Falha simulada'))
    render(<AdminPlansPage />)
    fireEvent.click(await screen.findByText('Standard'))
    await screen.findByLabelText('Nome')
    fireEvent.click(screen.getByText('Salvar'))
    await screen.findAllByText('Falha simulada')

    fireEvent.click(screen.getByText('Cancelar'))
    await waitFor(() => expect(screen.queryByLabelText('Nome')).toBeNull())

    fireEvent.click(screen.getByText('Standard'))
    await screen.findByLabelText('Nome')
    // Banner do modal não deve reaparecer com o erro antigo
    expect(document.querySelectorAll('[role="alert"]').length).toBe(0)
  })
})
