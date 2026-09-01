/**
 * DashboardIntegradoPage — task D3 ("nome cru na tela").
 *
 * O 3º ponto da entrega D3 (models_summary → display_name) só conta se chegar
 * no pixel: o backend já serve `display_name` no JSON (dashboard_edge_service.py),
 * mas o chip da seção "Observabilidade de Modelos" renderizava `m.model_name`
 * cru (nome de job interno tipo "RF-DETR - Job 0307e2b1") — achado do cético.
 * Este teste prova que o chip usa `nomeInternoOuCliente` (política F5-LEVE,
 * mesma de CameraModelScope): cliente vê o alias, superadmin vê o nome interno.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { DashboardIntegradoPage } from './DashboardIntegradoPage'

const mocks = vi.hoisted(() => ({ isSuperAdmin: false as boolean }))

const MODELO = {
  model_name: 'RF-DETR - Job 0307e2b1',
  display_name: 'Logikos V3' as string | null,
  framework: 'rfdetr',
  last_epoch: 40,
  epoch_count: 40,
  ap5095: 0.71,
  ap_small: 0.6,
}

vi.mock('../services/api', () => ({ getToken: () => null }))
vi.mock('../hooks/useAuth', () => ({ useAuth: () => ({ isSuperAdmin: mocks.isSuperAdmin }) }))
vi.mock('../hooks/useEdgeTelemetrySocket', () => ({
  useEdgeTelemetrySocket: () => ({ connected: false, samples: [], latest: null }),
}))
vi.mock('../services/dashboardEdgeService', () => ({
  dashboardEdgeService: {
    getModels: vi.fn(async () => [MODELO]),
    getTrainingCurves: vi.fn(async () => ({})),
    getEdgeTelemetry: vi.fn(async () => ({ window: '1h', samples: [], count: 0 })),
  },
}))

describe('DashboardIntegradoPage — chip de modelo (D3)', () => {
  it('não-superadmin: chip mostra o display_name, NUNCA o model_name cru (jargão de job interno)', async () => {
    mocks.isSuperAdmin = false
    render(<DashboardIntegradoPage />)

    expect(await screen.findByText('Logikos V3')).toBeDefined()
    expect(screen.queryByText(/RF-DETR - Job/)).toBeNull()
  })

  it('superadmin: continua vendo o nome interno (ferramenta de engenharia) — não regressão', async () => {
    mocks.isSuperAdmin = true
    render(<DashboardIntegradoPage />)

    expect(await screen.findByText('RF-DETR - Job 0307e2b1')).toBeDefined()
  })
})
