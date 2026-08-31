/**
 * Regressão: cenário crashava com "Cannot read properties of undefined
 * (reading 'scenario')".
 *
 * Causa raiz: useScenario chamava `/cameras/${id}/scenario` SEM o prefixo
 * `/v1` — a rota real é `/api/v1/cameras/<id>/scenario`. O path errado não
 * dava 404: caía no catch-all SPA do backend, que respondia 200 sem a chave
 * `data`, e o hook lia `.scenario` de undefined direto no render.
 *
 * Mesmo bug em useScenarioOperationTypes (`/scenarios/operation-types`).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { api } from '../../services/api'
import { useScenario, useScenarioOperationTypes } from '../../hooks/useScenario'

vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof import('../../services/api')>('../../services/api')
  return { ...actual, api: { ...actual.api, get: vi.fn() } }
})

beforeEach(() => {
  vi.resetAllMocks()
})

describe('useScenario', () => {
  it('chama GET com o prefixo /v1', async () => {
    vi.mocked(api.get).mockResolvedValue({
      success: true,
      data: { scenario: { camera: { id: 'cam-1', name: 'Cam 1' }, modules: [], operations: [], alert_rules: [], schedule: [] } },
    })

    const { result } = renderHook(() => useScenario({ cameraId: 'cam-1' }))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(api.get).toHaveBeenCalledWith('/v1/cameras/cam-1/scenario')
    expect(result.current.error).toBeNull()
    expect(result.current.scenario?.camera.id).toBe('cam-1')
  })

  it('resposta 200 sem `data.scenario` (catch-all) vira erro tratado, nunca exceção', async () => {
    // Formato do bug real: 200 "API online" sem chave `data`.
    vi.mocked(api.get).mockResolvedValue({ status: 'API online' } as never)

    const { result } = renderHook(() => useScenario({ cameraId: 'cam-1' }))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.error).toBeTruthy()
    expect(result.current.scenario).toBeNull()
  })
})

describe('useScenarioOperationTypes', () => {
  it('chama GET com o prefixo /v1', async () => {
    vi.mocked(api.get).mockResolvedValue({ success: true, data: { types: [] } })

    const { result } = renderHook(() => useScenarioOperationTypes({ moduleCode: 'epi' }))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(api.get).toHaveBeenCalledWith('/v1/scenarios/operation-types?module=epi')
  })

  it('resposta sem `data.types` não lança — cai em lista vazia', async () => {
    vi.mocked(api.get).mockResolvedValue({ status: 'API online' } as never)

    const { result } = renderHook(() => useScenarioOperationTypes({ moduleCode: 'epi' }))

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.types).toEqual([])
  })
})
