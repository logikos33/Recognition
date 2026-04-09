/**
 * cameraService — camada de acesso à API de câmeras.
 *
 * Mantém um único ponto de chamada HTTP para todas as operações de câmeras.
 * Mapeamento form → API: 'ip' → 'host', 'path' → 'rtsp_url_override'.
 */
import { api } from './api'
import type { Camera } from '../types'

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

type ApiListResponse = { cameras: Camera[]; gateway_status?: unknown; inference_status?: unknown }

export const cameraService = {
  async list(): Promise<Camera[]> {
    const res = await api.get<{ success: boolean; data: ApiListResponse }>('/cameras')
    const data = (res as unknown as { data: ApiListResponse }).data
    if (data?.cameras) return data.cameras
    // fallback para resposta direta
    const direct = res as unknown as { cameras?: Camera[] }
    return direct.cameras || (Array.isArray(res) ? (res as unknown as Camera[]) : [])
  },

  async get(id: string): Promise<Camera> {
    const res = await api.get<{ success: boolean; data: Camera }>(`/cameras/${id}`)
    return (res as unknown as { data: Camera }).data
  },

  async create(data: CameraFormData): Promise<Camera> {
    const res = await api.post<{ success: boolean; data: Camera }>('/cameras', formToApiPayload(data))
    return (res as unknown as { data: Camera }).data
  },

  async update(id: string, data: Partial<CameraFormData>): Promise<Camera> {
    const res = await api.put<{ success: boolean; data: Camera }>(`/cameras/${id}`, formToApiPayload(data))
    return (res as unknown as { data: Camera }).data
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/cameras/${id}`)
  },

  async test(id: string): Promise<TestResult> {
    const res = await api.post<{ success: boolean; data: TestResult }>(`/cameras/${id}/test`)
    return (res as unknown as { data: TestResult }).data
  },

  async start(id: string): Promise<void> {
    await api.post(`/cameras/${id}/stream/start`)
  },

  async stop(id: string): Promise<void> {
    await api.post(`/cameras/${id}/stream/stop`)
  },
}

export default cameraService
