/**
 * dashboardEdgeService — Dashboard Integrado (task-112, ADR-0053).
 *
 * Consome os endpoints tenant-scoped do blueprint dashboard_edge_bp
 * (backend /api/v1/dashboard/*). api.ts já prefixa '/api', então os paths
 * aqui começam em '/v1/dashboard/...'. Retorna o envelope { data } desembrulhado.
 * ZERO raw fetch — tudo via o cliente api central.
 */
import { api } from './api'

/** Métricas de uma época (JSONB do backend — campos opcionais). */
export interface EpochMetrics {
  ap5095?: number | null
  ap50?: number | null
  ap_small?: number | null
  ap_medium?: number | null
  ap_large?: number | null
  ar_100?: number | null
  precision?: number | null
  recall?: number | null
  lr?: number | null
  losses?: Record<string, number> | null
}

export interface EpochPoint {
  epoch: number
  framework?: string | null
  metrics: EpochMetrics
}

/** Curvas agrupadas por nome de modelo. */
export type TrainingCurves = Record<string, EpochPoint[]>

export interface ModelSummary {
  model_name: string
  /** Alias voltado ao cliente (migration 129, task D3) — NULL até alguém
   *  rebatizar. Renderizar SEMPRE via `nomeParaCliente`/`nomeInternoOuCliente`
   *  (services/modelDisplay.ts), nunca `model_name` cru — é jargão interno
   *  (nome de job/framework/UUID). */
  display_name: string | null
  framework: string | null
  last_epoch: number | null
  epoch_count: number
  ap5095: number | null
  ap_small: number | null
}

/** payload da telemetria do Jetson (subconjunto conhecido do JSONL). */
export interface TelemetryPayload {
  gpu_load_pct?: number
  ram_used_mb?: number
  fan_pwm?: number
  fan_rpm?: number
  power_mw?: Record<string, number>
  temps_c?: Record<string, number>
  fps_per_module?: Record<string, number>
  [key: string]: unknown
}

export interface TelemetrySample {
  site_id: string | null
  label: string | null
  sampled_at: string
  payload: TelemetryPayload
}

export interface TelemetrySeries {
  window: string
  samples: TelemetrySample[]
  count: number
}

export type TelemetryWindow = '15m' | '1h' | '6h' | '24h'

export const dashboardEdgeService = {
  async getModels(): Promise<ModelSummary[]> {
    const res = await api.get<{ data: { models: ModelSummary[] } }>(
      '/v1/dashboard/training-metrics/models',
    )
    return res.data.models
  },

  async getTrainingCurves(models: string[]): Promise<TrainingCurves> {
    const qs = models.length ? `?models=${encodeURIComponent(models.join(','))}` : ''
    const res = await api.get<{ data: { models: TrainingCurves } }>(
      `/v1/dashboard/training-metrics${qs}`,
    )
    return res.data.models
  },

  async getEdgeTelemetry(
    window: TelemetryWindow,
    siteId?: string,
  ): Promise<TelemetrySeries> {
    const params = new URLSearchParams({ window })
    if (siteId) params.set('site_id', siteId)
    const res = await api.get<{ data: TelemetrySeries }>(
      `/v1/dashboard/edge-telemetry?${params.toString()}`,
    )
    return res.data
  },
}
