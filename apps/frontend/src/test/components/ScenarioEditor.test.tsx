import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { useOperations, useOperationTypes } from '../../hooks/useOperations'
import { ScenarioEditor } from '../../components/scenario/ScenarioEditor'

vi.mock('../../hooks/useOperations', () => ({
  useOperations: vi.fn(),
  useOperationTypes: vi.fn(),
}))

const mockCreateOperation = vi.fn()

const defaultOpsReturn = {
  operations: [],
  loading: false,
  error: null,
  refetch: vi.fn(),
  createOperation: mockCreateOperation,
  updateOperation: vi.fn(),
  deleteOperation: vi.fn(),
}

const defaultTypesReturn = {
  types: [
    {
      type_id: 'zone_presence',
      type_label: 'Zona de Presença',
      description: '',
      available_modules: ['ppe'],
      config_schema: {},
      metric_options: [],
      output_formats: [],
    },
  ],
  loading: false,
}

beforeEach(() => {
  vi.mocked(useOperations).mockReturnValue(defaultOpsReturn)
  vi.mocked(useOperationTypes).mockReturnValue(defaultTypesReturn)
  mockCreateOperation.mockReset()
  mockCreateOperation.mockResolvedValue({
    id: 1, name: 'test', status: 'active',
    camera_id: 'cam1', module_id: 'ppe', type_id: 'zone_presence',
    config: {}, version: 1, created_at: '',
  })
  // Coordenadas previsíveis para interação com o canvas
  Element.prototype.getBoundingClientRect = vi.fn(
    () =>
      ({
        left: 0, top: 0, width: 100, height: 100,
        right: 100, bottom: 100, x: 0, y: 0,
        toJSON: () => ({}),
      } as DOMRect)
  )
})

