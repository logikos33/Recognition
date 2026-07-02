/**
 * timeBuckets — zero-fill de séries temporais do /api/v1/events/timeline.
 *
 * O backend só retorna buckets com count > 0; o gráfico precisa de série
 * densa (24 pontos em 24h, 7 em 7d, 30 em 30d). Decisão consciente do WS3:
 * zero-fill no client mantém o endpoint genérico e o payload menor.
 */

export type FillBucket = 'hour' | 'day'

export interface TimelineRow {
  bucket: string | null
  count: number
}

export interface DensePoint {
  /** ISO UTC do início do bucket */
  bucket: string
  count: number
}

const HOUR_MS = 3_600_000
const DAY_MS = 86_400_000

/**
 * Normaliza timestamps do backend: date_trunc devolve timestamp naive
 * ("2026-07-01T13:00:00", sem offset) que o JS interpretaria como hora local.
 * O banco opera em UTC — anexamos 'Z' quando não há offset explícito.
 */
function toUtcMs(iso: string): number {
  const hasOffset = /Z$|[+-]\d{2}:?\d{2}$/.test(iso)
  return new Date(hasOffset ? iso : `${iso}Z`).getTime()
}

function truncUtc(ms: number, bucket: FillBucket): number {
  const d = new Date(ms)
  if (bucket === 'hour') {
    d.setUTCMinutes(0, 0, 0)
  } else {
    d.setUTCHours(0, 0, 0, 0)
  }
  return d.getTime()
}

/**
 * Gera série densa entre fromISO (inclusivo) e toISO (exclusivo), passo de
 * 1 bucket, preenchendo count=0 onde o backend não retornou linha.
 */
export function fillBuckets(
  fromISO: string,
  toISO: string,
  bucket: FillBucket,
  rows: TimelineRow[]
): DensePoint[] {
  const step = bucket === 'hour' ? HOUR_MS : DAY_MS
  const start = truncUtc(toUtcMs(fromISO), bucket)
  const end = toUtcMs(toISO)
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return []

  const counts = new Map<number, number>()
  for (const row of rows) {
    if (!row.bucket) continue
    const key = truncUtc(toUtcMs(row.bucket), bucket)
    counts.set(key, (counts.get(key) ?? 0) + row.count)
  }

  const points: DensePoint[] = []
  for (let t = start; t < end; t += step) {
    points.push({ bucket: new Date(t).toISOString(), count: counts.get(t) ?? 0 })
  }
  return points
}

/** Rótulo pt-BR do bucket: "13h" (hour) ou "01/07" (day) — em hora local. */
export function formatBucketLabel(iso: string, bucket: FillBucket): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  if (bucket === 'hour') {
    return `${String(d.getHours()).padStart(2, '0')}h`
  }
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

export interface PeriodRange {
  from: string
  to: string
  bucket: FillBucket
}

/**
 * Intervalo alinhado ao bucket para o período selecionado, terminando no
 * bucket corrente (inclusivo): 24h → 24 pontos de hora; 7d/30d → 7/30 dias.
 */
export function rangeForPeriod(period: '24h' | '7d' | '30d', now: Date = new Date()): PeriodRange {
  const bucket: FillBucket = period === '24h' ? 'hour' : 'day'
  const step = bucket === 'hour' ? HOUR_MS : DAY_MS
  const buckets = period === '24h' ? 24 : period === '7d' ? 7 : 30
  const end = truncUtc(now.getTime(), bucket) + step // fim exclusivo: inclui bucket atual
  const start = end - buckets * step
  return {
    from: new Date(start).toISOString(),
    to: new Date(end).toISOString(),
    bucket,
  }
}
