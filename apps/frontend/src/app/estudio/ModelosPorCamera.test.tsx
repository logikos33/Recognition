/**
 * O que esta tela não pode errar:
 *
 *  · reimplementar carregando/erro/vazio por cima do CameraModelScope — ele já
 *    é o núcleo compartilhado com os próprios estados, e é `TrainingPage.tsx`
 *    quem prova que passar `classesCatalogo` sem bloquear a tela é o
 *    comportamento correto (fallback, não requisito);
 *  · deixar de repassar `classesCatalogo` — sem isso a câmera cujo modelo não
 *    tem `class_distribution` própria perde o nome das classes.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const get = vi.fn()
vi.mock('../../services/api', () => ({ api: { get: (...a: unknown[]) => get(...a) } }))

const scope = vi.hoisted(() => ({ props: null as { classesCatalogo: unknown[] } | null }))
vi.mock('../../components/training/CameraModelScope', () => ({
  CameraModelScope: (props: { classesCatalogo: unknown[] }) => {
    scope.props = props
    return <div>camera-model-scope</div>
  },
}))

import { ModelosPorCamera } from './ModelosPorCamera'

beforeEach(() => {
  get.mockReset()
  scope.props = null
})

describe('ModelosPorCamera', () => {
  it('título h2 padrão e o núcleo compartilhado montado', () => {
    get.mockResolvedValue({ data: [] })
    render(<ModelosPorCamera />)
    expect(screen.getByRole('heading', { level: 2, name: 'Modelos por câmera' })).toBeTruthy()
    expect(screen.getByText('camera-model-scope')).toBeTruthy()
  })

  it('repassa classesCatalogo com as classes reais do tenant (GET /classes)', async () => {
    get.mockResolvedValue({ data: [{ id: 1, name: 'Capacete', color: '#22d3ee' }] })
    render(<ModelosPorCamera />)
    await waitFor(() => expect(scope.props?.classesCatalogo).toEqual([{ id: 1, name: 'Capacete', color: '#22d3ee' }]))
  })

  it('CameraModelScope monta IMEDIATAMENTE — não espera /classes (fallback, não requisito)', () => {
    get.mockReturnValue(new Promise(() => {})) // nunca resolve
    render(<ModelosPorCamera />)
    expect(screen.getByText('camera-model-scope')).toBeTruthy()
    expect(scope.props?.classesCatalogo).toEqual([])
  })

  it('falha em /classes não quebra a tela — classesCatalogo fica vazio, em silêncio', async () => {
    get.mockRejectedValue(new Error('timeout'))
    render(<ModelosPorCamera />)
    await waitFor(() => expect(get).toHaveBeenCalled())
    expect(screen.getByText('camera-model-scope')).toBeTruthy()
    expect(scope.props?.classesCatalogo).toEqual([])
  })
})
