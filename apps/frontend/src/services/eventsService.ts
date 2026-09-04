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

/** Os três baldes de polaridade do backend (ADR-0065 + contrato A1). */
export type EventKind = 'violacao' | 'conformidade' | 'indefinido'

export interface ProfileRow {
  /** Início do bucket de hora, em UTC — mesmo formato de `/events/timeline`. */
  bucket: string | null
  kind: EventKind
  count: number
}

/** Tratativa dos eventos capturados no período — outro eixo do mesmo conjunto. */
export interface ProfileSituacao {
  total: number
  nao_reconhecidos: number
  procedentes: number
  improcedentes: number
  cameras: number
  primeira_captura: string | null
  ultima_captura: string | null
  confianca_media: number | null
}

export interface ProfileData {
  rows: ProfileRow[]
  situacao: ProfileSituacao
}

export const SITUACAO_VAZIA: ProfileSituacao = {
  total: 0,
  nao_reconhecidos: 0,
  procedentes: 0,
  improcedentes: 0,
  cameras: 0,
  primeira_captura: null,
  ultima_captura: null,
  confianca_media: null,
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
  /**
   * Eixo de tempo: 'created' (default, quando a linha entrou no banco) ou
   * 'captured' (quando o frame foi capturado). Só o segundo responde "em que
   * horário a fábrica gera violação" — numa carga em lote o primeiro responde
   * "a que horas o servidor gravou".
   */
  timeField?: 'created' | 'captured'
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
    const qs = buildQuery(params, params.bucket)
    const eixo = params.timeField === 'captured' ? '&time_field=captured' : ''
    const res = await api.get<Envelope<TimelineData>>(`/v1/events/timeline?${qs}${eixo}`)
    return res.data ?? { timeline: [], bucket: params.bucket ?? 'hour' }
  },

  async getSummary(params: EventsRangeParams): Promise<SummaryData> {
    const res = await api.get<Envelope<SummaryData>>(
      `/v1/events/summary?${buildQuery(params)}`
    )
    return res.data ?? { total: 0, by_class: [], by_camera: [] }
  },

  /** Volume por hora de CAPTURA × polaridade + tratativa, num pedido só. */
  async getProfile(params: EventsRangeParams): Promise<ProfileData> {
    const res = await api.get<Envelope<ProfileData>>(
      `/v1/events/profile?${buildQuery(params)}`
    )
    return res.data ?? { rows: [], situacao: SITUACAO_VAZIA }
  },
}
