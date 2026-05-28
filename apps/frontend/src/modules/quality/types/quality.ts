/**
 * Módulo de Qualidade Industrial — TypeScript types.
 * Espelha o schema do banco (quality_inspections, quality_camera_config, etc.)
 * e os payloads de API do blueprint /api/v1/quality/*.
 */

// ── Inspeção ──────────────────────────────────────────────────────────────────

export type InspectionResult = 'ok' | 'nok'
export type ClipStatus = 'pending' | 'available' | 'unavailable' | 'expired'
export type FeedbackStatus = 'pending' | 'confirmed' | 'rejected'
export type AnnotationStatus = 'pending' | 'ready' | 'in_progress' | 'completed'

export interface QualityInspection {
  id: string
  camera_id: string
  result: InspectionResult
  defect_class: number | null
  defect_category: string | null
  confidence: number
  evidence_r2_key: string | null
  production_order: string | null
  product_type: string | null
  shift: 'morning' | 'afternoon' | 'night'
  clip_status: ClipStatus
  clip_r2_key: string | null
  clip_start: string | null
  clip_end: string | null
  is_first_ok_of_order: boolean
  rolling_nok_rate_1h: number | null
  rolling_nok_rate_8h: number | null
  is_cep_alert: boolean
  feedback_status: FeedbackStatus
  feedback_by: string | null
  feedback_at: string | null
  feedback_notes: string | null
  annotation_status: AnnotationStatus | null
  created_at: string
  // campos enriquecidos pela API
  camera_name?: string
  defect_class_label?: string
}

export interface InspectionSummary {
  total: number
  ok: number
  nok: number
  nok_rate: number
  pending_feedback: number
  shift: string
}

// ── Câmera de qualidade ───────────────────────────────────────────────────────

export interface QualityCamera {
  id: string
  name: string
  rtsp_url: string
  active_module: string
  model_quality_id: string | null
  is_setup_mode: boolean
  production_order: string | null
  product_type: string | null
  reference_snapshot_r2_key: string | null
  created_at: string
}

// ── Classes e categorias ──────────────────────────────────────────────────────

export interface QualityClass {
  id: number
  name: string
  color: string
  label: string
  category: 'ok' | 'nok'
}

export interface DefectCategory {
  slug: string
  label: string
}

// ── Anotação ──────────────────────────────────────────────────────────────────

export interface BoundingBox {
  id: string           // uuid local para seleção
  class_id: number
  cx: number           // centro X normalizado [0, 1]
  cy: number           // centro Y normalizado [0, 1]
  w: number            // largura normalizada [0, 1]
  h: number            // altura normalizada [0, 1]
  label?: string
  color?: string
}

export type FrameStatus = 'pending' | 'annotated' | 'skipped'

export interface AnnotationFrame {
  id: string
  inspection_id: string
  frame_sequence: number
  r2_key: string
  status: FrameStatus
  annotations: BoundingBox[] | null
  url?: string         // presigned URL (preenchida pelo hook)
}

export interface AnnotationProgress {
  total: number
  annotated: number
  skipped: number
  pending: number
  can_create_job: boolean  // true se annotated >= 10
}

// ── Treinamento ───────────────────────────────────────────────────────────────

export type TrainingJobStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface QualityTrainingJob {
  id: string
  status: TrainingJobStatus
  frame_count: number
  model_id: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface TrainingProgress {
  job_id: string
  step: string
  progress: number   // 0-100
  message: string
  timestamp: string
}

// ── CEP ───────────────────────────────────────────────────────────────────────

export interface CepBaseline {
  camera_id: string
  mean_nok_rate: number
  sigma_nok_rate: number
  control_limit_upper: number
  control_limit_lower: number
  sample_size: number
  calculated_at: string
}

// ── Andon ─────────────────────────────────────────────────────────────────────

export interface AndonData {
  camera_id: string
  camera_name: string
  last_result: InspectionResult | null
  nok_rate_1h: number
  total_ok: number
  total_nok: number
  cep_status: 'in_control' | 'out_of_control' | 'unknown'
  recent_inspections: Array<{
    result: InspectionResult
    defect_class: number | null
    confidence: number
    timestamp: string
  }>
}

// ── Relatório de turno ────────────────────────────────────────────────────────

export interface ShiftReport {
  schema: string
  shift: 'morning' | 'afternoon' | 'night'
  date: string
  total_ok: number
  total_nok: number
  total: number
  nok_rate: number
  defect_pareto: Array<{
    defect_class: number
    count: number
    pct: number
    label?: string
  }>
  generated_at: string
}

// ── WebSocket events ──────────────────────────────────────────────────────────

export interface QualityInspectionEvent {
  inspection_id: string
  camera_id: string
  result: InspectionResult
  defect_class: number
  confidence: number
  nok_rate_1h: number
  timestamp: string
}

export interface QualityCepAlertEvent {
  camera_id: string
  nok_rate_1h: number
  limit: number
}

// ── Envelopes de resposta da API ──────────────────────────────────────────────

export interface ApiResponse<T> {
  status: 'success' | 'error'
  data: T
}