describe('ScenarioEditor', () => {
  it('renderiza seletor de módulo e de tipo de operação', () => {
    render(<ScenarioEditor cameraId="cam1" />)
    expect(screen.getByLabelText('Selecionar módulo')).toBeDefined()
    expect(screen.getByLabelText('Selecionar tipo de operação')).toBeDefined()
  })

  it('trocar módulo reseta a seleção de tipo de operação', () => {
    render(<ScenarioEditor cameraId="cam1" />)
    const typeSelect = screen.getByLabelText('Selecionar tipo de operação') as HTMLSelectElement

    fireEvent.change(typeSelect, { target: { value: 'zone_presence' } })
    expect(typeSelect.value).toBe('zone_presence')

    const moduleSelect = screen.getByLabelText('Selecionar módulo') as HTMLSelectElement
    fireEvent.change(moduleSelect, { target: { value: 'fueling' } })
    expect(typeSelect.value).toBe('')
  })

  it('exibe botões de ferramenta de desenho incluindo máscara', () => {
    render(<ScenarioEditor cameraId="cam1" />)
    expect(screen.getByText('Zona (polígono)')).toBeDefined()
    expect(screen.getByText('Linha')).toBeDefined()
    expect(screen.getByText('Ponto')).toBeDefined()
    expect(screen.getByText('Máscara (exclusão)')).toBeDefined()
  })

  it('undo após 3 pontos reduz para 2; redo restaura para 3', () => {
    render(<ScenarioEditor cameraId="cam1" />)
    const layer = screen.getByTestId('canvas-interaction-layer')

    fireEvent.click(layer, { clientX: 10, clientY: 10 })
    fireEvent.click(layer, { clientX: 50, clientY: 50 })
    fireEvent.click(layer, { clientX: 90, clientY: 10 })

    expect(screen.getByText(/3 vértices/)).toBeDefined()

    fireEvent.click(screen.getByLabelText('Desfazer (Ctrl+Z)'))
    expect(screen.getByText(/2 vértices — adicione mais 1/)).toBeDefined()

    fireEvent.click(screen.getByLabelText('Refazer (Ctrl+Shift+Z)'))
    expect(screen.getByText(/3 vértices/)).toBeDefined()
  })

  it('limpar input de limiar com valor inválido não envia NaN — usa valor anterior', async () => {
    render(<ScenarioEditor cameraId="cam1" />)

    fireEvent.change(screen.getByLabelText('Selecionar tipo de operação'), {
      target: { value: 'zone_presence' },
    })
    fireEvent.change(screen.getByLabelText('Nome da operação'), {
      target: { value: 'Teste NaN' },
    })

    // Digitar valor não-numérico — handleThresholdChange ignora NaN
    fireEvent.change(screen.getByLabelText('Limiar de confiança'), {
      target: { value: 'abc' },
    })

    fireEvent.click(screen.getByLabelText('Salvar operação'))

    await waitFor(() => expect(mockCreateOperation).toHaveBeenCalledTimes(1))
    const [payload] = mockCreateOperation.mock.calls[0]
    expect(isNaN(payload.config.threshold as number)).toBe(false)
    expect(payload.config.threshold).toBe(0.5) // valor inicial preservado
  })

  it('exibe estado de erro quando operações falham ao carregar', () => {
    vi.mocked(useOperations).mockReturnValueOnce({
      ...defaultOpsReturn,
      error: 'Erro de rede',
    })
    render(<ScenarioEditor cameraId="cam1" />)
    expect(screen.getByText('Erro de rede')).toBeDefined()
  })

  it('tipo de operação fica desabilitado enquanto tipos carregam', () => {
    vi.mocked(useOperationTypes).mockReturnValueOnce({ types: [], loading: true })
    render(<ScenarioEditor cameraId="cam1" />)
    const typeSelect = screen.getByLabelText('Selecionar tipo de operação') as HTMLSelectElement
    expect(typeSelect.disabled).toBe(true)
  })

  it('botão salvar desabilitado sem tipo ou nome; exibe feedback após salvar', async () => {
    render(<ScenarioEditor cameraId="cam1" />)
    const saveBtn = screen.getByLabelText('Salvar operação') as HTMLButtonElement
    expect(saveBtn.disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('Selecionar tipo de operação'), {
      target: { value: 'zone_presence' },
    })
    fireEvent.change(screen.getByLabelText('Nome da operação'), {
      target: { value: 'Minha Zona' },
    })
    expect(saveBtn.disabled).toBe(false)

    fireEvent.click(saveBtn)
    await waitFor(() => screen.getByText('Operação salva!'))
    expect(mockCreateOperation).toHaveBeenCalledOnce()
  })

  // ── task-039: exclude_zones + day_night_profile ─────────────────────────────

  it('campos de confidence dia e noite estão presentes', () => {
    render(<ScenarioEditor cameraId="cam1" />)
    expect(screen.getByLabelText('Confidence (dia)')).toBeDefined()
    expect(screen.getByLabelText('Confidence (noite)')).toBeDefined()
  })

  it('botão "Adicionar zona de exclusão" não aparece com menos de 3 pontos no modo máscara', () => {
    render(<ScenarioEditor cameraId="cam1" />)
    fireEvent.click(screen.getByText('Máscara (exclusão)'))
    const layer = screen.getByTestId('canvas-interaction-layer')

    // Desenha apenas 2 pontos
    fireEvent.click(layer, { clientX: 10, clientY: 10 })
    fireEvent.click(layer, { clientX: 50, clientY: 10 })

    expect(screen.queryByLabelText('Adicionar zona de exclusão')).toBeNull()
  })

  it('botão "Adicionar zona de exclusão" aparece após 3 pontos no modo máscara', () => {
    render(<ScenarioEditor cameraId="cam1" />)
    fireEvent.click(screen.getByText('Máscara (exclusão)'))
    const layer = screen.getByTestId('canvas-interaction-layer')

    fireEvent.click(layer, { clientX: 10, clientY: 10 })
    fireEvent.click(layer, { clientX: 50, clientY: 10 })
    fireEvent.click(layer, { clientX: 30, clientY: 50 })

    expect(screen.getByLabelText('Adicionar zona de exclusão')).toBeDefined()
  })

  it('adicionar máscara exibe resumo de zonas de exclusão e limpa pontos', () => {
    render(<ScenarioEditor cameraId="cam1" />)
    fireEvent.click(screen.getByText('Máscara (exclusão)'))
    const layer = screen.getByTestId('canvas-interaction-layer')

    fireEvent.click(layer, { clientX: 10, clientY: 10 })
    fireEvent.click(layer, { clientX: 50, clientY: 10 })
    fireEvent.click(layer, { clientX: 30, clientY: 50 })

    fireEvent.click(screen.getByLabelText('Adicionar zona de exclusão'))

    expect(screen.getByText(/1 zona\(s\) de exclusão/)).toBeDefined()
    // Após adicionar, botão some (pontos foram resetados)
    expect(screen.queryByLabelText('Adicionar zona de exclusão')).toBeNull()
  })

  it('salvar inclui exclude_zones quando máscaras foram adicionadas', async () => {
    render(<ScenarioEditor cameraId="cam1" />)

    // Adiciona máscara
    fireEvent.click(screen.getByText('Máscara (exclusão)'))
    const layer = screen.getByTestId('canvas-interaction-layer')
    fireEvent.click(layer, { clientX: 10, clientY: 10 })
    fireEvent.click(layer, { clientX: 50, clientY: 10 })
    fireEvent.click(layer, { clientX: 30, clientY: 50 })
    fireEvent.click(screen.getByLabelText('Adicionar zona de exclusão'))

    // Volta para zone e configura operação
    fireEvent.click(screen.getByText('Zona (polígono)'))
    fireEvent.change(screen.getByLabelText('Selecionar tipo de operação'), {
      target: { value: 'zone_presence' },
    })
    fireEvent.change(screen.getByLabelText('Nome da operação'), {
      target: { value: 'Zona com Máscara' },
    })

    fireEvent.click(screen.getByLabelText('Salvar operação'))
    await waitFor(() => expect(mockCreateOperation).toHaveBeenCalledTimes(1))

    const [payload] = mockCreateOperation.mock.calls[0]
    expect(Array.isArray(payload.config.exclude_zones)).toBe(true)
    expect((payload.config.exclude_zones as unknown[]).length).toBe(1)
  })

  it('salvar inclui day_night_profile quando confidence dia/noite configurados', async () => {
    render(<ScenarioEditor cameraId="cam1" />)

    fireEvent.change(screen.getByLabelText('Selecionar tipo de operação'), {
      target: { value: 'zone_presence' },
    })
    fireEvent.change(screen.getByLabelText('Nome da operação'), {
      target: { value: 'Zona Dia Noite' },
    })
    fireEvent.change(screen.getByLabelText('Confidence (dia)'), {
      target: { value: '0.4' },
    })
    fireEvent.change(screen.getByLabelText('Confidence (noite)'), {
      target: { value: '0.8' },
    })

    fireEvent.click(screen.getByLabelText('Salvar operação'))
    await waitFor(() => expect(mockCreateOperation).toHaveBeenCalledTimes(1))

    const [payload] = mockCreateOperation.mock.calls[0]
    const profile = payload.config.day_night_profile as Record<string, { confidence: number }>
    expect(profile).toBeDefined()
    expect(profile.day.confidence).toBe(0.4)
    expect(profile.night.confidence).toBe(0.8)
  })

  it('salvar sem confidence dia/noite não inclui day_night_profile no config', async () => {
    render(<ScenarioEditor cameraId="cam1" />)

    fireEvent.change(screen.getByLabelText('Selecionar tipo de operação'), {
      target: { value: 'zone_presence' },
    })
    fireEvent.change(screen.getByLabelText('Nome da operação'), {
      target: { value: 'Zona Simples' },
    })

    fireEvent.click(screen.getByLabelText('Salvar operação'))
    await waitFor(() => expect(mockCreateOperation).toHaveBeenCalledTimes(1))

    const [payload] = mockCreateOperation.mock.calls[0]
    expect(payload.config.day_night_profile).toBeUndefined()
  })

  it('salvar bem-sucedido reseta campos dia/noite e zonas de exclusão', async () => {
    render(<ScenarioEditor cameraId="cam1" />)

    // Adiciona máscara
    fireEvent.click(screen.getByText('Máscara (exclusão)'))
    const layer = screen.getByTestId('canvas-interaction-layer')
    fireEvent.click(layer, { clientX: 10, clientY: 10 })
    fireEvent.click(layer, { clientX: 50, clientY: 10 })
    fireEvent.click(layer, { clientX: 30, clientY: 50 })
    fireEvent.click(screen.getByLabelText('Adicionar zona de exclusão'))
    expect(screen.getByText(/1 zona\(s\) de exclusão/)).toBeDefined()

    // Configura e salva
    fireEvent.click(screen.getByText('Zona (polígono)'))
    fireEvent.change(screen.getByLabelText('Selecionar tipo de operação'), {
      target: { value: 'zone_presence' },
    })
    fireEvent.change(screen.getByLabelText('Nome da operação'), { target: { value: 'Op' } })
    fireEvent.change(screen.getByLabelText('Confidence (dia)'), { target: { value: '0.4' } })

    fireEvent.click(screen.getByLabelText('Salvar operação'))
    await waitFor(() => screen.getByText('Operação salva!'))

    // Após salvar: zonas e campos dia/noite resetados
    expect(screen.queryByText(/zona\(s\) de exclusão/)).toBeNull()
    const dayInput = screen.getByLabelText('Confidence (dia)') as HTMLInputElement
    expect(dayInput.value).toBe('')
  })
})
