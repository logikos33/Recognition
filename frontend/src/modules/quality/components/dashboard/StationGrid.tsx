import { StationCard } from './StationCard'
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
        padding: '14px 20px', background: '#FEF2F2',
        border: '1px solid #FECACA', borderRadius: 12,
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

  if (loading && stations.length === 0) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: gridColumns, gap: 20 }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} style={{
            borderRadius: 14, overflow: 'hidden',
            border: '1px solid #E5E7EB',
          }}>
            <div style={{ aspectRatio: '16/9', background: '#E5E7EB' }} />
            <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Array.from({ length: 4 }).map((_, j) => (
                <div key={j} style={{
                  height: 14, borderRadius: 4,
                  background: '#E5E7EB', width: j % 2 === 0 ? '60%' : '80%',
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
        color: '#9CA3AF', fontSize: 14,
        border: '1px dashed #E5E7EB', borderRadius: 14,
      }}>
        Nenhuma estação configurada.{' '}
        <a href="/quality/config" style={{ color: '#2563EB' }}>Configurar estações →</a>
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

// CSS grid string — responsivo via minmax
const gridColumns = 'repeat(auto-fill, minmax(340px, 1fr))'
