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
  for (const id of params.cameraIds ?? []) qs.append('camera_id[]', id)
  for (const cls of params.classNames ?? []) qs.append('class_name[]', cls)
  return qs.toString()
}

export const eventsService = {
  async getTimeline(params: TimelineParams): Promise<TimelineData> {
    const res = await api.get<Envelope<TimelineData>>(
      `/v1/events/timeline?${buildQuery(params, params.bucket)}`
    )
    return res.data ?? { timeline: [], bucket: params.bucket ?? 'hour' }
  },

  async getSummary(params: EventsRangeParams): Promise<SummaryData> {
    const res = await api.get<Envelope<SummaryData>>(
      `/v1/events/summary?${buildQuery(params)}`
    )
    return res.data ?? { total: 0, by_class: [], by_camera: [] }
  },
}
