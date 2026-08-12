/**
 * CameraFpsConfig (WS10) — health-aware real, fallback, gate por papel, salvar.
 */
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { CameraFpsConfig } from './CameraFpsConfig'
import type { Camera } from '../../types'
import type { CameraHealthContext } from '../../types/edge'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
const mocks = vi.hoisted(() => ({
  getHealthContext: vi.fn(),
  patchConfig: vi.fn(),
  role: 'operator' as string,
}))

vi.mock('../../services/cameraService', () => ({
  cameraService: {
    getHealthContext: mocks.getHealthContext,
    patchConfig: mocks.patchConfig,
  },
}))

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 'u1', email: 'x@y.z', name: 'User', role: mocks.role },
  }),
}))

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------
const camera: Camera = {
  id: 'cam-1',
  name: 'Cam Doca',
  manufacturer: 'generic',
  host: '10.0.0.1',
  port: 554,
  channel: 1,
  is_active: true,
  created_at: '2026-01-01',
  fps_target: 5,
  quality_preset: 'medium',
  site_id: 'site-1',
}

function ctx(overrides: Partial<CameraHealthContext> = {}): CameraHealthContext {
  return {
    has_telemetry: true,
    site_id: 'site-1',
    derived_status: 'healthy',
    received_at: '2026-07-01 10:00:00+00',
    metrics: {
      gpu_pct: 40,
      gpu_mem_pct: 50,
      cpu_pct: 30,
      inference_fps: 24.5,
      inference_latency_ms: 120,
      queue_depth: 2,
      cameras_online: 5,
      cameras_total: 6,
      gpu_temp_c: null,
      decode_pct: null,
    },
    fps_demand_total: 45,
    cameras_active_count: 6,
    ...overrides,
  }
}

