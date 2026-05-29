/**
 * Tipos para operações configuráveis — compartilhado por todos os componentes training/.
 */

export interface Operation {
  id: number
  camera_id: string
  module_id: string
  type_id: string
  type_label?: string
  name: string
  config: Record<string, unknown>
  status: OperationStatus
  version: number
  last_value_json?: Record<string, unknown>
  last_evaluated_at?: string
  created_at: string
}

export type OperationStatus = 'active' | 'warning' | 'error' | 'inactive'

export interface OperationWithStatus extends Operation {
  live_status?: OperationStatus
  live_last_value?: unknown
  live_timestamp?: string
}

export interface OperationType {
  type_id: string
  type_label: string
  description?: string
  available_modules: string[]
  config_schema: Record<string, unknown>
  metric_options: string[]
  output_formats: string[]
}

export interface OperationCreate {
  module_id: string
  type_id: string
  name: string
  config: Record<string, unknown>
}

export interface OperationUpdate {
  name: string
  config: Record<string, unknown>
}

export interface OperationStatusEvent {
  operation_id: number
  status: OperationStatus
  last_value?: unknown
  timestamp: string
}

export interface OperationReloadedEvent {
  operation_id: number
  version: number
}

export interface RoiPoint {
  x: number  // normalized [0, 1]
  y: number  // normalized [0, 1]
}

export type MetricOption =
  | 'state'
  | 'coordinates'
  | 'both'
  | 'time_seconds'
  | 'coverage_percent'
  | 'entry_exit_count'
  | 'iou_percent'
  | 'min_distance'
  | 'overlap_time_seconds'
  | 'count'
  | 'boolean_above'
  | 'boolean_below'

export type OutputFormat = 'physical' | 'conditional' | 'both'
