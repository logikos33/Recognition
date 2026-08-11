/**
 * propagationService — propagação semeada (RunPod): preflight (custo ANTES
 * de criar o job), criação/consulta/listagem de `propagation_jobs`.
 *
 * Envelope REAL da API: `{success: boolean, message: string, data}`
 * (services/api/app/core/responses.py) — mesmo aviso de eventsService.ts,
 * NÃO `{status, data}`.
 *
 * Rotas montadas SEM prefixo de blueprint — o path completo já está no
 * decorator (services/api/app/api/v1/training/routes.py):
 * `/api/v1/training/propagation/...`. `api.ts` já prefixa `/api`, então os
 * paths aqui começam em `/v1/...`.
 */
import { api } from './api'

export type PropagationJobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'stopped'

export interface PropagationGpuCost {
  provider?: string
  gpu_type?: string
  price_usd_h?: number | null
  estimated_usd?: number | null
  actual_usd?: number | null
}

/** `job.metrics` — merge raso gravado pelo dispatch (tasks/propagation.py)
 * e pelo executor remoto (training/propagate_seeded.py). Índice extra:
 * o executor pode adicionar campos não listados aqui sem quebrar o tipo. */
export interface PropagationJobMetrics {
  stage?: string
  frames_processed?: number
  frames_total?: number
  proposals_so_far?: number
  seed_count?: number
  failure_kind?: 'cost_cap' | 'timeout' | 'pod_died' | 'stopped' | 'executor_error' | string
  gpu_cost?: PropagationGpuCost
  [key: string]: unknown
}

export interface PropagationJob {
  id: string
  tenant_id?: string
  status: PropagationJobStatus
  pool_criteria?: Record<string, unknown>
  pool_frame_ids?: string[]
  pool_hash?: string | null
  seed_frame_ids?: string[]
  seed_count?: number
  proposals_count: number
  gpu_instance_ref?: string | null
  metrics: PropagationJobMetrics
  error_reason?: string | null
  created_by?: string | null
  created_at: string
  started_at?: string | null
  finished_at?: string | null
}

/** `active_job` do preflight — SELECT explícito de só 3 colunas no backend
 * (PropagationRepository.get_active_for_tenant), nunca o job inteiro. */
export interface PropagationActiveJob {
  id: string
  status: PropagationJobStatus
  created_at: string
}

export interface PropagationGpuEstimate {
  gpu_type: string
  price_usd_h: number | null
  estimated_cost_usd: number | null
  max_usd: number
  timeout_seconds: number
  price_error: boolean
}

export interface PropagationPreflight {
  pool_total: number
  pool_effective: number
  validation_only: boolean
  seed_frame_count: number
  seed_box_count: number
  active_job: PropagationActiveJob | null
  third_party_cloud_enabled: boolean
  runpod_configured: boolean
  gpu: PropagationGpuEstimate
}

export interface PreflightParams {
  camera_id: string
  date_from: string
  date_to: string
  validation_only?: boolean
}

export interface CreatePropagationJobBody {
  camera_ids: string[]
  date_from: string
  date_to: string
  validation_only?: boolean
  max_results?: number
  threshold?: number
  seed_frame_ids?: string[]
}

interface Envelope<T> {
  success: boolean
  message?: string
  data?: T
}

function buildPreflightQuery(params: PreflightParams): string {
  const qs = new URLSearchParams()
  qs.set('camera_id', params.camera_id)
  qs.set('date_from', params.date_from)
  qs.set('date_to', params.date_to)
  if (params.validation_only != null) qs.set('validation_only', String(params.validation_only))
  return qs.toString()
}

export const propagationService = {
  async getPreflight(params: PreflightParams): Promise<PropagationPreflight> {
    const res = await api.get<Envelope<PropagationPreflight>>(
      `/v1/training/propagation/preflight?${buildPreflightQuery(params)}`,
    )
    if (!res.data) throw new Error('Resposta vazia do preflight de propagação')
    return res.data
  },

  async createJob(body: CreatePropagationJobBody): Promise<PropagationJob> {
    const res = await api.post<Envelope<PropagationJob>>('/v1/training/propagation/jobs', body)
    if (!res.data) throw new Error('Resposta vazia ao criar job de propagação')
    return res.data
  },

  async getJob(id: string): Promise<PropagationJob> {
    const res = await api.get<Envelope<PropagationJob>>(`/v1/training/propagation/jobs/${id}`)
    if (!res.data) throw new Error('Resposta vazia ao consultar job de propagação')
    return res.data
  },

  async listJobs(): Promise<PropagationJob[]> {
    const res = await api.get<Envelope<PropagationJob[]>>('/v1/training/propagation/jobs')
    return res.data ?? []
  },
}