function noTelemetry(): CameraHealthContext {
  return {
    has_telemetry: false,
    site_id: null,
    derived_status: null,
    received_at: null,
    metrics: null,
    fps_demand_total: 0,
    cameras_active_count: 0,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.role = 'operator'
  mocks.getHealthContext.mockResolvedValue(ctx())
  mocks.patchConfig.mockResolvedValue({ ...camera, fps_target: 10, propagation: { queued: true, reason: null } })
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('CameraFpsConfig', () => {
  it('sem telemetria mostra disclaimer de estimativa aproximada', async () => {
    mocks.getHealthContext.mockResolvedValue(noTelemetry())
    render(<CameraFpsConfig camera={camera} totalActiveCameras={3} onSaved={vi.fn()} />)

    await waitFor(() => {
      expect(
        screen.getByText(/Estimativa aproximada — sem telemetria do edge/i),
      ).toBeDefined()
    })
    expect(screen.getByText(/carga estimada/i)).toBeDefined()
  })

  it('telemetria com GPU 90% mostra aviso crítico de saturação', async () => {
    mocks.getHealthContext.mockResolvedValue(
      ctx({ metrics: { ...ctx().metrics!, gpu_pct: 90 } }),
    )
    render(<CameraFpsConfig camera={camera} onSaved={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText(/Aumentar o FPS pode saturar o edge/i)).toBeDefined()
    })
    // Demanda real do site exibida (não a heurística)
    expect(screen.getByText(/45 fps/)).toBeDefined()
    expect(screen.queryByText(/Estimativa aproximada/i)).toBeNull()
  })

  it('viewer vê controles desabilitados (read-only)', async () => {
    mocks.role = 'viewer'
    render(<CameraFpsConfig camera={camera} onSaved={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText(/somente leitura/i)).toBeDefined()
    })
    const fpsBtn = screen.getByRole('button', { name: '10 fps' })
    expect((fpsBtn as HTMLButtonElement).disabled).toBe(true)
    const saveBtn = screen.getByRole('button', { name: /Salvar configuração/i })
    expect((saveBtn as HTMLButtonElement).disabled).toBe(true)
  })

  it('salvar chama patchConfig e dispara onSaved', async () => {
    const onSaved = vi.fn()
    render(<CameraFpsConfig camera={camera} onSaved={onSaved} />)

    await waitFor(() => {
      expect(mocks.getHealthContext).toHaveBeenCalled()
    })

    fireEvent.click(screen.getByRole('button', { name: '10 fps' }))
    fireEvent.click(screen.getByRole('button', { name: /Salvar configuração/i }))

    await waitFor(() => {
      expect(mocks.patchConfig).toHaveBeenCalledWith('cam-1', {
        fps_target: 10,
        quality_preset: 'medium',
      })
      expect(onSaved).toHaveBeenCalled()
    })
  })

  it('erro no salvar aparece inline com a mensagem do backend', async () => {
    mocks.patchConfig.mockRejectedValue(new Error('fps_target inválido'))
    render(<CameraFpsConfig camera={camera} onSaved={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: '10 fps' }))
    fireEvent.click(screen.getByRole('button', { name: /Salvar configuração/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toContain('fps_target inválido')
    })
  })

  it('botão Atualizar refaz o fetch do health-context', async () => {
    render(<CameraFpsConfig camera={camera} onSaved={vi.fn()} />)
    await waitFor(() => {
      expect(mocks.getHealthContext).toHaveBeenCalledTimes(1)
    })

    fireEvent.click(screen.getByRole('button', { name: /Atualizar telemetria/i }))
    await waitFor(() => {
      expect(mocks.getHealthContext).toHaveBeenCalledTimes(2)
    })
  })

  // -------------------------------------------------------------------------
  // Eixo COLETA (migration 114) — seletor independente de FPS/qualidade
  // -------------------------------------------------------------------------
  describe('eixo COLETA (collection_subtype)', () => {
    it('renderiza os dois seletores de coleta, junto com os de FPS/qualidade', async () => {
      render(<CameraFpsConfig camera={camera} onSaved={vi.fn()} />)

      await waitFor(() => {
        expect(mocks.getHealthContext).toHaveBeenCalled()
      })

      expect(screen.getByText(/Qualidade da coleta \(dado de treino\)/i)).toBeDefined()
      expect(screen.getByRole('button', { name: 'Principal (máxima)' })).toBeDefined()
      expect(screen.getByRole('button', { name: 'Substream (704×480)' })).toBeDefined()
      // Seletores de OPERAÇÃO continuam presentes e distintos
      expect(screen.getByText(/FPS de inferência/i)).toBeDefined()
      expect(screen.getByText(/Qualidade do stream/i)).toBeDefined()
    })

    it('escolher Substream na coleta e salvar chama patchConfig só com collection_subtype (fps/quality inalterados)', async () => {
      const onSaved = vi.fn()
      render(<CameraFpsConfig camera={camera} onSaved={onSaved} />)

      await waitFor(() => {
        expect(mocks.getHealthContext).toHaveBeenCalled()
      })

      fireEvent.click(screen.getByRole('button', { name: 'Substream (704×480)' }))
      fireEvent.click(screen.getByRole('button', { name: /Salvar configuração/i }))

      await waitFor(() => {
        expect(mocks.patchConfig).toHaveBeenCalledWith('cam-1', {
          fps_target: 5,
          quality_preset: 'medium',
          collection_subtype: 1,
        })
        expect(onSaved).toHaveBeenCalled()
      })
    })

    it('não muda fps nem quality no payload quando só a coleta é alterada e o resto já mudou antes', async () => {
      render(<CameraFpsConfig camera={camera} onSaved={vi.fn()} />)
      await waitFor(() => expect(mocks.getHealthContext).toHaveBeenCalled())

      // fps muda, coleta muda — quality permanece o valor original da câmera
      fireEvent.click(screen.getByRole('button', { name: '10 fps' }))
      fireEvent.click(screen.getByRole('button', { name: 'Substream (704×480)' }))
      fireEvent.click(screen.getByRole('button', { name: /Salvar configuração/i }))

      await waitFor(() => {
        expect(mocks.patchConfig).toHaveBeenCalledWith('cam-1', {
          fps_target: 10,
          quality_preset: 'medium',
          collection_subtype: 1,
        })
      })
    })

    it('alerta de desalinhamento aparece quando coleta=0 e operação está no substream', async () => {
      render(
        <CameraFpsConfig
          camera={{ ...camera, collection_subtype: 0, live_view_subtype: 1 }}
          onSaved={vi.fn()}
        />,
      )
      await waitFor(() => expect(mocks.getHealthContext).toHaveBeenCalled())

      expect(screen.getByText(/Coleta em alta, operação em baixa/i)).toBeDefined()
    })

    it('alerta some quando o usuário muda a coleta para substream (coleta=1)', async () => {
      render(
        <CameraFpsConfig
          camera={{ ...camera, collection_subtype: 0, live_view_subtype: 1 }}
          onSaved={vi.fn()}
        />,
      )
      await waitFor(() => expect(mocks.getHealthContext).toHaveBeenCalled())
      expect(screen.getByText(/Coleta em alta, operação em baixa/i)).toBeDefined()

      fireEvent.click(screen.getByRole('button', { name: 'Substream (704×480)' }))

      expect(screen.queryByText(/Coleta em alta, operação em baixa/i)).toBeNull()
    })

    it('sem alerta quando coleta e operação já estão alinhadas (ambas em alta)', async () => {
      render(
        <CameraFpsConfig
          camera={{ ...camera, collection_subtype: 0, live_view_subtype: 0 }}
          onSaved={vi.fn()}
        />,
      )
      await waitFor(() => expect(mocks.getHealthContext).toHaveBeenCalled())

      expect(screen.queryByText(/Coleta em alta, operação em baixa/i)).toBeNull()
    })
  })
})
