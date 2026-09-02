/** Recognition — Shared TypeScript types. */

export * from './counting'

export interface User {
  id: string
  email: string
  name: string
  role: 'admin' | 'operator'
}

export interface Video {
  id: string
  user_id: string
  filename: string
  original_filename?: string
  file_size?: number
  duration_seconds?: number
  status: 'uploaded' | 'queued' | 'extracting' | 'extracted' | 'error'
  frame_count: number
  frames_expected?: number
  error_message?: string
  created_at: string
}

export interface Frame {
  id: string
  video_id: string
  frame_number: number
  filename: string
  timestamp_seconds?: number
  is_annotated: boolean
  created_at: string
}

export interface Annotation {
  id: string
  frame_id: string
  class_id: number
  class_name?: string
  class_color?: string
  x_center: number
  y_center: number
  width: number
  height: number
}

export interface YoloClass {
  id: number
  name: string
  color: string
}

/**
 * Métricas de treino (training_jobs.metrics / trained_models.metrics — JSONB).
 * `simulated`: marcador indelével (task "treino honesto", C2) — presente e
 * `true` quando o treino rodou em simulação (TRAINING_SIMULATION_ENABLED),
 * nunca em treino real. Nunca renderizar métricas sem checar esta flag.
 */
export type TrainingMetrics = Record<string, number> & { simulated?: boolean }

export interface TrainingJob {
  id: string
  preset: string
  model_size: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  progress: number
  current_epoch: number
  total_epochs: number
  metrics: TrainingMetrics
  error_message?: string
  started_at?: string
  completed_at?: string
  created_at: string
}

export interface TrainedModel {
  id: string
  job_id?: string
  name: string
  /** Nome voltado ao cliente (migration 129, rebranding F5-LEVE) — NULL até
   * alguém atribuir. Use `nomeParaCliente()` (services/modelDisplay.ts) para
   * exibir; nunca `name`/`framework` cru em superfície de tenant. */
  display_name?: string | null
  model_path: string
  map50?: number
  precision?: number
  recall?: number
  is_active: boolean
  created_at: string
  /** Proveniência do treino (migration 090): vast_ai | ultralytics_hub | colab | simulated | training_service | unknown */
  origin?: string
  /** Métricas por classe (migration 098) — inclui marcador `simulated` (task "treino honesto"). */
  metrics?: TrainingMetrics
  /** Dono do modelo (usuário que disparou o treino) */
  created_by?: string
  owner_name?: string
  owner_email?: string
  /** Classificação Funcional/Parcial/Não avaliado (gate de ativação —
   * services/api/app/domain/services/model_status.py), derivada da última
   * avaliação campeão×desafiante. Ausente só em dados antigos/mocks de
   * teste; GET /training/models sempre preenche pós-fix. */
  eval_status?: 'funcional' | 'parcial' | 'nao_avaliado'
  /** Por que não está Funcional (língua de gente) — null quando funcional. */
  eval_motivo?: string | null
  /** mAP@50/precisão/cobertura REAIS de model_evaluations — null quando o
   * status é 'nao_avaliado' (nunca 0 fingido; ver utils/labels.ts). */
  eval_map50?: number | null
  eval_precision?: number | null
  eval_recall?: number | null
  /** "n" — imagens avaliadas na última avaliação. */
  eval_images_evaluated?: number | null
}

export interface Camera {
  id: string
  user_id?: string
  name: string
  location?: string
  description?: string
  manufacturer: string
  host: string
  port: number
  username?: string
  channel: number
  subtype?: number
  rtsp_url_override?: string
  module_code?: string
  /** Módulo que o worker usa pra resolver modelo/deployment da câmera
   * (cameras.active_module; default 'epi'). */
  active_module?: string | null
  is_active: boolean
  stream_status?: string
  last_seen?: string
  last_error?: string
  last_tested_at?: string
  updated_at?: string
  created_at: string
  fps_target?: number
  quality_preset?: string
  /** Eixo OPERAÇÃO (live view): 0=stream principal, 1=substream. Independente
   * de collection_subtype (eixo COLETA, migration 114). */
  live_view_subtype?: number
  /** Eixo COLETA (frame de treino, migration 114): 0=principal (alta,
   * padrão), 1=substream. Independente de fps_target/quality_preset/
   * live_view_subtype (eixo OPERAÇÃO). */
  collection_subtype?: number
  site_id?: string | null
  /** Alguém conferiu presencialmente na fábrica que o canal mostra este lugar (D-85). Nasce false para todas — inclusive as originais. */
  position_confirmed?: boolean
  /** Codec detectado por probe (ex. H265/H264) — PR #353. */
  codec_detected?: string | null
}

export interface Alert {
  id: string
  camera_id: string
  timestamp: string
  violations: Array<{ class: string; confidence: number }>
  confidence: number
  evidence_key?: string
  acknowledged: boolean
}

export interface ApiResponse<T> {
  success: boolean
  message?: string
  data?: T
  error?: string
}
