/**
 * Types do módulo de Contagem / Carga & Descarga (counting_sessions).
 *
 * Espelham o schema de public.counting_sessions (migrations 049 + 050) e o
 * relatório de validação/aceite CD-07 (GET /counting/sessions/validation-report).
 */

export type CountingDirection = 'load' | 'unload'
export type AcceptanceStatus = 'pending' | 'accepted' | 'rejected'

/** Sessão de contagem (DeepSORT) com campos de carga/descarga. */
export interface CountingSession {
  id: string
  tenant_id?: string
  camera_id: string
  camera_name?: string | null
  module_code?: string
  status: string
  total_counts?: Record<string, number>
  started_at?: string | null
  ended_at?: string | null
  // --- Carga & Descarga (migration 050) ---
  bay_id?: string | null
  truck_plate?: string | null
  direction?: CountingDirection | null
  expected_count?: number | null
  divergence?: number | null
  video_clip_url?: string | null
  manual_count?: number | null
  acceptance_status?: AcceptanceStatus | null
}

/** Campos aceitos pelo PATCH /counting/sessions/<id>. */
export interface CountingSessionUpdate {
  truck_plate?: string | null
  manual_count?: number
  acceptance_status?: AcceptanceStatus
  expected_count?: number
  direction?: CountingDirection
}

/** Linha de sessão do relatório de validação (CD-07). */
export interface ValidationSessionRow {
  id: string
  bay_id: string | null
  camera_id: string
  truck_plate: string | null
  direction: CountingDirection | null
  started_at: string | null
  ended_at: string | null
  acceptance_status: AcceptanceStatus | null
  video_clip_url: string | null
  manual_count: number
  system_count: number
  abs_error: number
  error_pct: number | null
  passed: boolean
}

/** Agregado diário do relatório de validação. */
export interface ValidationDailyRow {
  day: string
  sessions: number
  system_total: number
  manual_total: number
  abs_error: number
  error_pct: number | null
  passed: boolean
}

/** Resumo agregado do período. */
export interface ValidationSummary {
  sessions_validated: number
  system_count: number
  manual_count: number
  abs_error: number
  error_pct: number | null
  passed: boolean
}

/** Payload de GET /counting/sessions/validation-report. */
export interface ValidationReport {
  threshold_pct: number
  period: { start: string; end: string }
  bay_id: string | null
  sessions: ValidationSessionRow[]
  daily: ValidationDailyRow[]
  summary: ValidationSummary
}

/** Atribuição de modelo por módulo de uma câmera (Task 045). */
export interface CameraModelAssignment {
  epi: string | null
  quality: string | null
  counting: string | null
}
