import { StationCard } from './StationCard'
import { vars } from '../../../../styles/theme.css'
import type { StationLive } from '../../types/qualityDashboard'

interface StationGridProps {
  stations: StationLive[]
  loading: boolean
  error: string | null
  onRetry: () => void
}

export function StationGrid({ stations, loading, error, onRetry }: StationGridProps) {
  if (error) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '14px 20px', background: vars.color.dangerMuted,
        border: `1px solid ${vars.color.danger}`, borderRadius: 12,
      }}>
        <span style={{ color: vars.color.danger, fontSize: 14 }}>{error}</span>
        <button
          onClick={onRetry}
          style={{
            padding: '4px 12px', borderRadius: 6, border: `1px solid ${vars.color.danger}`,
            background: 'transparent', color: vars.color.danger, cursor: 'pointer', fontSize: 13,
          }}
        >
          Tentar novamente
        </button>
      </div>
    )
  }

  if (loading && stations.length === 0) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: gridColumns, gap: 20 }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} style={{
            borderRadius: 14, overflow: 'hidden',
            border: `1px solid ${vars.color.borderSubtle}`,
          }}>
            <div style={{ aspectRatio: '16/9', background: vars.color.bgHover }} />
            <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Array.from({ length: 4 }).map((_, j) => (
                <div key={j} style={{
                  height: 14, borderRadius: 4,
                  background: vars.color.bgHover, width: j % 2 === 0 ? '60%' : '80%',
                }} />
              ))}
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!loading && stations.length === 0) {
    return (
      <div style={{
        textAlign: 'center', padding: '60px 20px',
        color: vars.color.textMuted, fontSize: 14,
        border: `1px dashed ${vars.color.borderDefault}`, borderRadius: 14,
      }}>
        Nenhuma estação configurada.{' '}
        <a href="/quality/config" style={{ color: vars.color.cyan400 }}>Configurar estações →</a>
      </div>
    )
  }

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: gridColumns,
      gap: 20,
    }}>
      {stations.map((s) => (
        <StationCard key={s.id ?? s.station_code} station={s} />
      ))}
    </div>
  )
}

const gridColumns = 'repeat(auto-fill, minmax(340px, 1fr))'
