import { KpiCard } from './KpiCard'
import type { DashboardSummary } from '../../types/qualityDashboard'

interface DashboardHeroProps {
  summary: DashboardSummary | null
  loading: boolean
  error: string | null
  onRetry: () => void
}

export function DashboardHero({ summary, loading, error, onRetry }: DashboardHeroProps) {
  if (error) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '14px 20px', background: '#FEF2F2',
        border: '1px solid #FECACA', borderRadius: 12, marginBottom: 24,
      }}>
        <span style={{ color: '#DC2626', fontSize: 14 }}>{error}</span>
        <button
          onClick={onRetry}
          style={{
            padding: '4px 12px', borderRadius: 6, border: '1px solid #DC2626',
            background: 'transparent', color: '#DC2626', cursor: 'pointer', fontSize: 13,
          }}
        >
          Tentar novamente
        </button>
      </div>
    )
  }

  const fmt = (n: number | undefined) => (n ?? 0).toLocaleString('pt-BR')
  const okPct = summary ? `${summary.ok_pct.toFixed(1)}%` : '—'
  const stations = summary
    ? `${summary.stations_active} / ${summary.stations_total}`
    : '—'

  return (
    <div style={{ display: 'flex', gap: 14, marginBottom: 28, flexWrap: 'wrap' }}>
      <KpiCard label="Peças no turno" value={fmt(summary?.pieces_total)} loading={loading} />
      <KpiCard label="OK %" value={okPct} color="#16A34A" loading={loading} />
      <KpiCard label="NOK" value={fmt(summary?.nok_count)} color="#DC2626" loading={loading} />
      <KpiCard label="Retrabalho ativo" value={fmt(summary?.rework_active)} color="#D97706" loading={loading} />
      <KpiCard label="Estações ativas" value={stations} loading={loading} />
    </div>
  )
}
