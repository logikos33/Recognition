/**
 * O assistente de cenário oferece as classes do TENANT, não as da demonstração.
 *
 * `EPI_CLASS_OPTIONS` (`helmet/no_helmet/vest/no_vest/gloves/no_gloves/…`) é a
 * taxonomia COCO de exemplo. Ela não existe em cliente nenhum: no RVB as
 * classes são "Protetor auditivo", "Sem protetor de ouvido", "Uso incorreto de
 * mascara"… Um admin configurava aqui um cenário sobre classes que o modelo
 * dele nunca emite, e nada reclamava.
 *
 * Mesmo defeito do #544 no backend, e do anotador antes dele — o docstring de
 * `module_service.get_classes` registra que classe custom do tenant "sumia" na
 * tela porque só o catálogo global era consultado.
 *
 * `GET /api/modules/{code}/classes` devolve catálogo global ∪ custom do tenant.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

vi.mock('../../hooks/useModuleClasses', () => ({
  useModuleClasses: vi.fn(),
}))

vi.mock('../../services/api', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: { scenario_config: null, cameras: [] } }),
    put: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

// Canvas/SVG pesados — irrelevantes para o passo de classes
vi.mock('../../components/scenario/CountingLineCanvas', () => ({
  CountingLineCanvas: () => <div data-testid="counting-line" />,
}))
vi.mock('../../components/training/canvas/RoiDrawer', () => ({
  RoiDrawer: () => <div data-testid="roi" />,
}))

import { ModelScenarioWizard } from '../../components/scenario/ModelScenarioWizard'
import { useModuleClasses } from '../../hooks/useModuleClasses'

const mocked = vi.mocked(useModuleClasses)

/** O que o cadastro do RVB realmente tem. */
const CLASSES_RVB = [
  { id: '1', module_code: 'epi', class_id: 100001, class_name: 'Protetor auditivo',
    display_name: 'Protetor auditivo', icon: '', is_violation: false, color: '#0f0' },
  { id: '2', module_code: 'epi', class_id: 100002, class_name: 'Sem protetor de ouvido',
    display_name: 'Sem protetor de ouvido', icon: '', is_violation: true, color: '#f00' },
  { id: '3', module_code: 'epi', class_id: 100003, class_name: 'Uso incorreto de mascara',
    display_name: 'Uso incorreto de mascara', icon: '', is_violation: true, color: '#f80' },
]

async function abreNoPassoDeClasses() {
  render(
    <ModelScenarioWizard modelId="m1" modelName="Modelo RVB" onClose={() => {}} />,
  )
  // ⚠️ o clique fica FORA do waitFor: waitFor reexecuta o callback até passar,
  // e clicar lá dentro avançava o wizard várias vezes.
  const proximo = await screen.findByRole('button', { name: /avan|próx|next/i })
  fireEvent.click(proximo)
  await screen.findByText(/Selecione as classes/i)
}

describe('ModelScenarioWizard — passo de classes', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('oferece as classes do tenant quando a API responde', async () => {
    mocked.mockReturnValue({
      classes: CLASSES_RVB, loading: false, classLabel: (c: string) => c,
    })
    await abreNoPassoDeClasses()

    await waitFor(() => {
      expect(screen.getByText('Sem protetor de ouvido')).toBeTruthy()
    })
    expect(screen.getByText('Uso incorreto de mascara')).toBeTruthy()
    // e NÃO a taxonomia de demonstração
    expect(screen.queryByText('Sem Capacete')).toBeNull()
    expect(screen.queryByText('Sem Colete')).toBeNull()
  })

  it('cai no fallback estático enquanto a API não respondeu', async () => {
    // enriquecimento, não bloqueio: a tela continua utilizável
    mocked.mockReturnValue({
      classes: [], loading: true, classLabel: (c: string) => c,
    })
    await abreNoPassoDeClasses()

    await waitFor(() => {
      expect(screen.getByText('Sem Capacete')).toBeTruthy()
    })
  })

  it('pede as classes do módulo epi', async () => {
    mocked.mockReturnValue({
      classes: CLASSES_RVB, loading: false, classLabel: (c: string) => c,
    })
    await abreNoPassoDeClasses()
    await waitFor(() => {
      expect(mocked).toHaveBeenCalledWith('epi')
    })
  })
})
