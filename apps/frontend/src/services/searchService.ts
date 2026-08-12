/**
 * searchService — "busca por conteúdo" nas imagens de treino selecionadas
 * (job de GPU sob demanda, mesma família de infra da propagação semeada,
 * ver propagationService.ts): preflight com custo ANTES de criar o job,
 * criação/consulta/listagem de `search_jobs`, promoção de achados.
 *
 * Envelope REAL da API: `{success: boolean, message: string, data}`
 * (services/api/app/core/responses.py) — mesmo aviso de propagationService.ts,
 * NÃO `{status, data}`.
 *
 * Rotas (services/api/app/api/v1/training/routes.py, backend em construção em
 * paralelo — contrato tratado como fixo): `/api/v1/training/search/...`.
 * `api.ts` já prefixa `/api`, então os paths aqui começam em `/v1/...`.
 */
import { api } from './api'

export type SearchJobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'stopped'

/** `label` é o rótulo pt-BR mostrado ao usuário; `query` é o termo em inglês
 * que de fato vai pro modelo (o usuário não precisa saber que é inglês). */
export interface SearchTerm {
  label: string
  query: string
}

export interface SearchIneligibleFrame {
  frame_id: string
  reason: string
}

export interface SearchGpuEstimate {
  gpu_type: string
  price_usd_h: number | null
  estimated_cost_usd: number | null
  max_usd: number
  timeout_seconds: number
  price_error: boolean
}

export interface SearchPreflight {
  selected_count: number
  eligible_count: number
  ineligible: SearchIneligibleFrame[]
  terms_count: number
  /** Mesmo gate ADR-0047/0060 reusado do treino/propagação — CTA some se falso. */
  third_party_cloud_enabled: boolean
  runpod_configured: boolean
  gpu: SearchGpuEstimate
  allowed_dates: string[]
}

/** Um achado (results[i] do job) — ACHADO, não proposta; vira proposta só
 * depois de promovido (ver promoteFindings). `index` pro promote é a posição
 * deste item dentro de `SearchJob.results`. */
export interface SearchFinding {
  frame_id: string
  /** query em inglês (a mesma enviada no termo) — chave de agrupamento. */
  term: string
  /** rótulo pt-BR do termo. */
  label: string
  /** [x, y, w, h] normalizado 0–1 relativo ao frame inteiro. */
  bbox: [number, number, number, number]
  confidence: number
}

export interface SearchJobGpuCost {
  estimated_usd: number | null
  actual_usd?: number | null
}

/** `job.metrics` — vocabulário de `stage` não é fixo no contrato (executor
 * pode variar, mesma cautela de PropagationJobMetrics) — mapSearchJobToPhase
 * em searchContentUi.ts é tolerante a nomes desconhecidos, mesmo sabendo que
 * o executor real (training/search_content.py) hoje emite 'manifest' →
 * 'deps' → 'model' → 'searching' (com frames_processed/frames_total) →
 * 'done'; o dispatch (tasks/search.py) usa 'preparing'/'creating_pod'/
 * 'gpu_starting' antes disso. `failure_kind` é gravado por
 * `tasks/search.py::_record_failure_metrics` (mesmo mapeamento de
 * `tasks/propagation.py`). */
export interface SearchJobMetrics {
  stage?: string
  frames_processed?: number
  frames_total?: number
  failure_kind?: 'cost_cap' | 'timeout' | 'pod_died' | 'stopped' | 'executor_error' | string
  gpu_cost?: SearchJobGpuCost
  [key: string]: unknown
}

export interface SearchJob {
  id: string
  status: SearchJobStatus
  selected_frame_ids: string[]
  terms: SearchTerm[]
  results: SearchFinding[]
  findings_count: number
  metrics: SearchJobMetrics
  error_reason?: string | null
  created_at: string
  finished_at?: string | null
}

export interface PromoteItem {
  index: number
  class_name: string
}

interface Envelope<T> {
  success: boolean
  message?: string
  data?: T
}

export const searchService = {
  /** POST (não GET) — o corpo carrega frame_ids + terms, grande demais pra
   * querystring e o preflight precisa ser recalculado a cada mudança de termo. */
  async getPreflight(frameIds: string[], terms: SearchTerm[]): Promise<SearchPreflight> {
    const res = await api.post<Envelope<SearchPreflight>>('/v1/training/search/preflight', {
      frame_ids: frameIds,
      terms,
    })
    if (!res.data) throw new Error('Resposta vazia do preflight de busca')
    return res.data
  },

  async createJob(frameIds: string[], terms: SearchTerm[]): Promise<SearchJob> {
    const res = await api.post<Envelope<SearchJob>>('/v1/training/search/jobs', {
      frame_ids: frameIds,
      terms,
    })
    if (!res.data) throw new Error('Resposta vazia ao criar job de busca')
    return res.data
  },

  async getJob(id: string): Promise<SearchJob> {
    const res = await api.get<Envelope<SearchJob>>(`/v1/training/search/jobs/${id}`)
    if (!res.data) throw new Error('Resposta vazia ao consultar job de busca')
    return res.data
  },

  /** `data` é a lista de jobs direto — `list_search_jobs_handler` faz
   * `return success(jobs)`, NÃO `success({jobs})`. */
  async listJobs(): Promise<SearchJob[]> {
    const res = await api.get<Envelope<SearchJob[]>>('/v1/training/search/jobs')
    return res.data ?? []
  },

  /** `items[].index` = posição do achado em `SearchJob.results`. Retorna
   * quantos foram de fato promovidos (o caller marca os índices ENVIADOS
   * como promovidos no estado local — ver searchContentUi.ts). */
  async promoteFindings(jobId: string, items: PromoteItem[]): Promise<number> {
    const res = await api.post<Envelope<{ promoted: number }>>(
      `/v1/training/search/jobs/${jobId}/promote`,
      { items },
    )
    return res.data?.promoted ?? 0
  },
}
