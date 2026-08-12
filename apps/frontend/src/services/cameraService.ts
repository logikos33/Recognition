/**
 * cameraService — camada de acesso à API de câmeras.
 *
 * Mantém um único ponto de chamada HTTP para todas as operações de câmeras.
 * Mapeamento form → API: 'ip' → 'host', 'path' → 'rtsp_url_override'.
 */
import { api } from './api'
import type { Camera } from '../types'
import type { CameraHealthContext } from '../types/edge'

export interface CameraFormData {
  name: string
  ip: string
  port: number
  username: string
  password: string
  path: string
  manufacturer: string
  location?: string
}

export interface StreamStartResult {
  camera_id: string
  /** URL HLS autorizada pelo backend — tokenizada quando o enforcement está
   * ligado. Nunca montar esta URL no frontend. */
  hls_url: string
  status: string
  dispatch_mode?: string
  rtsp_url_validated?: boolean
}

export interface TestCheck {
  status: 'ok' | 'error' | 'warning' | 'pending'
  message: string
}

export interface TestResult {
  camera_id: string
  success: boolean
  error: string | null
  suggestion: string | null
  checks: {
    url_format: TestCheck
    host_reachable: TestCheck
    port_open: TestCheck
    rtsp_response: TestCheck
    stream_available: TestCheck
  }
}

function formToApiPayload(data: Partial<CameraFormData>): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  if (data.name !== undefined) payload.name = data.name
  if (data.ip !== undefined) payload.host = data.ip
  if (data.port !== undefined) payload.port = data.port
  if (data.username !== undefined) payload.username = data.username
  if (data.password !== undefined) payload.password = data.password
  if (data.path !== undefined) payload.rtsp_url_override = data.path || null
  if (data.manufacturer !== undefined) payload.manufacturer = data.manufacturer
  if (data.location !== undefined) payload.location = data.location
  return payload
}

/**
 * Constrói preview da URL RTSP para exibir ao usuário (sem fazer requisição).
 * Senha sempre mascarada com ****.
 */
export function buildRtspPreview(data: Partial<CameraFormData>): string {
  if (data.path) return data.path

  const ip = data.ip || '...'
  const port = data.port || 554
  const user = data.username || ''
  const path = getDefaultPath(data.manufacturer || '')

  if (user) {
    return `rtsp://${user}:****@${ip}:${port}${path}`
  }
  return `rtsp://${ip}:${port}${path}`
}

export function getDefaultPath(manufacturer: string): string {
  const paths: Record<string, string> = {
    hikvision: '/Streaming/Channels/101',
    dahua: '/cam/realmonitor?channel=1&subtype=0',
    intelbras: '/cam/realmonitor?channel=1&subtype=1',
    axis: '/axis-media/media.amp',
    samsung: '/profile1/media.smp',
    generic: '/stream',
  }
  return paths[manufacturer?.toLowerCase()] || '/stream'
}

/** Envelope padrão do backend: { status: "success"|"error", data: T } */
type ApiEnvelope<T> = { status: string; data: T }

/** PATCH parcial de config — pelo menos um campo (validado no backend). */
export interface CameraConfigPatch {
  fps_target?: number
  quality_preset?: string
  /** Eixo COLETA (frame de treino, migration 114): 0=principal, 1=substream.
   * Independente de fps_target/quality_preset (eixo OPERAÇÃO). */
  collection_subtype?: number
}

/** Resultado da propagação cloud→edge enfileirada no PATCH /config (aditivo). */
export interface CameraPropagation {
  queued: boolean
  reason: 'no_site' | 'error' | null
}

export type CameraWithPropagation = Camera & { propagation?: CameraPropagation }
type ApiListData = { cameras: Camera[]; gateway_status?: unknown; inference_status?: unknown }

export interface ProbeInput {
  manufacturer: string
  ip_or_host: string
  port?: number
  username?: string
  password?: string
  channel?: number
  is_behind_nat?: boolean
}

export interface ProbeResult {
  ok: boolean | null
  method?: string
  codec?: string | null
  resolution?: string | null
  fps?: number | null
  substream_url_sugerida?: string | null
  gateway_available?: boolean
  warning?: string | null
  error?: string | null
  message?: string
}

export const cameraService = {
  async list(): Promise<Camera[]> {
    const res = await api.get<ApiEnvelope<ApiListData>>('/cameras')
    return res.data?.cameras ?? []
  },

  async get(id: string): Promise<Camera> {
    const res = await api.get<ApiEnvelope<Camera>>(`/cameras/${id}`)
    return res.data
  },

  async create(data: CameraFormData): Promise<Camera> {
    const res = await api.post<ApiEnvelope<Camera>>('/cameras', formToApiPayload(data))
    return res.data
  },

  async update(id: string, data: Partial<CameraFormData>): Promise<Camera> {
    const res = await api.put<ApiEnvelope<Camera>>(`/cameras/${id}`, formToApiPayload(data))
    return res.data
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/cameras/${id}`)
  },

  async test(id: string): Promise<TestResult> {
    const res = await api.post<ApiEnvelope<TestResult>>(`/cameras/${id}/test`)
    return res.data
  },

  /** Inicia o stream e devolve a URL HLS que o backend autorizou.
   *
   * A URL TEM que vir do backend: com HLS_REQUIRE_PLAYBACK_TOKEN ligado ela
   * carrega um token de playback no path, e a URL legada (montada no front)
   * recebe 404. O token é o portão de tenant do serve_hls, que é público por
   * design — hls.js não envia header de auth.
   */
  async start(id: string): Promise<StreamStartResult> {
    const res = await api.post<ApiEnvelope<StreamStartResult>>(`/cameras/${id}/stream/start`)
    return res.data
  },

  async stop(id: string): Promise<void> {
    await api.post(`/cameras/${id}/stream/stop`)
  },

  async patchConfig(
    id: string,
    patch: CameraConfigPatch,
  ): Promise<CameraWithPropagation> {
    const res = await api.patch<ApiEnvelope<CameraWithPropagation>>(
      `/cameras/${id}/config`,
      patch,
    )
    return res.data
  },

  /** Telemetria real do site da câmera para o aviso health-aware (WS10). */
  async getHealthContext(id: string): Promise<CameraHealthContext> {
    const res = await api.get<ApiEnvelope<CameraHealthContext>>(
      `/cameras/${id}/health-context`,
    )
    return res.data
  },

  async probe(data: ProbeInput): Promise<ProbeResult> {
    const res = await api.post<ApiEnvelope<ProbeResult>>('/cameras/probe', data)
    return res.data
  },
}

export default cameraService
