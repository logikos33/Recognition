import { useQualityDashboard } from '../hooks/useQualityDashboard'
import { DashboardHero } from '../components/dashboard/DashboardHero'
import { StationGrid } from '../components/dashboard/StationGrid'

export function QualityDashboard() {
  const {
    summary, stations,
    summaryLoading, stationsLoading,
    summaryError, stationsError,
    refresh,
  } = useQualityDashboard()

  return (
    <div style={{ padding: '24px', maxWidth: 1600, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#111827', margin: 0 }}>
          Dashboard de Qualidade
        </h1>
        <button
          onClick={refresh}
          style={{
            padding: '6px 14px', borderRadius: 8,
            border: '1px solid #D1D5DB', background: '#fff',
            cursor: 'pointer', fontSize: 13, color: '#374151',
          }}
        >
          ↺ Atualizar
        </button>
      </div>

      <DashboardHero
        summary={summary}
        loading={summaryLoading}
        error={summaryError}
        onRetry={refresh}
      />

      <div style={{ marginBottom: 16 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: '#374151' }}>
          Estações ({stations.length})
        </span>
        {stationsLoading && stations.length > 0 && (
          <span style={{ fontSize: 12, color: '#9CA3AF', marginLeft: 8 }}>atualizando…</span>
        )}
      </div>

      <StationGrid
        stations={stations}
        loading={stationsLoading}
        error={stationsError}
        onRetry={refresh}
      />
    </div>
  )
}
