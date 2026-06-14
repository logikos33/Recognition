/**
 * Tipos do Quality Gate RVB.
 * Espelham o schema de banco e os payloads WebSocket do quality gate.
 */

// Status possíveis de uma peça na state machine do gate
export type PieceStatus =
  | 'idle'
  | 'identified'
  | 'validating_v1'
  | 'rework_v1'
  | 'validating_v2'
  | 'rework_v2'
  | 'waiting_bench_b'
  | 'validating_v3'
  | 'rework_v3'
  | 'approved'
  | 'rejected'

// Tipo de validação: V1 (fio no anel), V2 (saída isolada), V3 (anel encapado)
export type ValidationType = 'v1' | 'v2' | 'v3'

// Código de bancada física
export type StationCode = 'bench_a' | 'bench_b'

// Peça em processo no quality gate
export interface QualityPiece {
  id: string
  piece_number: string
  work_order: string | null
  product_type: string | null
  status: PieceStatus
  current_station: StationCode | null
  operator_id: string | null
  started_at: string
  completed_at: string | null
  total_rework_count: number
  total_rework_time_seconds: number
  photo_quality_path: string | null
  photo_quality_r2_key: string | null
  wiser_exported: boolean
  wiser_exported_at: string | null
  created_at: string
  updated_at: string
}

// Registro de retrabalho vinculado a uma peça
export interface QualityRework {
  id: string
  piece_id: string
  inspection_id: string | null
  validation_type: ValidationType
  defect_type: string | null
  defect_description: string | null
  photo_before_path: string | null
  photo_after_path: string | null
  operator_id: string | null
  started_at: string
  completed_at: string | null
  duration_seconds: number | null
  attempt_number: number
  notes: string | null
  created_at: string
}

// Estação (bancada) física com câmeras associadas
export interface QualityStation {
  id: string
  station_code: StationCode
  name: string
  overview_camera_id: string | null
  closeup_camera_id: string | null
  tower_controller_type: string
  is_active: boolean
  current_piece?: QualityPiece | null
}

// Registro de exportação para sistema Wiser
export interface WiserExport {
  id: string
  piece_id: string
  export_method: string
  file_path: string | null
  exported_at: string
  success: boolean
  error_message: string | null
}

// ── Eventos WebSocket ─────────────────────────────────────────────────────────

// Resultado de inspeção emitido pelo worker após inferência YOLO
export interface InspectionResultEvent {
  piece_id: string
  validation_type: ValidationType
  camera_id: string
  result: 'ok' | 'nok'
  confidence: number
  ok_ratio: number
  detections: Detection[]
  photo_path: string | null
  photo_r2_key: string | null
  timestamp: string
}

// Bounding box de detecção individual
export interface Detection {
  class: string
  class_id: number
  confidence: number
  bbox: [number, number, number, number]
  is_defect: boolean
}

// Estado atual de uma bancada (emitido a cada mudança de peça ou status)
export interface StationStateEvent {
  station_code: StationCode
  current_piece: QualityPiece | null
  tower_state: 'green' | 'red' | 'idle'
  timestamp: string
}

// Peça identificada por OCR, barcode ou entrada manual
export interface PieceIdentifiedEvent {
  piece_id: string
  piece_number: string
  work_order: string | null
  method: 'ocr' | 'barcode' | 'manual'
  confidence: number
  station_code: StationCode
}
