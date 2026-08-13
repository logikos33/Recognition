/**
 * proposalService — grade de triagem de propostas de propagação/pré-anotação
 * (migration 118, tabela `public.propagation_proposals`).
 *
 * Envelope REAL da API: `{success: boolean, message: string, data}`
 * (services/api/app/core/responses.py) — mesmo aviso de propagationService.ts,
 * NÃO `{status, data}`.
 *
 * Rotas montadas SEM prefixo de blueprint — o path completo já está no
 * decorator (services/api/app/api/v1/training/routes.py):
 * `/api/v1/training/proposals...` e `/api/v1/training/propagation/jobs/<id>/reject-proposals`.
 * `api.ts` já prefixa `/api`, então os paths aqui começam em `/v1/...`.
 *
 * Ver contrato completo: PROPOSALS_CONTRACT.md (worktree wt-rejeicao-propostas).
 */
import { api } from './api'

export type ProposalStatus = 'pending' | 'accepted' | 'rejected' | 'corrected'
export type ProposalSource = 'propagation' | 'search' | 'pre_annotation' | 'backfill'
export type ProposalSortField = 'confidence' | 'class_name' | 'created_at'
export type ProposalSortOrder = 'asc' | 'desc'

/** bbox normalizado (0..1) na convenção YOLO: [xCenter, yCenter, width, height]. */
export type ProposalBbox = [number, number, number, number]

export interface ProposalFrameRef {
  r2_key: string
  width: number | null
  height: number | null
  camera_id: string | null
  /** Presigned R2 (best-effort) — `null` se a geração falhar. */
  url: string | null
}

export interface Proposal {
  id: string
  frame_id: string
  job_id: string | null
  class_name: string
  confidence: number | null
  bbox: ProposalBbox
  status: ProposalStatus
  source: ProposalSource | string
  frame: ProposalFrameRef
}

export interface ProposalClassFacet {
  class_name: string
  count: number
}

export interface ProposalFacets {
  by_class: ProposalClassFacet[]
}

export interface ProposalListResponse {
  proposals: Proposal[]
  total: number
  page: number
  page_size: number
  total_pages: number
  facets: ProposalFacets
}

export interface ListProposalsParams {
  status?: ProposalStatus
  job_id?: string
  /** Repetível/CSV no backend — aqui sempre um array (join feito no client). */
  class_name?: string[]
  confidence_min?: number
  confidence_max?: number
  camera_id?: string[]
  sort?: ProposalSortField
  order?: ProposalSortOrder
  page?: number
  page_size?: number
}

export interface RejectBatchBody {
  proposal_ids?: string[]
  frame_ids?: string[]
  job_id?: string
  class_names?: string[]
  confidence_lt?: number
  reason?: string
}

export interface RejectBatchResult {
  rejected_count: number
  affected_frame_count: number
  affected_frames: string[]
}

export interface RejectJobBody {
  class_names?: string[]
  confidence_lt?: number
}

export interface RejectProposalResult {
  id: string
  status: ProposalStatus
}

export interface AcceptProposalResult {
  id: string
  status: ProposalStatus
  frame_id: string
}

interface Envelope<T> {
  success: boolean
  message?: string
  data?: T
}

function buildListQuery(params: ListProposalsParams): string {
  const qs = new URLSearchParams()
  qs.set('status', params.status ?? 'pending')
  if (params.job_id) qs.set('job_id', params.job_id)
  if (params.class_name && params.class_name.length > 0) {
    qs.set('class_name', params.class_name.join(','))
  }
  if (params.confidence_min != null) qs.set('confidence_min', String(params.confidence_min))
  if (params.confidence_max != null) qs.set('confidence_max', String(params.confidence_max))
  if (params.camera_id && params.camera_id.length > 0) {
    qs.set('camera_id', params.camera_id.join(','))
  }
  qs.set('sort', params.sort ?? 'confidence')
  qs.set('order', params.order ?? 'asc')
  qs.set('page', String(params.page ?? 1))
  qs.set('page_size', String(params.page_size ?? 60))
  return qs.toString()
}

export const proposalService = {
  async listProposals(params: ListProposalsParams = {}): Promise<ProposalListResponse> {
    const res = await api.get<Envelope<ProposalListResponse>>(
      `/v1/training/proposals?${buildListQuery(params)}`,
    )
    if (!res.data) throw new Error('Resposta vazia ao listar propostas')
    return res.data
  },

  async rejectBatch(body: RejectBatchBody): Promise<RejectBatchResult> {
    const res = await api.post<Envelope<RejectBatchResult>>(
      '/v1/training/proposals/reject-batch',
      body,
    )
    if (!res.data) throw new Error('Resposta vazia ao rejeitar propostas em lote')
    return res.data
  },

  async rejectJob(jobId: string, body?: RejectJobBody): Promise<RejectBatchResult> {
    const res = await api.post<Envelope<RejectBatchResult>>(
      `/v1/training/propagation/jobs/${jobId}/reject-proposals`,
      body ?? {},
    )
    if (!res.data) throw new Error('Resposta vazia ao rejeitar job de propostas')
    return res.data
  },

  async rejectProposal(id: string): Promise<RejectProposalResult> {
    const res = await api.post<Envelope<RejectProposalResult>>(
      `/v1/training/proposals/${id}/reject`,
    )
    if (!res.data) throw new Error('Resposta vazia ao rejeitar proposta')
    return res.data
  },

  async acceptProposal(id: string, bbox?: ProposalBbox): Promise<AcceptProposalResult> {
    const res = await api.post<Envelope<AcceptProposalResult>>(
      `/v1/training/proposals/${id}/accept`,
      bbox ? { bbox } : undefined,
    )
    if (!res.data) throw new Error('Resposta vazia ao aprovar proposta')
    return res.data
  },
}
