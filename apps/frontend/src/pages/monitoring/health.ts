/**
 * health.ts — lógica pura da página /monitoring: semáforo, thresholds,
 * runbooks e formatação. Sem React, sem fetch — testável isolado.
 *
 * Regra do contrato: em samples agregados (1m/5m) booleanos viram frações
 * 0..1 — TODO acesso a boolean|number passa por asRatio().
 */
import type {
  CollectorStatus,
  DetectionsHealth,
  MonitoringSample,
  MonitoringSite,
  MonitoringThresholds,
  RawThresholds,
} from '../../types/monitoring'

// ── Ratio helper (boolean|number → 0..1) ────────────────────────────────────

export function asRatio(v: boolean | number | null | undefined): number {
  if (v == null) return 0
  if (typeof v === 'boolean') return v ? 1 : 0
  return v
}

// ── Thresholds ──────────────────────────────────────────────────────────────

export const EXPECTED_POWER_MODE = 'MAXN_SUPER'

/** Units Type=oneshot disparadas por timer — `inactive` é o estado normal. */
export const ONESHOT_UNITS = new Set(['edge-sync-agent-updater'])

/**
 * Timestamps do box chegam como epoch em SEGUNDOS (int) — mas o contrato
 * tolera ISO string. Converte qualquer um para epoch em ms; null se inválido.
 */
export function toEpochMs(v: string | number | null | undefined): number | null {
  if (v == null) return null
  if (typeof v === 'number') return v < 1e12 ? v * 1000 : v
  const asNum = Number(v)
  if (!Number.isNaN(asNum) && v.trim() !== '') return asNum < 1e12 ? asNum * 1000 : asNum
  const parsed = Date.parse(v)
  return Number.isNaN(parsed) ? null : parsed
}

export const DEFAULT_THRESHOLDS: MonitoringThresholds = {
  ram_pct_warn: 85,
  ram_pct_crit: 92,
  temp_warn_c: 85,
  temp_crit_c: 95,
  disk_min_free_gb: 10,
  heartbeat_max_min: 10,
  gw_loss_warn_pct: 2,
  api_rtt_warn_ms: 300,
  restarts_warn: 3,
  swap_warn_pct: 50,
  alert_power_mode: true,
}

/** Merge defensivo: defaults no cliente quando o GET vier vazio/parcial. */
export function mergeThresholds(raw: RawThresholds | null | undefined): MonitoringThresholds {
  const out: MonitoringThresholds = { ...DEFAULT_THRESHOLDS }
  if (!raw) return out
  for (const key of Object.keys(DEFAULT_THRESHOLDS) as (keyof MonitoringThresholds)[]) {
    const v = raw[key]
    if (v == null) continue
    if (key === 'alert_power_mode') {
      out.alert_power_mode = typeof v === 'boolean' ? v : asRatio(v) > 0
    } else if (typeof v === 'number' && Number.isFinite(v)) {
      out[key] = v
    }
  }
  return out
}

// ── Runbooks (uma linha de "o que fazer" por alerta) ────────────────────────

export const RUNBOOK: Record<string, string> = {
  throttle: 'Verificar ventilação/dissipador e carga; conferir nvpmodel.',
  temp: 'Verificar ventilação/dissipador; reduzir carga se a temperatura persistir alta.',
  ram: 'Identificar unit acima do teto na tabela de serviços; considerar restart da unit.',
  swap: 'Swap alto degrada latência — identificar unit consumindo RAM e conter o vazamento.',
  disk: 'Ver ring buffer e logs; nunca deixar chegar na reserva.',
  disk_guard: 'Reserva de disco atingida — o device intertrava. Liberar espaço AGORA (ring buffer/logs).',
  heartbeat: 'Checar pipeline da câmera e unit de inferência — silêncio ≠ sem violação.',
  ota: 'Rodar o updater / checar edge-sync-agent-updater.timer.',
  collector: 'Checar a unit edge-monitoring-collector no box (ver log) e o espaço em disco.',
  net_gw: 'Checar link local e MikroTik do site; perda no gateway derruba os streams.',
  net_api: 'RTT alto até a API — checar WireGuard/Tailscale e a banda de upload do site.',
  net_vpn: 'Túnel Tailscale caído — checar conectividade do box e o hub WireGuard.',
  power_mode: 'Conferir nvpmodel no box — modo diferente do esperado reduz a capacidade de inferência.',
  service: "Ver o log da unit (botão 'Ver log'); restarts em sequência indicam crash-loop.",
  service_down: "Unit parada — ver o log (botão 'Ver log') e reiniciar a unit no box.",
  oom: 'Ver qual processo foi morto (log da unit); revisar tetos de memória das units.',
  pipeline: 'Checar ffmpeg/câmera no box; última imagem antiga = stream parado na origem.',
}

