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
})
