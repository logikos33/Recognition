/**
 * parts.tsx — blocos pequenos reutilizados pelos painéis de /monitoring.
 */
import { Component, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
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

/**
 * Estado de ERRO — visualmente DISTINTO do EmptyState neutro (requisito:
 * "sem dado" e "erro" nunca podem ter a mesma cara). Borda + ícone + título
 * em vermelho de perigo, com o motivo e uma ação opcional de "tentar de novo".
 */
export function ErrorState({
  title,
  detail,
  action,
}: {
  title: string
  detail?: string
  action?: ReactNode
}) {
  return (
    <div
      role="alert"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        alignItems: 'flex-start',
        padding: 16,
        border: `1px solid ${vars.color.danger}`,
        borderRadius: 8,
      }}
    >
      <span
        style={{
          display: 'inline-flex',
          gap: 8,
          alignItems: 'center',
          color: vars.color.danger,
          fontWeight: 600,
        }}
      >
        <AlertTriangle size={15} aria-hidden="true" />
        {title}
      </span>
      {detail && <span className={s.muted} style={{ fontSize: 13 }}>{detail}</span>}
      {action}
    </div>
  )
}

/**
 * Fronteira de erro POR PAINEL. Um painel que lança no render (ex.: contrato
 * divergente do box) degrada só o seu card com um ErrorState — NÃO derruba a
 * página inteira via ErrorBoundary global (era exatamente a causa do "painel
 * abre e fica em branco mudo"). Re-tenta sozinho quando `resetKey` muda
 * (nova amostra chega), sem exigir clique.
 */
interface PanelBoundaryProps {
  title: string
  resetKey?: unknown
  children: ReactNode
}

export class PanelBoundary extends Component<PanelBoundaryProps, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidUpdate(prev: PanelBoundaryProps) {
    if (this.state.error != null && prev.resetKey !== this.props.resetKey) {
      this.setState({ error: null })
    }
  }

  render() {
    if (this.state.error != null) {
      return (
        <ErrorState
          title={`Falha ao renderizar: ${this.props.title}`}
          detail={`${this.state.error.message} — os demais painéis seguem funcionando.`}
        />
      )
    }
    return this.props.children
  }
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