// ── Semáforo ────────────────────────────────────────────────────────────────

export type HealthLevel = 'ok' | 'warn' | 'crit'

export interface HealthReason {
  id: string
  severity: 'warn' | 'crit'
  label: string
  runbook: string
}

export interface HealthSummary {
  level: HealthLevel
  reasons: HealthReason[]
}

/** Duração (s) do throttling contínuo até a última amostra, varrendo p/ trás. */
export function throttleDurationS(samples: MonitoringSample[]): number {
  if (!samples.length) return 0
  let start: number | null = null
  for (let i = samples.length - 1; i >= 0; i--) {
    const s = samples[i]
    if (asRatio(s.hw?.throttle?.active) > 0) start = s.ts
    else break
  }
  if (start == null) return 0
  return Math.max(0, samples[samples.length - 1].ts - start)
}

export function maxTemp(temps: Record<string, number> | undefined): number | null {
  if (!temps) return null
  const vals = Object.values(temps).filter((v) => Number.isFinite(v))
  return vals.length ? Math.max(...vals) : null
}

export function pctOf(used: number | undefined, total: number | undefined): number | null {
  if (used == null || total == null || total <= 0) return null
  return (used / total) * 100
}

interface EvaluateArgs {
  latest: MonitoringSample | null
  samples: MonitoringSample[]
  collector: CollectorStatus | null
  detections: DetectionsHealth | null
  thresholds: MonitoringThresholds
  site: MonitoringSite | null
  /** Idade da última amostra do coletor em segundos (null = desconhecida). */
  sampleAgeS: number | null
  /** Relógio local (ms) — injetável para teste. */
  nowMs: number
}

/**
 * Semáforo geral computado NO CLIENTE da última amostra + thresholds.
 * Retorna o pior nível + a lista completa de motivos (pior primeiro).
 */
