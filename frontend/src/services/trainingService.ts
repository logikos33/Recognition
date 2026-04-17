/**
 * trainingService.ts — HTTP calls for training pipeline.
 *
 * All endpoints proxied via api.ts (auto-injects Auth header).
 */
import { api } from './api'

export interface TrainingJobCreate {
  dataset_version_id: string
  module: string
  model_size?: 'yolo26n' | 'yolo26s' | 'yolo26m'
  epochs?: number
  imgsz?: number
  batch?: number
}

export interface TrainingJobProgress {
  job_id: string
  stage: 'pending' | 'extracting' | 'uploading' | 'training' | 'completed' | 'failed'
  progress: number
  epoch?: number
  total_epochs?: number
  metrics?: {
    mAP50?: number
    precision?: number
    recall?: number
    loss?: number
  }
  error?: string
}

export const trainingService = {
  listJobs: () =>
    api.get<{ status: string; data: { jobs: unknown[] } }>('/training/jobs'),

  createJob: (data: TrainingJobCreate) =>
    api.post<{ status: string; data: { job: unknown } }>('/training/jobs', data),

  getJobStatus: (jobId: string) =>
    api.get<{ status: string; data: { job: unknown } }>(`/training/jobs/${jobId}/status`),

  /** Reads live progress from Redis (no DB query). */
  getJobProgress: (jobId: string) =>
    api.get<{ status: string; data: TrainingJobProgress }>(`/training/jobs/${jobId}/progress`),

  listModels: () =>
    api.get<{ status: string; data: { models: unknown[] } }>('/training/models'),

  activateModel: (modelId: string) =>
    api.post<{ status: string; data: unknown }>(`/training/models/${modelId}/activate`, {}),

  listVideos: () =>
    api.get<{ status: string; data: { videos: unknown[] } }>('/training/videos'),

  uploadVideo: async (formData: FormData): Promise<{ status: string; data: unknown }> => {
    const { getToken } = await import('./api')
    const token = getToken()
    const apiBase = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL || ''
    const res = await fetch(`${apiBase}/api/training/videos`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    })
    return res.json()
  },
}
