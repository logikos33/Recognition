/**
 * Tipos para o cenário de câmera — espelha o DTO da Scenario API (task-022).
 */

export interface ScenarioCamera {
  id: string
  name: string
  site_id?: string | null
}

export interface ScenarioModuleClass {
  id: string | number
  class_name: string
  display_name?: string
  color?: string
}

export interface ScenarioModule {
  module_code: string
  enabled: boolean
  config?: Record<string, unknown> | null
  activated_at?: string | null
  expires_at?: string | null
  classes: ScenarioModuleClass[]
}

export interface Scenario {
  camera: ScenarioCamera
  modules: ScenarioModule[]
  operations: Array<Record<string, unknown>>
  alert_rules: Array<Record<string, unknown>>
  schedule: unknown[]
}