export function evaluateHealth(args: EvaluateArgs): HealthSummary {
  const { latest, samples, collector, detections, thresholds: t, site, sampleAgeS, nowMs } = args
  const reasons: HealthReason[] = []
  const add = (id: string, severity: 'warn' | 'crit', label: string, runbookKey?: string) =>
    reasons.push({ id, severity, label, runbook: RUNBOOK[runbookKey ?? id] ?? '' })

  // Coletor
  if (collector?.status === 'down' || (collector && collector.alive === false)) {
    add('collector', 'crit', 'Coletor de monitoramento parado no box', 'collector')
  } else if (collector?.status === 'stale') {
    add(
      'collector',
      'warn',
      sampleAgeS != null
        ? `Coletor sem dados há ${fmtDurationS(sampleAgeS)}`
        : 'Coletor com dados atrasados',
      'collector',
    )
  }
  if (collector?.disk_guard_active) {
    add('disk_guard', 'crit', 'Reserva de disco atingida — guarda de disco ativa', 'disk_guard')
  }

  const hw = latest?.hw
  if (hw) {
    // Throttling (destaque)
    if (asRatio(hw.throttle?.active) > 0) {
      const dur = throttleDurationS(samples)
      const devices = hw.throttle?.devices?.length ? ` (${hw.throttle.devices.join(', ')})` : ''
      add(
        'throttle',
        'crit',
        dur > 0
          ? `Throttling térmico há ${fmtDurationS(dur)}${devices}`
          : `Throttling térmico ativo${devices}`,
      )
    }

    // Temperatura
    const tmax = maxTemp(hw.temps_c)
    if (tmax != null) {
      if (tmax >= t.temp_crit_c) add('temp', 'crit', `Temperatura ${tmax.toFixed(0)}°C (crítico ≥ ${t.temp_crit_c}°C)`)
      else if (tmax >= t.temp_warn_c) add('temp', 'warn', `Temperatura ${tmax.toFixed(0)}°C (atenção ≥ ${t.temp_warn_c}°C)`)
    }

    // RAM / swap
    const ramPct = pctOf(hw.ram_used_mb, hw.ram_total_mb)
    if (ramPct != null) {
      if (ramPct >= t.ram_pct_crit) add('ram', 'crit', `RAM ${ramPct.toFixed(0)}% (crítico ≥ ${t.ram_pct_crit}%)`)
      else if (ramPct >= t.ram_pct_warn) add('ram', 'warn', `RAM ${ramPct.toFixed(0)}% (atenção ≥ ${t.ram_pct_warn}%)`)
    }
    const swapPct = pctOf(hw.swap_used_mb, hw.swap_total_mb)
    if (swapPct != null && swapPct >= t.swap_warn_pct) {
      add('swap', 'warn', `Swap ${swapPct.toFixed(0)}% (atenção ≥ ${t.swap_warn_pct}%)`)
    }

    // Disco
    const free = hw.disk?.free_gb
    if (free != null) {
      const reserve = hw.disk?.min_free_gb
      if (reserve != null && free <= reserve) {
        add('disk', 'crit', `Disco a ${free.toFixed(1)} GB livres — DENTRO da reserva (${reserve} GB)`, 'disk_guard')
      } else if (free < t.disk_min_free_gb) {
        add('disk', 'warn', `Disco com ${free.toFixed(1)} GB livres (mínimo ${t.disk_min_free_gb} GB)`)
      }
    }

    // Power mode
    if (t.alert_power_mode && hw.power_mode && hw.power_mode !== EXPECTED_POWER_MODE) {
      add('power_mode', 'warn', `Power mode ${hw.power_mode} (esperado ${EXPECTED_POWER_MODE})`)
    }
  }

  // Serviços — units ONESHOT disparadas por timer (updater) ficam `inactive`
  // entre execuções por design: só `failed` é problema para elas. Sem esta
  // exceção o semáforo acusa "Crítico" permanente (visto no box real).
  if (latest?.svc) {
    for (const [unit, svc] of Object.entries(latest.svc)) {
      const oneshot = ONESHOT_UNITS.has(unit)
      if (svc.active && svc.active !== 'active' && (!oneshot || svc.active === 'failed')) {
        add(`svc-${unit}`, 'crit', `Unit ${unit} está ${svc.active}`, 'service_down')
      } else if ((svc.nrestarts ?? 0) >= t.restarts_warn) {
        add(`svc-restarts-${unit}`, 'warn', `Unit ${unit} com ${svc.nrestarts} restarts`, 'service')
      }
    }
  }

  // Rede
  const net = latest?.net
  if (net) {
    if (net.tailscale_up != null && asRatio(net.tailscale_up) < 0.5) {
      add('net_vpn', 'crit', 'Tailscale caído no box')
    }
    if (net.gw_loss_pct != null && net.gw_loss_pct >= t.gw_loss_warn_pct) {
      add('net_gw', 'warn', `Perda de ${net.gw_loss_pct.toFixed(1)}% no gateway (atenção ≥ ${t.gw_loss_warn_pct}%)`)
    }
    if (net.api_rtt_ms != null && net.api_rtt_ms >= t.api_rtt_warn_ms) {
      add('net_api', 'warn', `RTT até a API ${net.api_rtt_ms.toFixed(0)} ms (atenção ≥ ${t.api_rtt_warn_ms} ms)`)
    }
  }

  // OTA / versão
  if (site?.divergent) {
    add('ota', 'warn', `Release divergente do target do canal${site.target_ref ? ` (${site.target_ref})` : ''}`)
  }

  // Heartbeat de detecção (endpoint cloud-side)
  if (detections) {
    const silent = detections.cameras.filter((c) => {
      const age = agoMinutes(c.last_occurred_at, nowMs)
      return age == null || age > t.heartbeat_max_min
    })
    if (silent.length > 0) {
      add(
        'heartbeat',
        'warn',
        silent.length === 1
          ? `Câmera ${silent[0].camera_id} sem detecção há ${fmtHeartbeatAge(silent[0].last_occurred_at, nowMs)}`
          : `${silent.length} câmeras sem detecção acima do limiar (${t.heartbeat_max_min} min)`,
      )
    }
  }

  // Ordena: crit primeiro
  reasons.sort((a, b) => (a.severity === b.severity ? 0 : a.severity === 'crit' ? -1 : 1))
  const level: HealthLevel = reasons.some((r) => r.severity === 'crit')
    ? 'crit'
    : reasons.length > 0
      ? 'warn'
      : 'ok'
  return { level, reasons }
}

