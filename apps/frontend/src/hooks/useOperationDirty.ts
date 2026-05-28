/**
 * Detecta alterações não salvas em operações durante modo de edição.
 * Usado para exibir confirmação "Descartar alterações?" ao sair sem salvar.
 */
import { useCallback, useState } from 'react'
import type { OperationUpdate } from '../types/operations'

export function useOperationDirty() {
  const [dirtyOperations, setDirtyOperations] = useState<Map<number, OperationUpdate>>(new Map())

  const markDirty = useCallback((operationId: number, update: OperationUpdate) => {
    setDirtyOperations(prev => new Map(prev).set(operationId, update))
  }, [])

  const clearDirty = useCallback((operationId?: number) => {
    if (operationId !== undefined) {
      setDirtyOperations(prev => {
        const next = new Map(prev)
        next.delete(operationId)
        return next
      })
    } else {
      setDirtyOperations(new Map())
    }
  }, [])

  const isDirty = dirtyOperations.size > 0
  const getDirtyUpdate = useCallback(
    (operationId: number) => dirtyOperations.get(operationId),
    [dirtyOperations]
  )

  return { isDirty, dirtyOperations, markDirty, clearDirty, getDirtyUpdate }
}
