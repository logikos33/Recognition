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

/**
 * FAIL-LOUD: valida o envelope antes de extrair `data`. Se a API não está
 * servindo o monitoramento (ex.: deploy sobrescrito → catch-all 200
 * `{"frontend":"separate service"}`), `success`/`data` faltam e devolvíamos
 * `undefined` silenciosamente — o painel abria em BRANCO MUDO. Agora vira um
 * erro diagnóstico que os banners da página exibem com "tentar de novo".
 */
function unwrap<T>(r: Env<T>): T {
  if (r == null || typeof r !== 'object' || r.success !== true || r.data === undefined) {
    throw new Error(
      'A API não está servindo o monitoramento (resposta inesperada). ' +
        'Confirme que o deploy da API-V3 inclui o blueprint /api/v1/monitoring.',
    )
  }
  return r.data
}

export interface QueryOptions {
  /** Teto de pontos na série (downsample no box antes do egress). */
  maxPoints?: number
  /** Só estas camadas por amostra (reduz payload; box filtra antes de sair). */
  layers?: string[]
  /** Janela explícita por epoch (s) — navegação sob demanda nos gráficos. */
  fromEpoch?: number
  toEpoch?: number
}

export const monitoringService = {
  getSites: () =>
    api.get<Env<{ sites: MonitoringSite[] }>>('/v1/monitoring/sites')
      .then((r) => unwrap(r).sites),

  /** Janela histórica (2h/24h/7d/30d) — comando para o box. */
  querySite: (siteId: string, window: MonitoringWindow, opts: QueryOptions = {}) => {
    const body: Record<string, unknown> = { window }
    if (opts.maxPoints != null) body.max_points = opts.maxPoints
    if (opts.layers?.length) body.layers = opts.layers
    if (opts.fromEpoch != null) body.from_epoch = opts.fromEpoch
    if (opts.toEpoch != null) body.to_epoch = opts.toEpoch
    return api.post<Env<MonitoringCommandResponse>>(
      `/v1/monitoring/sites/${siteId}/query`,
      body,
    ).then((r) => unwrap(r))
  },

  /** Snapshot ao vivo (1 amostra) — comando para o box. */
  snapshot: (siteId: string) =>
    api.post<Env<MonitoringCommandResponse>>(
      `/v1/monitoring/sites/${siteId}/snapshot`,
      {},
    ).then((r) => unwrap(r)),

  getCommand: (commandId: string) =>
    api.get<Env<MonitoringCommandResponse>>(`/v1/monitoring/commands/${commandId}`)
      .then((r) => unwrap(r)),

  getLogtailCommand: (commandId: string) =>
    api.get<Env<LogtailCommandResponse>>(`/v1/monitoring/commands/${commandId}`)
      .then((r) => unwrap(r)),

  getThresholds: (siteId: string) =>
    api.get<Env<{ thresholds: RawThresholds }>>(`/v1/monitoring/sites/${siteId}/thresholds`)
      .then((r) => unwrap(r).thresholds),

  putThresholds: (siteId: string, thresholds: RawThresholds) =>
    api.put<Env<{ thresholds: RawThresholds }>>(
      `/v1/monitoring/sites/${siteId}/thresholds`,
      { thresholds },
    ).then((r) => unwrap(r).thresholds),

  logtail: (siteId: string, unit: string, lines = 200) =>
    api.post<Env<LogtailCommandResponse>>(
      `/v1/monitoring/sites/${siteId}/logtail`,
      { unit, lines },
    ).then((r) => unwrap(r)),

  getDetections: (siteId: string, windowMinutes = 60) => {
    const qs = new URLSearchParams({ window_minutes: String(windowMinutes) })
    return api.get<Env<DetectionsHealth>>(
      `/v1/monitoring/sites/${siteId}/detections?${qs}`,
    ).then((r) => unwrap(r))
  },
}
