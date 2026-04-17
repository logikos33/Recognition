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

export const moduleService = {
  list: async (): Promise<any[]> => {
    const res = await api.get<R<{ modules: any[] }>>('/modules/')
    return res.data?.modules ?? []
  },

  get: async (moduleCode: string): Promise<any> => {
    const res = await api.get<R<{ module: any }>>(`/modules/${moduleCode}`)
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
