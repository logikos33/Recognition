/**
 * Módulo de Qualidade — Serviço de API.
 * Usa a instância centralizada `api` de services/api.ts (fetch + JWT automático).
 */
import { api } from '../../../services/api'
import type {
  ApiResponse,
  QualityClass,
  DefectCategory,
  QualityCamera,
  QualityInspection,
  InspectionSummary,
  AnnotationFrame,
  AnnotationProgress,
  BoundingBox,
  QualityTrainingJob,
  CepBaseline,
  AndonData,
  ShiftReport,
} from '../types/quality'

const BASE = '/v1/quality'

// ── Classes e categorias ──────────────────────────────────────────────────────

export const qualityService = {
  getClasses: () =>
    api.get<ApiResponse<{ classes: QualityClass[] }>>(`${BASE}/classes`),

  getDefectCategories: () =>
    api.get<ApiResponse<{ categories: DefectCategory[] }>>(`${BASE}/defect-categories`),

  // ── Câmeras ─────────────────────────────────────────────────────────────────

  getCameras: () =>
    api.get<ApiResponse<{ cameras: QualityCamera[] }>>(`${BASE}/cameras`),

  getAvailableCameras: () =>
    api.get<ApiResponse<{ cameras: QualityCamera[] }>>(`${BASE}/cameras/available`),

  assignCamera: (cameraId: string) =>
    api.post<ApiResponse<{ camera: QualityCamera }>>(`${BASE}/cameras/${cameraId}/assign`),

  unassignCamera: (cameraId: string) =>
    api.delete<ApiResponse<null>>(`${BASE}/cameras/${cameraId}/unassign`),

  updateCameraConfig: (
    cameraId: string,
    config: { production_order?: string; product_type?: string; model_quality_id?: string }
  ) =>
    api.patch<ApiResponse<{ camera: QualityCamera }>>(`${BASE}/cameras/${cameraId}/config`, config),

  toggleSetupMode: (cameraId: string) =>
    api.post<ApiResponse<{ is_setup_mode: boolean }>>(`${BASE}/cameras/${cameraId}/toggle-setup-mode`),

  // ── Inspeções ────────────────────────────────────────────────────────────────

  getInspections: (params?: {
    camera_id?: string
    result?: string
    defect_category?: string
    feedback_status?: string
    shift?: string
    from?: string
    to?: string
    production_order?: string
    page?: number
    per_page?: number
  }) => {
    const qs = params
      ? '?' + new URLSearchParams(
          Object.fromEntries(
            Object.entries(params)
              .filter(([, v]) => v !== undefined && v !== '')
              .map(([k, v]) => [k, String(v)])
          )
        ).toString()
      : ''
    return api.get<ApiResponse<{ inspections: QualityInspection[]; total: number; page: number; per_page: number }>>(
      `${BASE}/inspections${qs}`
    )
  },

  getInspection: (id: string) =>
    api.get<ApiResponse<{ inspection: QualityInspection }>>(`${BASE}/inspections/${id}`),

  getClipUrl: (id: string) =>
    api.get<ApiResponse<{ url: string; expires_in: number }>>(`${BASE}/inspections/${id}/clip-url`),

  getEvidenceUrl: (id: string) =>
    api.get<ApiResponse<{ url: string; expires_in: number }>>(`${BASE}/inspections/${id}/evidence-url`),

  submitFeedback: (id: string, payload: { status: 'confirmed' | 'rejected'; notes?: string }) =>
    api.patch<ApiResponse<{ inspection: QualityInspection }>>(`${BASE}/inspections/${id}/feedback`, payload),

  getSummary: (params?: { shift?: string; camera_id?: string; date?: string }) => {
    const qs = params
      ? '?' + new URLSearchParams(
          Object.fromEntries(
            Object.entries(params)
              .filter(([, v]) => v !== undefined)
              .map(([k, v]) => [k, String(v)])
          )
        ).toString()
      : ''
    return api.get<ApiResponse<InspectionSummary>>(`${BASE}/inspections/summary${qs}`)
  },

  // ── Anotação ─────────────────────────────────────────────────────────────────

  prepareAnnotation: (inspectionId: string) =>
    api.post<ApiResponse<{ job_queued: boolean }>>(`${BASE}/inspections/${inspectionId}/prepare-annotation`),

  getAnnotationFrames: (inspectionId: string) =>
    api.get<ApiResponse<{ frames: AnnotationFrame[] }>>(`${BASE}/inspections/${inspectionId}/annotation-frames`),

  getFrameUrl: (frameId: string) =>
    api.get<ApiResponse<{ url: string; expires_in: number }>>(`${BASE}/annotation-frames/${frameId}/url`),

  saveAnnotations: (frameId: string, annotations: BoundingBox[]) =>
    api.put<ApiResponse<{ frame: AnnotationFrame }>>(`${BASE}/annotation-frames/${frameId}/annotations`, {
      annotations,
    }),

  getAnnotationProgress: (inspectionId: string) =>
    api.get<ApiResponse<AnnotationProgress>>(`${BASE}/inspections/${inspectionId}/annotation-progress`),

  // ── Treinamento ───────────────────────────────────────────────────────────────

  createTrainingJob: () =>
    api.post<ApiResponse<{ job: QualityTrainingJob }>>(`${BASE}/training/jobs`),

  getTrainingJobs: () =>
    api.get<ApiResponse<{ jobs: QualityTrainingJob[] }>>(`${BASE}/training/jobs`),

  getTrainingJob: (jobId: string) =>
    api.get<ApiResponse<{ job: QualityTrainingJob }>>(`${BASE}/training/jobs/${jobId}`),

  activateModel: (modelId: string, cameraId: string) =>
    api.post<ApiResponse<null>>(`${BASE}/training/models/${modelId}/activate`, { camera_id: cameraId }),

  getReferenceSnapshots: (cameraId: string) =>
    api.get<ApiResponse<{ snapshots: Array<{ id: string; r2_key: string; production_order: string; created_at: string }> }>>(
      `${BASE}/reference-snapshots/${cameraId}`
    ),

  // ── CEP ───────────────────────────────────────────────────────────────────────

  getCepData: (cameraId: string) =>
    api.get<ApiResponse<{ baseline: CepBaseline | null }>>(`${BASE}/cep/${cameraId}`),

  // ── Andon ─────────────────────────────────────────────────────────────────────

  getAndon: (cameraId: string) =>
    api.get<ApiResponse<AndonData>>(`${BASE}/andon/${cameraId}`),

  // ── Relatórios ────────────────────────────────────────────────────────────────

  getShiftReport: (params?: { shift?: string; date?: string; camera_id?: string }) => {
    const qs = params
      ? '?' + new URLSearchParams(
          Object.fromEntries(
            Object.entries(params)
              .filter(([, v]) => v !== undefined)
              .map(([k, v]) => [k, String(v)])
          )
        ).toString()
      : ''
    return api.get<ApiResponse<ShiftReport>>(`${BASE}/reports/shift${qs}`)
  },

  getShiftReportPdfUrl: (params?: { shift?: string; date?: string }) => {
    const qs = params
      ? '?' + new URLSearchParams(
          Object.fromEntries(
            Object.entries(params)
              .filter(([, v]) => v !== undefined)
              .map(([k, v]) => [k, String(v)])
          )
        ).toString()
      : ''
    // Retorna a URL completa para download direto (não usa api.get para evitar JSON parse)
    const apiBase = import.meta.env.VITE_API_URL
      ? `${import.meta.env.VITE_API_URL}/api`
      : '/api'
    return `${apiBase}${BASE}/reports/shift/pdf${qs}`
  },
}
