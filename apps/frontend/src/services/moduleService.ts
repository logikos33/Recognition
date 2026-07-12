import { api } from './api'

export interface ModuleClass {
  id: string
  module_code: string
  class_id: number
  class_name: string
  display_name: string
  icon: string
  is_violation: boolean
  color: string
}

export interface ModuleStats {
  cameras_active: number
  cameras_total: number
  alerts_today: number
  alerts_week: number
}

// api.ts returns the full envelope: { status, data }
type R<T> = { status: string; data: T }

export interface Module {
  id: string
  module_code: string
  enabled: boolean
  cameras_count?: number
  alerts_today?: number
  config?: Record<string, unknown>
}

export const moduleService = {
  list: async (): Promise<Module[]> => {
    const res = await api.get<R<{ modules: Module[] }>>('/modules/')
    return res.data?.modules ?? []
  },

  get: async (moduleCode: string): Promise<Module | null> => {
    const res = await api.get<R<{ module: Module }>>(`/modules/${moduleCode}`)
    return res.data?.module ?? null
  },

  getClasses: async (moduleCode: string): Promise<ModuleClass[]> => {
    const res = await api.get<R<{ classes: ModuleClass[] }>>(`/modules/${moduleCode}/classes`)
    return res.data?.classes ?? []
  },

  getStats: async (moduleCode: string): Promise<ModuleStats> => {
    const res = await api.get<R<{ stats: ModuleStats }>>(`/modules/${moduleCode}/stats`)
    return res.data?.stats ?? { cameras_active: 0, cameras_total: 0, alerts_today: 0, alerts_week: 0 }
  },
}
