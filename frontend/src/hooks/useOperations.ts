/**
 * Hook CRUD para operações configuráveis via REST.
 * Segue padrão dos outros hooks do projeto (sem Zustand — estado local).
 */
import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api'
import type { Operation, OperationCreate, OperationUpdate, OperationType } from '../types/operations'

interface UseOperationsOptions {
  cameraId: string | number
  moduleId?: string
  enabled?: boolean
}

export function useOperations({ cameraId, moduleId, enabled = true }: UseOperationsOptions) {
  const [operations, setOperations] = useState<Operation[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchOperations = useCallback(async () => {
    if (!enabled || !cameraId) return
    setLoading(true)
    setError(null)
    try {
      const params = moduleId ? `?module_id=${moduleId}` : ''
      const res = await api.get<{ status: string; data: { operations: Operation[] } }>(
        `/cameras/${cameraId}/operations${params}`
      )
      setOperations(res.data.operations ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar operações')
    } finally {
      setLoading(false)
    }
  }, [cameraId, moduleId, enabled])

  useEffect(() => {
    fetchOperations()
  }, [fetchOperations])

  const createOperation = useCallback(
    async (data: OperationCreate): Promise<Operation> => {
      const res = await api.post<{ status: string; data: { operation: Operation } }>(
        `/cameras/${cameraId}/operations`,
        data
      )
      const created = res.data.operation
      setOperations(prev => [...prev, created])
      return created
    },
    [cameraId]
  )

  const updateOperation = useCallback(
    async (operationId: number, data: OperationUpdate): Promise<Operation> => {
      const res = await api.put<{ status: string; data: { operation: Operation } }>(
        `/operations/${operationId}`,
        data
      )
      const updated = res.data.operation
      setOperations(prev => prev.map(op => (op.id === operationId ? updated : op)))
      return updated
    },
    []
  )

  const deleteOperation = useCallback(
    async (operationId: number, confirmName?: string): Promise<void> => {
      const params = confirmName ? `?confirm_name=${encodeURIComponent(confirmName)}` : ''
      await api.delete(`/operations/${operationId}${params}`)
      setOperations(prev => prev.filter(op => op.id !== operationId))
    },
    []
  )

  return {
    operations,
    loading,
    error,
    refetch: fetchOperations,
    createOperation,
    updateOperation,
    deleteOperation,
  }
}

interface UseOperationTypesOptions {
  moduleId: string
  enabled?: boolean
}

export function useOperationTypes({ moduleId, enabled = true }: UseOperationTypesOptions) {
  const [types, setTypes] = useState<OperationType[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!enabled || !moduleId) return
    setLoading(true)
    api
      .get<{ status: string; data: { types: OperationType[] } }>(
        `/modules/${moduleId}/operation-types`
      )
      .then(res => setTypes(res.data.types ?? []))
      .catch(() => setTypes([]))
      .finally(() => setLoading(false))
  }, [moduleId, enabled])

  return { types, loading }
}
