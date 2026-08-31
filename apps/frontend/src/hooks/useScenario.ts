/**
 * Hooks para leitura de cenário e catálogo de operation-types da Scenario API (task-022).
 * Seguem o mesmo padrão de useOperations.ts (estado local, sem Zustand).
 */
import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api'
import type { Scenario } from '../types/scenario'
import type { OperationType } from '../types/operations'

// Envelope real da API (app/core/responses.py): {success, message, data}.
// NUNCA {status, data} — isso não existe no backend.
interface ApiEnvelope<T> {
  success: boolean
  message?: string
  data?: T
}

interface UseScenarioOptions {
  cameraId: string
  enabled?: boolean
}

export function useScenario({ cameraId, enabled = true }: UseScenarioOptions) {
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchScenario = useCallback(async () => {
    if (!enabled || !cameraId) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.get<ApiEnvelope<{ scenario: Scenario }>>(
        `/v1/cameras/${cameraId}/scenario`
      )
      // Guarda de shape: resposta 200 sem `data.scenario` (ex.: catch-all de
      // rota inexistente) é tratada como erro humano, nunca crash de render.
      if (!res.data?.scenario) {
        setError('Resposta inesperada do servidor ao carregar cenário')
        return
      }
      setScenario(res.data.scenario)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar cenário')
    } finally {
      setLoading(false)
    }
  }, [cameraId, enabled])

  useEffect(() => { fetchScenario() }, [fetchScenario])

  return { scenario, loading, error, refetch: fetchScenario }
}

interface UseScenarioOperationTypesOptions {
  moduleCode: string
  enabled?: boolean
}

export function useScenarioOperationTypes({ moduleCode, enabled = true }: UseScenarioOperationTypesOptions) {
  const [types, setTypes] = useState<OperationType[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!enabled || !moduleCode) return
    setLoading(true)
    api
      .get<ApiEnvelope<{ types: OperationType[] }>>(
        `/v1/scenarios/operation-types?module=${encodeURIComponent(moduleCode)}`
      )
      .then(res => setTypes(res.data?.types ?? []))
      .catch(() => setTypes([]))
      .finally(() => setLoading(false))
  }, [moduleCode, enabled])

  return { types, loading }
}
