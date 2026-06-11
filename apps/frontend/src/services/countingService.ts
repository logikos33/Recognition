/**
 * countingService.ts — HTTP calls do módulo de Contagem / Carga & Descarga.
 *
 * Endpoints via api.ts (auto-injeta Auth header; envelope {status, data}).
 */
import { api } from './api'
import type {
  CameraModelAssignment,
  CountingSession,
  CountingSessionUpdate,
  ValidationReport,
} from '../types/counting'

interface Envelope<T> {
  status: string
  data: T
}

export interface ValidationReportParams {
  /** Data inicial YYYY-MM-DD (default backend: 7 dias atrás). */
  start?: string
  /** Data final YYYY-MM-DD, inclusiva (default backend: hoje). */
  end?: string
  /** UUID da baia (opcional). */
  bay_id?: string
  /** % de erro máximo aceito (default backend: 5). */
  threshold?: number
}

export const countingService = {
  /** PATCH parcial da sessão (placa, manual_count, aceite, direção...). */
  updateSession: (sessionId: string, fields: CountingSessionUpdate) =>
    api.patch<Envelope<{ session: CountingSession }>>(
      `/counting/sessions/${sessionId}`,
      fields,
    ),

  /** Relatório de validação/aceite CD-07 (system vs manual). */
  getValidationReport: (params: ValidationReportParams = {}) => {
    const qs = new URLSearchParams()
    if (params.start) qs.set('start', params.start)
    if (params.end) qs.set('end', params.end)
    if (params.bay_id) qs.set('bay_id', params.bay_id)
    if (params.threshold !== undefined) qs.set('threshold', String(params.threshold))
    const query = qs.toString()
    return api.get<Envelope<ValidationReport>>(
      `/counting/sessions/validation-report${query ? `?${query}` : ''}`,
    )
  },

  /** Atribuição de modelo por módulo da câmera (Task 045). */
  getCameraModels: (cameraId: string) =>
    api.get<Envelope<{ camera_id: string; models: CameraModelAssignment }>>(
      `/cameras/${cameraId}/models`,
    ),

  /** Define (ou remove com model_id=null) o modelo de um módulo da câmera. */
  setCameraModel: (cameraId: string, module: 'epi' | 'quality' | 'counting', modelId: string | null) =>
    api.put<Envelope<{ camera_id: string; models: CameraModelAssignment }>>(
      `/cameras/${cameraId}/models`,
      { module, model_id: modelId },
    ),
}
