/** EPI Monitor V2 — Shared TypeScript types. */

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
  status: 'uploaded' | 'extracting' | 'extracted' | 'error'
  frame_count: number
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

export interface TrainingJob {
  id: string
  preset: string
  model_size: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  progress: number
  current_epoch: number
  total_epochs: number
  metrics: Record<string, number>
  error_message?: string
  started_at?: string
  completed_at?: string
  created_at: string
}

export interface TrainedModel {
  id: string
  name: string
  model_path: string
  map50?: number
  precision?: number
  recall?: number
  is_active: boolean
  created_at: string
}

export interface Camera {
  id: string
  name: string
  location?: string
  manufacturer: string
  host: string
  port: number
  channel: number
  is_active: boolean
  stream_status?: string
  last_seen?: string
  created_at: string
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
