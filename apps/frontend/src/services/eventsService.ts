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
  /**
   * Somar `public.demo_events` (evento SEMEADO) ao evento real. Default
   * `false` — ver `buildQuery`. Só passe `true` numa tela que DIGA, na
   * legenda, que está mostrando demonstração.
   */
  includeDemo?: boolean
  /**
   * Eixo de tempo: 'captured' (DEFAULT aqui, quando o frame foi capturado) ou
   * 'created' (quando a linha entrou no banco). Só o primeiro responde "em que
   * horário a fábrica gera violação" — numa carga em lote o segundo responde
   * "a que horas o servidor gravou". Vale para timeline E resumo: os dois
   * alimentam painéis da MESMA tela, e painel da mesma tela não pode contar em
   * eixos diferentes. Ver `buildQuery`.
   */
  timeField?: 'created' | 'captured'
}

export interface TimelineParams extends EventsRangeParams {
  bucket?: 'hour' | 'day' | 'week'
}

/**
 * ⚠️ `include_demo` é emitido SEMPRE, e o default é `false` — invertido em
 * relação à rota (issue #677).
 *
 * `GET /v1/events/timeline` e `/search` fazem
 * `include_demo = request.args.get("include_demo","true") != "false"`: quem
 * NÃO manda o parâmetro recebe `public.demo_events` unido por `UNION ALL` ao
 * evento real. O funil PADRÃO do usuário mostra só origem real — o semeado
 * aparece por filtro DECLARADO na tela. Como a rota tem outros consumidores,
 * o default se inverte AQUI, no cliente, e não lá.
 *
 * Hoje `SELECT count(*) FROM public.demo_events` = 0 no DEV: o defeito é
 * inerte e passa a mentir no minuto em que alguém semear a primeira demo.
 */
function buildQuery(params: EventsRangeParams, bucket?: string): string {
  const qs = new URLSearchParams()
  qs.set('from', params.from)
  qs.set('to', params.to)
  qs.set('include_demo', params.includeDemo === true ? 'true' : 'false')
  // EIXO DO TEMPO — mesmo motivo do `include_demo` acima: default invertido
  // AQUI, no cliente, e não na rota (que tem outros consumidores). A rota
  // trata ausência como 'created' (GRAVAÇÃO); esta tela conta CAPTURA em todo
  // painel, e `GET /api/alerts` — o destino de todo deep-link do Dashboard —
  // recorta por captura desde a issue #676. Resumo em `created_at` com lista
  // em `timestamp` é o cartão dizendo um número e a lista mostrando outro.
  qs.set('time_field', params.timeField === 'created' ? 'created' : 'captured')
  if (bucket) qs.set('bucket', bucket)
  if (params.moduleCode) qs.set('module_code', params.moduleCode)
  for (const id of params.cameraIds ?? []) qs.append('camera_id[]', id)
  for (const cls of params.classNames ?? []) qs.append('class_name[]', cls)
  return qs.toString()
}

export const eventsService = {
  async getTimeline(params: TimelineParams): Promise<TimelineData> {
    const qs = buildQuery(params, params.bucket)
    const res = await api.get<Envelope<TimelineData>>(`/v1/events/timeline?${qs}`)
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
