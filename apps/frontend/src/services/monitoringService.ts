/**
 * monitoringService — API da página oculta /monitoring (superadmin only).
 *
 * Backend responde com o envelope {"success": true, "message": ..., "data": ...}
 * (app/core/responses.py). Para não-superadmin TODAS as rotas devolvem 404
 * (C-01 — a rota se comporta como inexistente).
 *
 * query/snapshot/logtail são COMANDOS: podem voltar `state: 'pending'` quando
 * o box ainda não acordou (o agente faz poll de comandos a cada 60 s) — o
 * caller acompanha via getCommand(commandId) até done/failed.
 */
import { api } from './api'
import type {
  DetectionsHealth,
  LogtailCommandResponse,
  MonitoringCommandResponse,
  MonitoringEnvelope,
  MonitoringSite,
  MonitoringWindow,
  RawThresholds,
} from '../types/monitoring'

type Env<T> = MonitoringEnvelope<T>

export const monitoringService = {
  getSites: () =>
    api.get<Env<{ sites: MonitoringSite[] }>>('/v1/monitoring/sites')
      .then((r) => r.data.sites),

  /** Janela histórica (2h/24h/7d/30d) — comando para o box. */
  querySite: (siteId: string, window: MonitoringWindow, maxPoints?: number) =>
    api.post<Env<MonitoringCommandResponse>>(
      `/v1/monitoring/sites/${siteId}/query`,
      maxPoints != null ? { window, max_points: maxPoints } : { window },
    ).then((r) => r.data),

  /** Snapshot ao vivo (1 amostra) — comando para o box. */
  snapshot: (siteId: string) =>
    api.post<Env<MonitoringCommandResponse>>(
      `/v1/monitoring/sites/${siteId}/snapshot`,
      {},
    ).then((r) => r.data),

  getCommand: (commandId: string) =>
    api.get<Env<MonitoringCommandResponse>>(`/v1/monitoring/commands/${commandId}`)
      .then((r) => r.data),

  getLogtailCommand: (commandId: string) =>
    api.get<Env<LogtailCommandResponse>>(`/v1/monitoring/commands/${commandId}`)
      .then((r) => r.data),

  getThresholds: (siteId: string) =>
    api.get<Env<{ thresholds: RawThresholds }>>(`/v1/monitoring/sites/${siteId}/thresholds`)
      .then((r) => r.data.thresholds),

  putThresholds: (siteId: string, thresholds: RawThresholds) =>
    api.put<Env<{ thresholds: RawThresholds }>>(
      `/v1/monitoring/sites/${siteId}/thresholds`,
      { thresholds },
    ).then((r) => r.data.thresholds),

  logtail: (siteId: string, unit: string, lines = 200) =>
    api.post<Env<LogtailCommandResponse>>(
      `/v1/monitoring/sites/${siteId}/logtail`,
      { unit, lines },
    ).then((r) => r.data),

  getDetections: (siteId: string, windowMinutes = 60) => {
    const qs = new URLSearchParams({ window_minutes: String(windowMinutes) })
    return api.get<Env<DetectionsHealth>>(
      `/v1/monitoring/sites/${siteId}/detections?${qs}`,
    ).then((r) => r.data)
  },
}
