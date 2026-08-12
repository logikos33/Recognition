/**
 * parts.tsx — blocos pequenos reutilizados pelos painéis de /monitoring.
 */
import type { ReactNode } from 'react'
import { Badge } from '../../components/ui/Badge/Badge'
import { vars } from '../../styles/theme.css'
import { asRatio, fmtPct } from './health'
import type { HealthLevel } from './health'
import * as s from './monitoring.css'

export function levelColor(level: HealthLevel): string {
  switch (level) {
    case 'crit': return vars.color.danger
    case 'warn': return vars.color.warning
    default: return vars.color.success
  }
}

/** Classifica um valor contra limiares warn/crit crescentes. */
export function levelFor(value: number | null | undefined, warn: number, crit?: number): HealthLevel {
  if (value == null || !Number.isFinite(value)) return 'ok'
  if (crit != null && value >= crit) return 'crit'
  if (value >= warn) return 'warn'
  return 'ok'
}

interface StatProps {
  label: string
  value: ReactNode
  sub?: ReactNode
}

export function Stat({ label, value, sub }: StatProps) {
  return (
    <div className={s.statRow}>
      <span className={s.statLabel}>{label}</span>
      <span className={s.statValue}>{value}</span>
      {sub != null && <span className={s.statSub}>{sub}</span>}
    </div>
  )
}

interface MeterProps {
  /** 0..100 (clampado). */
  pct: number | null
  level?: HealthLevel
}

export function Meter({ pct, level = 'ok' }: MeterProps) {
  const width = pct == null ? 0 : Math.min(100, Math.max(0, pct))
  return (
    <div className={s.meterTrack} aria-hidden="true">
      <div
        className={s.meterFill}
        style={{ width: `${width}%`, background: levelColor(level) }}
      />
    </div>
  )
}

/**
 * Badge de "vivo" para boolean|number (fração 0..1 em samples agregados).
 * null/undefined ⇒ neutro "—" (desconhecido ≠ morto).
 */
export function AliveBadge({ value }: { value: boolean | number | null | undefined }) {
  if (value == null) return <Badge variant="neutral">—</Badge>
  const ratio = asRatio(value)
  if (ratio >= 1) return <Badge variant="success">Ativo</Badge>
  if (ratio > 0) return <Badge variant="warning">{fmtPct(ratio * 100)} da janela</Badge>
  return <Badge variant="danger">Parado</Badge>
}

/** Tabela simples tokenizada (sem sort/paginação — poucas linhas por card). */
export function MiniTable({ headers, children }: { headers: string[]; children: ReactNode }) {
  return (
    <div className={s.tableWrap}>
      <table className={s.table}>
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h} className={s.th}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}