// ── Formatação pt-BR ────────────────────────────────────────────────────────

export function fmtDurationS(s: number): string {
  if (!Number.isFinite(s) || s < 0) return '—'
  if (s < 60) return `${Math.round(s)} s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} min`
  const h = Math.floor(m / 60)
  if (h < 48) return `${h} h ${m % 60} min`
  return `${Math.floor(h / 24)} d ${h % 24} h`
}

/** Minutos desde um ISO timestamp (null = nunca/inválido). */
export function agoMinutes(iso: string | null | undefined, nowMs: number): number | null {
  if (!iso) return null
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return null
  return Math.max(0, (nowMs - t) / 60000)
}

export function fmtHeartbeatAge(iso: string | null | undefined, nowMs: number): string {
  const m = agoMinutes(iso, nowMs)
  if (m == null) return 'nunca'
  return fmtDurationS(m * 60)
}

export function fmtMb(mb: number | undefined): string {
  if (mb == null) return '—'
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
  return `${Math.round(mb)} MB`
}

export function fmtBytes(b: number | undefined): string {
  if (b == null) return '—'
  if (b >= 1024 ** 3) return `${(b / 1024 ** 3).toFixed(1)} GB`
  if (b >= 1024 ** 2) return `${(b / 1024 ** 2).toFixed(1)} MB`
  if (b >= 1024) return `${(b / 1024).toFixed(0)} KB`
  return `${b} B`
}

export function fmtGhz(hz: number | undefined): string {
  if (hz == null) return '—'
  return `${(hz / 1e9).toFixed(2)} GHz`
}

export function fmtPct(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${v.toFixed(digits)}%`
}

export function fmtNum(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toFixed(digits)
}

export function fmtKbps(v: number | undefined): string {
  if (v == null) return '—'
  if (v >= 1000) return `${(v / 1000).toFixed(1)} Mbps`
  return `${Math.round(v)} kbps`
}

/** Rótulo de eixo/tooltip para epoch (s) conforme a janela. */
export function fmtEpoch(tsS: number, window: '2h' | '24h' | '7d' | '30d'): string {
  const d = new Date(tsS * 1000)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  if (window === '7d' || window === '30d') {
    return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')} ${hh}h`
  }
  return `${hh}:${mm}`
}

export function fmtIsoShort(iso: string | null | undefined): string {
  if (!iso) return '—'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return '—'
  const d = new Date(t)
  return d.toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

export const EVENT_LABELS: Record<string, string> = {
  throttle_start: 'Início de throttling',
  throttle_end: 'Fim de throttling',
  oom_kill: 'OOM kill',
  power_mode_change: 'Mudança de power mode',
  service_restart: 'Restart de serviço',
  collector_start: 'Coletor iniciado',
}

/** Unidades com logtail disponível no box. */
export const LOGTAIL_UNITS = [
  'edge-live-view',
  'edge-sync-agent',
  'edge-frame-collector',
  'edge-monitoring-collector',
] as const

// ── OTA: derivação site-level a partir dos devices ──────────────────────────
//
// A API entrega target_ref/divergent POR DEVICE. Para o cabeçalho/painel, o
// site herda o target do primeiro device que tiver um. A divergência mais
// honesta compara o `current_ref` REAL do box (symlink do OTA, vem na
// amostra) com o target — o edge_version do heartbeat é um rótulo manual
// (ex.: "gate1.6-e2e") que nunca bate com SHA e geraria alerta falso.

export function siteTargetRef(site: MonitoringSite | null): string | null {
  if (!site) return null
  if (site.target_ref) return site.target_ref
  for (const dev of site.devices ?? []) {
    if (dev.target_ref) return dev.target_ref
  }
  return null
}

export function siteDivergent(
  site: MonitoringSite | null,
  currentRef?: string | null,
): boolean | null {
  const target = siteTargetRef(site)
  if (currentRef && target) return currentRef !== target
  // Sem current_ref (amostra ainda não chegou): não há veredito honesto —
  // o divergent por edge_version compararia rótulo com SHA (falso positivo).
  return null
}
