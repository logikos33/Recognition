/**
 * Tipos da página oculta /monitoring — observabilidade do box edge (Jetson).
 *
 * Contrato: GET/POST /api/v1/monitoring/* (backend em paralelo).
 * O MonitoringResult é produzido NO BOX — campos podem faltar em qualquer
 * nível, então tudo aqui é defensivamente opcional. Em samples agregados
 * (1m/5m) os booleanos viram frações 0..1 (ex.: throttle.active = 0.3 ⇒
 * 30% da janela com throttle) — sempre ler via asRatio() de health.ts.
 */

/** Envelope real do backend (app/core/responses.py). */
export interface MonitoringEnvelope<T> {
  success: boolean
  message?: string
  data: T
}

export type MonitoringWindow = '2h' | '24h' | '7d' | '30d'
export type CommandState = 'pending' | 'done' | 'failed'

// ── Sites ───────────────────────────────────────────────────────────────────

export interface MonitoringSiteDevice {
  device_id: string
  last_seen_at?: string | null
  channel?: string | null
  // A API entrega target_ref/divergent POR DEVICE (o canal OTA é do device);
  // o nível de site é derivado no cliente (siteTargetRef/siteDivergent).
  target_ref?: string | null
  divergent?: boolean | null
  edge_version?: string | null
}

export interface MonitoringSiteHeartbeat {
  edge_version?: string | null
  received_at?: string | null
}

export interface MonitoringSite {
  id: string
  name: string
  tenant_id?: string | null
  tenant_name?: string | null
  tenant_slug?: string | null
  devices?: MonitoringSiteDevice[]
  last_heartbeat?: MonitoringSiteHeartbeat | null
  target_ref?: string | null
  divergent?: boolean | null
}

// ── MonitoringResult (produzido no box) ─────────────────────────────────────

export interface CollectorStatus {
  alive?: boolean
  last_sample_ts?: string | number | null
  status?: 'ok' | 'stale' | 'down'
  db_size_bytes?: number
  disk_guard_active?: boolean
}

export interface HwDisk {
  free_gb?: number
  total_gb?: number
  write_mbps?: number
  min_free_gb?: number
}

export interface HwThrottle {
  active?: boolean | number
  devices?: string[]
}

export interface HwSample {
  cpu_pct?: number
  cpu_cores_pct?: number[]
  ram_used_mb?: number
  ram_total_mb?: number
  swap_used_mb?: number
  swap_total_mb?: number
  gpu_pct?: number
  gpu_freq_hz?: number
  gpu_freq_max_hz?: number
  emc_pct?: number
  temps_c?: Record<string, number>
  power_mw?: Record<string, number>
  throttle?: HwThrottle
  power_mode?: string
  disk?: HwDisk
  uptime_s?: number
  load1?: number
  load5?: number
  load15?: number
  oom_kills_total?: number
}

export interface SvcUnitSample {
  active?: string
  sub?: string
  nrestarts?: number
  uptime_s?: number
  mem_mb?: number
  mem_max_mb?: number | null
  cpu_pct?: number
}

export interface NetSample {
  nic?: string
  tx_kbps?: number
  rx_kbps?: number
  tailscale_up?: boolean | number
  gw_rtt_ms?: number
  gw_loss_pct?: number
  api_rtt_ms?: number
  api_last_ok_ts?: number | string | null
}

export interface PipelineCameraSample {
  ffmpeg_alive?: boolean | number
  segments_per_min?: number
  push_p50_ms?: number
  push_p95_ms?: number
  push_fail_total?: number
  last_push_age_s?: number
  restarts_total?: number
  state?: string
}

export interface CollectionCameraSample {
  frames_uploaded?: number
  target?: number
}

export interface CollectionSample {
  enabled?: boolean | number
  cameras?: Record<string, CollectionCameraSample>
  state_age_s?: number
}

export interface VersionsSample {
  current_ref?: string
  ota_channel?: string
  edge_version?: string
}

export interface InferenceCameraSample {
  model?: string
  model_version?: string
  fps?: number
  latency_ms?: number
  dropped_total?: number
  detections_per_min?: Record<string, number>
}

export interface InferenceSample {
  available?: boolean | number
  cameras?: Record<string, InferenceCameraSample>
}

export interface MonitoringSample {
  /** Epoch em segundos. */
  ts: number
  hw?: HwSample
  svc?: Record<string, SvcUnitSample>
  net?: NetSample
  pipeline?: { cameras?: Record<string, PipelineCameraSample> }
  collection?: CollectionSample
  versions?: VersionsSample
  inference?: InferenceSample
}

/**
 * kinds conhecidos: throttle_start, throttle_end, oom_kill,
 * power_mode_change, service_restart, collector_start.
 */
export interface MonitoringEvent {
  ts: number
  kind: string
  detail?: string
}

export interface MonitoringResult {
  schema?: number
  /** Relógio do box no momento da resposta (ISO). */
  device_ts?: string | number
  resolution?: '10s' | '1m' | '5m'
  collector?: CollectorStatus
  samples?: MonitoringSample[]
  events?: MonitoringEvent[]
}

// ── Comandos (query / snapshot / logtail) ───────────────────────────────────

export interface MonitoringCommandResponse {
  state: CommandState
  command_id?: string
  result?: MonitoringResult
}

export interface LogtailResult {
  unit?: string
  path?: string
  lines?: string[]
  truncated?: boolean
}

export interface LogtailCommandResponse {
  state: CommandState
  command_id?: string
  result?: LogtailResult
}

// ── Detections heartbeat (cloud-side, sem egress do box) ────────────────────

export interface DetectionCameraHealth {
  camera_id: string
  last_detection_at: string | null
  count_window: number
  ingest_lag_s: number | null
}

export interface DetectionsHealth {
  cameras: DetectionCameraHealth[]
  chain: {
    detection_to_ingest_s: number | null
    ingest_to_notification_s: number | null
  }
}

// ── Thresholds ──────────────────────────────────────────────────────────────

/**
 * Shape canônico no cliente — o backend guarda Record<string, number|boolean>.
 * Type alias (não interface) de propósito: ganha index signature implícita
 * e é atribuível a RawThresholds no PUT.
 */
export type MonitoringThresholds = {
  ram_pct_warn: number
  ram_pct_crit: number
  temp_warn_c: number
  temp_crit_c: number
  disk_min_free_gb: number
  heartbeat_max_min: number
  gw_loss_warn_pct: number
  api_rtt_warn_ms: number
  restarts_warn: number
  swap_warn_pct: number
  /** Alertar quando power mode ≠ esperado (MAXN_SUPER). */
  alert_power_mode: boolean
}

export type RawThresholds = Record<string, number | boolean>
