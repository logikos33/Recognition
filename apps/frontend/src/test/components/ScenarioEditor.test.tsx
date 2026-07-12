/**
 * Testes Vitest/RTL para ScenarioEditor.
 * Padrão: mocks nos hooks/serviços; nenhuma chamada de rede real.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { ScenarioEditor } from '../../components/scenario/ScenarioEditor'
import type { Scenario } from '../../types/scenario'
import type { Operation, OperationType } from '../../types/operations'

// Mocks de módulos externos
vi.mock('../../hooks/useScenario', () => ({
  useScenario: vi.fn(),
  useScenarioOperationTypes: vi.fn(),
}))

vi.mock('../../hooks/useOperations', () => ({
  useOperations: vi.fn(),
}))

// CameraPlayer usa HLS.js — não funciona no jsdom
vi.mock('../../components/monitoring/CameraPlayer', () => ({
  CameraPlayer: () => <div data-testid="camera-player" />,
}))

import { useScenario, useScenarioOperationTypes } from '../../hooks/useScenario'
import { useOperations } from '../../hooks/useOperations'

const mockScenario: Scenario = {
  camera: { id: '1', name: 'Câmera Portão' },
  modules: [
    {
      module_code: 'epi',
      enabled: true,
      classes: [
        { id: 1, class_name: 'helmet', display_name: 'Capacete' },
        { id: 2, class_name: 'vest', display_name: 'Colete' },
      ],
    },
    {
      module_code: 'fueling',
      enabled: true,
      classes: [{ id: 3, class_name: 'truck', display_name: 'Caminhão' }],
    },
  ],
  operations: [],
  alert_rules: [],
  schedule: [],
}

const mockTypes: OperationType[] = [
  {
    type_id: 'position',
    type_label: 'Posição / Presença',
    description: 'Detecta presença em zona',
    available_modules: ['epi'],
    config_schema: { roi_points: {} },
    metric_options: ['state'],
    output_formats: ['conditional'],
  },
  {
    type_id: 'count_static',
    type_label: 'Contagem Estática',
    available_modules: ['epi'],
    config_schema: { roi_points: {}, count_threshold: {} },
    metric_options: ['count'],
    output_formats: ['physical'],
  },
  {
    type_id: 'epi_zone',
    type_label: 'Zona EPI',
    description: 'Alerta quando classe de EPI negativo é detectada dentro de uma zona definida.',
    available_modules: ['epi'],
    // task-039: exclude_zones + day_night_profile — ver services/api/.../canonical/epi_zone.py
    config_schema: {
      zone_points: {}, watch_classes: {}, confidence_threshold: {},
      exclude_zones: {}, day_night_profile: {},
    },
    metric_options: ['violation_detected', 'violation_count'],
    output_formats: ['physical', 'conditional', 'both'],
  },
]

const mockCreateOperation = vi.fn().mockResolvedValue({ id: 99, name: 'Nova Op' } as Operation)
const mockRefetch = vi.fn()

function setupMocks(overrides: { scenarioError?: string; scenarioLoading?: boolean } = {}) {
  vi.mocked(useScenario).mockReturnValue({
    scenario: overrides.scenarioLoading || overrides.scenarioError ? null : mockScenario,
    loading: overrides.scenarioLoading ?? false,
    error: overrides.scenarioError ?? null,
    refetch: mockRefetch,
  })
  vi.mocked(useScenarioOperationTypes).mockReturnValue({
    types: mockTypes,
    loading: false,
  })
  vi.mocked(useOperations).mockReturnValue({
    operations: [],
    loading: false,
    error: null,
    refetch: vi.fn(),
    createOperation: mockCreateOperation,
    updateOperation: vi.fn(),
    deleteOperation: vi.fn(),
  })
}

describe('ScenarioEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
    // Coordenadas previsíveis para cliques no canvas: virtual 100×100 em (0,0) — mesmo padrão de DrawingCanvas.test.tsx
    Element.prototype.getBoundingClientRect = vi.fn(
      () =>
        ({
          left: 0, top: 0, width: 100, height: 100,
          right: 100, bottom: 100, x: 0, y: 0,
          toJSON: () => ({}),
        } as DOMRect)
    )
  })

  it('renderiza o editor com título', () => {
    render(<ScenarioEditor cameraId="1" />)
    expect(screen.getByText('Editor de Cenário')).toBeDefined()
  })

  it('exibe nome da câmera do cenário', () => {
    render(<ScenarioEditor cameraId="1" />)
    expect(screen.getByText('Câmera Portão')).toBeDefined()
  })

  it('exibe botões de módulo para cada módulo habilitado', () => {
    render(<ScenarioEditor cameraId="1" />)
    expect(screen.getByTestId('module-btn-epi')).toBeDefined()
    expect(screen.getByTestId('module-btn-fueling')).toBeDefined()
  })

  it('auto-seleciona o primeiro módulo habilitado', () => {
    render(<ScenarioEditor cameraId="1" />)
    const epiBtn = screen.getByTestId('module-btn-epi')
    expect(epiBtn.getAttribute('aria-checked')).toBe('true')
  })

  it('exibe tipos de operação após selecionar módulo', async () => {
    render(<ScenarioEditor cameraId="1" />)
    await waitFor(() => {
      expect(screen.getByTestId('type-btn-position')).toBeDefined()
      expect(screen.getByTestId('type-btn-count_static')).toBeDefined()
    })
  })

  it('trocar de módulo atualiza os tipos disponíveis', async () => {
    vi.mocked(useScenarioOperationTypes).mockImplementation(({ moduleCode }) => ({
      types: moduleCode === 'epi' ? mockTypes : [],
      loading: false,
    }))
    render(<ScenarioEditor cameraId="1" />)
    fireEvent.click(screen.getByTestId('module-btn-fueling'))
    await waitFor(() => {
      expect(screen.queryByTestId('type-btn-position')).toBeNull()
    })
  })

  it('exibe ferramentas de desenho ao selecionar tipo', async () => {
    render(<ScenarioEditor cameraId="1" />)
    await waitFor(() => screen.getByTestId('type-btn-position'))
    fireEvent.click(screen.getByTestId('type-btn-position'))
    expect(screen.getByLabelText(/ferramenta zone \(ativa\)/i)).toBeDefined()
  })

  it('exibe campo de nome da operação após selecionar tipo', async () => {
    render(<ScenarioEditor cameraId="1" />)
    await waitFor(() => screen.getByTestId('type-btn-position'))
    fireEvent.click(screen.getByTestId('type-btn-position'))
    expect(screen.getByTestId('op-name-input')).toBeDefined()
  })

  it('exibe classes do módulo selecionado', async () => {
    render(<ScenarioEditor cameraId="1" />)
    await waitFor(() => screen.getByTestId('type-btn-position'))
    fireEvent.click(screen.getByTestId('type-btn-position'))
    expect(screen.getByLabelText(/Capacete/i)).toBeDefined()
    expect(screen.getByLabelText(/Colete/i)).toBeDefined()
  })

  it('botão salvar desabilitado sem nome e sem geometria', async () => {
    render(<ScenarioEditor cameraId="1" />)
    await waitFor(() => screen.getByTestId('type-btn-position'))
    fireEvent.click(screen.getByTestId('type-btn-position'))
    const btn = screen.getByTestId('save-btn') as HTMLButtonElement
    expect(btn.disabled).toBe(true)
  })

  it('exibe estado de loading do cenário', () => {
    setupMocks({ scenarioLoading: true })
    render(<ScenarioEditor cameraId="1" />)
    expect(screen.getByText(/Carregando cenário/i)).toBeDefined()
  })

  it('exibe mensagem de erro quando cenário falha', () => {
    setupMocks({ scenarioError: 'Câmera não encontrada' })
    render(<ScenarioEditor cameraId="1" />)
    expect(screen.getByRole('alert')).toBeDefined()
    expect(screen.getByText(/Câmera não encontrada/i)).toBeDefined()
  })

  it('botão voltar chama onBack', () => {
    const onBack = vi.fn()
    render(<ScenarioEditor cameraId="1" onBack={onBack} />)
    fireEvent.click(screen.getByLabelText('Voltar'))
    expect(onBack).toHaveBeenCalledOnce()
  })

  it('DrawingCanvas está presente no editor', () => {
    render(<ScenarioEditor cameraId="1" />)
    expect(screen.getByTestId('drawing-canvas')).toBeDefined()
  })

  // ── task-039: zonas de exclusão + perfil dia/noite (epi_zone / defect_trigger) ──

  describe('per-camera tuning: exclude_zones + day_night_profile', () => {
    function clickCanvas(points: Array<[number, number]>) {
      const layer = screen.getByTestId('canvas-interaction-layer')
      for (const [x, y] of points) {
        fireEvent.click(layer, { clientX: x, clientY: y })
      }
    }

    it('não exibe controles de zona de exclusão / perfil dia-noite para tipos sem suporte (position)', async () => {
      render(<ScenarioEditor cameraId="1" />)
      await waitFor(() => screen.getByTestId('type-btn-position'))
      fireEvent.click(screen.getByTestId('type-btn-position'))

      expect(screen.queryByTestId('draw-mode-exclude-btn')).toBeNull()
      expect(screen.queryByTestId('day-night-enabled-checkbox')).toBeNull()
    })

    it('exibe controles de zona de exclusão e perfil dia/noite para epi_zone', async () => {
      render(<ScenarioEditor cameraId="1" />)
      await waitFor(() => screen.getByTestId('type-btn-epi_zone'))
      fireEvent.click(screen.getByTestId('type-btn-epi_zone'))

      expect(screen.getByTestId('draw-mode-main-btn')).toBeDefined()
      expect(screen.getByTestId('draw-mode-exclude-btn')).toBeDefined()
      expect(screen.getByTestId('day-night-enabled-checkbox')).toBeDefined()
    })

    it('botão "Adicionar zona" fica desabilitado até desenhar 3 pontos', async () => {
      render(<ScenarioEditor cameraId="1" />)
      await waitFor(() => screen.getByTestId('type-btn-epi_zone'))
      fireEvent.click(screen.getByTestId('type-btn-epi_zone'))
      fireEvent.click(screen.getByTestId('draw-mode-exclude-btn'))

      const addBtn = screen.getByTestId('add-exclude-zone-btn') as HTMLButtonElement
      expect(addBtn.disabled).toBe(true)

      clickCanvas([[10, 10], [50, 10]])
      expect((screen.getByTestId('add-exclude-zone-btn') as HTMLButtonElement).disabled).toBe(true)

      clickCanvas([[30, 50]])
      expect((screen.getByTestId('add-exclude-zone-btn') as HTMLButtonElement).disabled).toBe(false)
    })

    it('desenhar e adicionar zona de exclusão exibe na lista; remover a retira', async () => {
      render(<ScenarioEditor cameraId="1" />)
      await waitFor(() => screen.getByTestId('type-btn-epi_zone'))
      fireEvent.click(screen.getByTestId('type-btn-epi_zone'))
      fireEvent.click(screen.getByTestId('draw-mode-exclude-btn'))
      clickCanvas([[10, 10], [50, 10], [30, 50]])
      fireEvent.click(screen.getByTestId('add-exclude-zone-btn'))

      const item = screen.getByTestId('exclude-zone-item-0')
      expect(item.textContent).toMatch(/Zona 1.*3 pontos/)

      // Desenho é resetado após adicionar — botão desabilita de novo
      expect((screen.getByTestId('add-exclude-zone-btn') as HTMLButtonElement).disabled).toBe(true)

      fireEvent.click(screen.getByLabelText('Remover zona de exclusão 1'))
      expect(screen.queryByTestId('exclude-zone-item-0')).toBeNull()
    })

    it('salvar operação epi_zone inclui exclude_zones com o polígono desenhado', async () => {
      render(<ScenarioEditor cameraId="1" />)
      await waitFor(() => screen.getByTestId('type-btn-epi_zone'))
      fireEvent.click(screen.getByTestId('type-btn-epi_zone'))
      fireEvent.change(screen.getByTestId('op-name-input'), { target: { value: 'Zona com exclusão' } })

      // Geometria principal (modo 'main' é o padrão)
      clickCanvas([[5, 5], [95, 5], [95, 95]])

      // Zona de exclusão
      fireEvent.click(screen.getByTestId('draw-mode-exclude-btn'))
      clickCanvas([[10, 10], [50, 10], [30, 50]])
      fireEvent.click(screen.getByTestId('add-exclude-zone-btn'))

      await waitFor(() => {
        expect((screen.getByTestId('save-btn') as HTMLButtonElement).disabled).toBe(false)
      })
      fireEvent.click(screen.getByTestId('save-btn'))

      await waitFor(() => expect(mockCreateOperation).toHaveBeenCalledOnce())
      const [payload] = mockCreateOperation.mock.calls[0]
      expect(payload.type_id).toBe('epi_zone')
      expect(Array.isArray(payload.config.exclude_zones)).toBe(true)
      expect(payload.config.exclude_zones.length).toBe(1)
      expect(payload.config.exclude_zones[0]).toEqual([[0.1, 0.1], [0.5, 0.1], [0.3, 0.5]])
    })

    it('salvar sem zonas de exclusão ainda inclui exclude_zones vazio (default do schema)', async () => {
      render(<ScenarioEditor cameraId="1" />)
      await waitFor(() => screen.getByTestId('type-btn-epi_zone'))
      fireEvent.click(screen.getByTestId('type-btn-epi_zone'))
      fireEvent.change(screen.getByTestId('op-name-input'), { target: { value: 'Zona simples' } })
      clickCanvas([[5, 5], [95, 5], [95, 95]])

      fireEvent.click(screen.getByTestId('save-btn'))
      await waitFor(() => expect(mockCreateOperation).toHaveBeenCalledOnce())

      const [payload] = mockCreateOperation.mock.calls[0]
      expect(payload.config.exclude_zones).toEqual([])
      expect(payload.config.day_night_profile).toBeUndefined()
    })

    it('habilitar perfil dia/noite e salvar inclui day_night_profile com os valores configurados', async () => {
      render(<ScenarioEditor cameraId="1" />)
      await waitFor(() => screen.getByTestId('type-btn-epi_zone'))
      fireEvent.click(screen.getByTestId('type-btn-epi_zone'))
      fireEvent.change(screen.getByTestId('op-name-input'), { target: { value: 'Zona dia/noite' } })
      clickCanvas([[5, 5], [95, 5], [95, 95]])

      fireEvent.click(screen.getByTestId('day-night-enabled-checkbox'))
      fireEvent.change(screen.getByTestId('day-confidence-input'), { target: { value: '0.4' } })
      fireEvent.change(screen.getByTestId('night-confidence-input'), { target: { value: '0.8' } })

      fireEvent.click(screen.getByTestId('save-btn'))
      await waitFor(() => expect(mockCreateOperation).toHaveBeenCalledOnce())

      const [payload] = mockCreateOperation.mock.calls[0]
      const profile = payload.config.day_night_profile as Record<string, { confidence: number }>
      expect(profile).toBeDefined()
      expect(profile.day.confidence).toBe(0.4)
      expect(profile.night.confidence).toBe(0.8)
    })

    it('confidence de dia/noite é limitada ao intervalo [0.1, 1.0] no próprio input (validação client-side)', async () => {
      render(<ScenarioEditor cameraId="1" />)
      await waitFor(() => screen.getByTestId('type-btn-epi_zone'))
      fireEvent.click(screen.getByTestId('type-btn-epi_zone'))
      fireEvent.click(screen.getByTestId('day-night-enabled-checkbox'))

      const dayInput = screen.getByTestId('day-confidence-input') as HTMLInputElement
      fireEvent.change(dayInput, { target: { value: '5' } })
      expect(dayInput.value).toBe('1')

      fireEvent.change(dayInput, { target: { value: '0' } })
      expect(dayInput.value).toBe('0.1')
    })

    it('trocar de tipo reseta zonas de exclusão e perfil dia/noite', async () => {
      render(<ScenarioEditor cameraId="1" />)
      await waitFor(() => screen.getByTestId('type-btn-epi_zone'))
      fireEvent.click(screen.getByTestId('type-btn-epi_zone'))
      fireEvent.click(screen.getByTestId('draw-mode-exclude-btn'))
      clickCanvas([[10, 10], [50, 10], [30, 50]])
      fireEvent.click(screen.getByTestId('add-exclude-zone-btn'))
      expect(screen.getByTestId('exclude-zone-item-0')).toBeDefined()

      fireEvent.click(screen.getByTestId('type-btn-count_static'))
      fireEvent.click(screen.getByTestId('type-btn-epi_zone'))

      expect(screen.queryByTestId('exclude-zone-item-0')).toBeNull()
    })
  })
})
