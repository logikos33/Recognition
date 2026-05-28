import { useState, useEffect } from 'react'
import { moduleService } from '../services/moduleService'

export interface Module {
  id: string
  module_code: string
  enabled: boolean
  cameras_count: number
  alerts_today: number
  config: Record<string, unknown>
}

export function useModules() {
  const [modules, setModules] = useState<Module[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadModules()
  }, [])

  const loadModules = async () => {
    try {
      setLoading(true)
      const result = await moduleService.list()
      setModules(result || [])
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar módulos')
    } finally {
      setLoading(false)
    }
  }

  const hasModule = (code: string): boolean =>
    modules.some(m => m.module_code === code && m.enabled)

  const getModule = (code: string): Module | undefined =>
    modules.find(m => m.module_code === code)

  return { modules, loading, error, hasModule, getModule, refresh: loadModules }
}
