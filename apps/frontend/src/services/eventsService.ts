/**
 * eventsService — timeline e resumo agregado de eventos (alertas).
 *
 * ATENÇÃO: API_BASE já termina em '/api' (services/api.ts) — os paths aqui
 * começam em '/v1/...' (nunca '/api/v1/...', que geraria /api/api/v1 → 404).
 *
 * Envelope REAL da API: {success: boolean, message: string, data: {...}}
 * (app/core/responses.py — o CLAUDE.md do repo está desatualizado).
 */
import { api } from './api'

export interface TimelinePoint {
  bucket: string | null
  count: number
}

export interface TimelineData {
  timeline: TimelinePoint[]
  bucket: string
}

export interface SummaryByClass {
  class: string
  count: number
}

export interface SummaryByCamera {
  camera_id: string | null
  camera_name: string | null
  count: number
}

export interface SummaryData {
  total: number
  by_class: SummaryByClass[]
  by_camera: SummaryByCamera[]
}

interface Envelope<T> {
  success: boolean
  message?: string
  data?: T
}

export interface EventsRangeParams {
  /** ISO datetime (inclusive) */
  from: string
  /** ISO datetime (exclusive) */
  to: string
  moduleCode?: string
  cameraIds?: string[]
  classNames?: string[]
  /** false exclui `demo_events` — o backend inclui por padrão (`include_demo`
   *  default true), mas `GET /alerts` (a lista real) NUNCA soma demo. Quem
   *  cruza este agregado com a lista (ex.: faixa clicável de Eventos.tsx)
   *  precisa disto: sem excluir, uma barra pode contar só evento demo e o
   *  clique cai numa lista vazia — beco sem saída. */
  includeDemo?: boolean
}

export interface TimelineParams extends EventsRangeParams {
  bucket?: 'hour' | 'day' | 'week'
}

function buildQuery(params: EventsRangeParams, bucket?: string): string {
  const qs = new URLSearchParams()
  qs.set('from', params.from)
  qs.set('to', params.to)
  if (bucket) qs.set('bucket', bucket)
  if (params.moduleCode) qs.set('module_code', params.moduleCode)
  if (params.includeDemo === false) qs.set('include_demo', 'false')
  for (const id of params.cameraIds ?? []) qs.append('camera_id[]', id)
  for (const cls of params.classNames ?? []) qs.append('class_name[]', cls)
  return qs.toString()
}

export const eventsService = {
  // `res.data ?? default` só protege contra `data` ausente — não contra um
  // `data` presente porém incompleto (`{}`, visto num mock de teste e
  // plausível num hiccup de rede/backend). `timeline` sempre-array é o
  // contrato que `fillBuckets` (utils/timeBuckets.ts) assume sem checar —
  // sem isto, `for (const row of rows)` explode em render (não em efeito) e
  // derruba a ÁRVORE INTEIRA de quem chama, lista de eventos incluída.
  async getTimeline(params: TimelineParams): Promise<TimelineData> {
    const res = await api.get<Envelope<TimelineData>>(
      `/v1/events/timeline?${buildQuery(params, params.bucket)}`
    )
    const timeline = res.data?.timeline
    return {
      timeline: Array.isArray(timeline) ? timeline : [],
      bucket: res.data?.bucket ?? params.bucket ?? 'hour',
    }
  },

  async getSummary(params: EventsRangeParams): Promise<SummaryData> {
    const res = await api.get<Envelope<SummaryData>>(
      `/v1/events/summary?${buildQuery(params)}`
    )
    const d = res.data
    return {
      total: d?.total ?? 0,
      by_class: Array.isArray(d?.by_class) ? d.by_class : [],
      by_camera: Array.isArray(d?.by_camera) ? d.by_camera : [],
    }
  },
}
