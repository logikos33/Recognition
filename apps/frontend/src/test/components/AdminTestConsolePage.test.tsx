/**
 * Testes Vitest/RTL para AdminTestConsolePage (WS5).
 *
 * Cobre:
 *   1. handleStart envia default_fps=5 no payload (payload aditivo)
 *   2. Modo "Ajustar FPS por câmera" envia camera_fps coerente com camera_count
 *   3. Tabela de integrações renderiza status REAL (error → "Erro"),
 *      sem o "● configurada" hard-coded
 *   4. Catálogo de integrações cobre os 5 tipos da migration 082
 *   5. Chips de classes exibem rótulos pt-BR
 *
 * Padrão: adminService mockado; nenhuma chamada de rede real.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeAll, beforeEach } from 'vitest'

// jsdom não implementa scrollIntoView (usado no auto-scroll do log)
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
})
import { AdminTestConsolePage } from '../../modules/admin/pages/AdminTestConsolePage'
import { INTEGRATION_CATALOG } from '../../modules/admin/constants/integrationCatalog'
import type { TestConsoleStatus, Integration } from '../../modules/admin/types/admin'

// ── Mocks ─────────────────────────────────────────────────────────────────────

const idleStatus: TestConsoleStatus = {
  status: 'idle',
  session_id: null,
  started_at: null,
  stopped_at: null,
  config: null,
  metrics: {
    detections_per_sec: 0,
    latency_ms: 0,
    throughput_infs: 0,
    vram_pct: 0,
    cameras_active: 0,
  },
  log_lines: [],
  vast_ai_configured: true,
}

const errorIntegration: Integration = {
  id: 'int-1',
  integration_type: 'vast_ai',
  label: 'vast_ai',
  config: {},
  secret_display: '••••cdef',
  status: 'error',
  last_tested_at: '2026-06-30T10:00:00Z',
  last_error: 'HTTP 401',
}

vi.mock('../../modules/admin/services/adminService', () => ({
  adminService: {
    getTestConsoleStatus: vi.fn(),
    getModelsForConsole: vi.fn(),
    getIntegrations: vi.fn(),
    startTestConsole: vi.fn(),
    stopTestConsole: vi.fn(),
    getModelScenarioConfig: vi.fn(),
  },
}))

import { adminService } from '../../modules/admin/services/adminService'

function setupMocks(integrations: Integration[] = []) {
  vi.mocked(adminService.getTestConsoleStatus).mockResolvedValue(idleStatus)
  vi.mocked(adminService.getModelsForConsole).mockResolvedValue([])
  vi.mocked(adminService.getIntegrations).mockResolvedValue(integrations)
  vi.mocked(adminService.startTestConsole).mockResolvedValue({
    session_id: 's1', status: 'running', mode: 'stub',
  })
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/admin/test-console']}>
      <AdminTestConsolePage />
    </MemoryRouter>,
  )
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('AdminTestConsolePage — FPS no payload de start (WS5 M5)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  it('envia default_fps=5 por padrão e omite camera_fps', async () => {
    renderPage()
    const startBtn = await screen.findByRole('button', { name: /Iniciar Teste/i })
    fireEvent.click(startBtn)

    await waitFor(() => {
      expect(adminService.startTestConsole).toHaveBeenCalledTimes(1)
    })
    const payload = vi.mocked(adminService.startTestConsole).mock.calls[0][0]
    expect(payload.default_fps).toBe(5)
    expect(payload.camera_count).toBe(1)
    expect(payload.camera_fps).toBeUndefined()
    // payload de classes continua com ids em inglês
    expect((payload.scenario_config as { classes: string[] }).classes).toContain('helmet')
  })

  it('com "Ajustar FPS por câmera" ativo envia camera_fps com um valor por câmera', async () => {
    renderPage()
    const toggle = await screen.findByLabelText(/Ajustar FPS por câmera/i)
    fireEvent.click(toggle)

    const startBtn = screen.getByRole('button', { name: /Iniciar Teste/i })
    fireEvent.click(startBtn)

    await waitFor(() => {
      expect(adminService.startTestConsole).toHaveBeenCalledTimes(1)
    })
    const payload = vi.mocked(adminService.startTestConsole).mock.calls[0][0]
    expect(payload.camera_fps).toEqual([5])
    expect(payload.camera_fps?.length).toBe(payload.camera_count)
  })
})

describe('AdminTestConsolePage — integrações com status real (WS5 M9)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renderiza badge "Erro" para integração com status error (sem "configurada" fixo)', async () => {
    setupMocks([errorIntegration])
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Erro')).toBeTruthy()
    })
    // título vem do catálogo, não da chave crua
    expect(screen.getByText('Provedor GPU — Vast.ai')).toBeTruthy()
    // segredo mascarado exibido
    expect(screen.getByText('••••cdef')).toBeTruthy()
    // o status hard-coded antigo não existe mais
    expect(screen.queryByText(/● configurada/)).toBeNull()
  })

  it('possui botão "Gerenciar em Integrações" (deep link — sem form inline)', async () => {
    setupMocks([errorIntegration])
    renderPage()

    expect(await screen.findByRole('button', { name: /Gerenciar em Integrações/i })).toBeTruthy()
    // form inline antigo (chave/valor/tenant) foi removido
    expect(screen.queryByText(/\+ Adicionar \/ Atualizar/)).toBeNull()
  })
})

describe('integrationCatalog — completude (WS5 M9)', () => {
  it('cobre os 5 integration_types da migration 082', () => {
    const types = INTEGRATION_CATALOG.map((spec) => spec.type)
    for (const expected of ['r2', 'vast_ai', 'generic_gpu', 'notification', 'byo_db']) {
      expect(types).toContain(expected)
    }
    // todo spec tem helpText não-vazio (onde obter a chave)
    for (const spec of INTEGRATION_CATALOG) {
      expect(spec.helpText.length).toBeGreaterThan(10)
    }
  })
})

describe('AdminTestConsolePage — classes pt-BR (WS5 M6)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  it('chips de classes exibem rótulos pt-BR', async () => {
    renderPage()
    expect(await screen.findByRole('button', { name: 'Capacete' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Sem Capacete' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Colete' })).toBeTruthy()
  })
})
