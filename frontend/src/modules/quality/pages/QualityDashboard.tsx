import { useState } from 'react'
import { useQualityDashboard } from '../hooks/useQualityDashboard'
import { DashboardHero } from '../components/dashboard/DashboardHero'
import { StationGrid } from '../components/dashboard/StationGrid'
import { QualityDashboardDemo } from './QualityDashboardDemo'
import { vars } from '../../../styles/theme.css'

const STORAGE_KEY = 'quality_dashboard_mode'

function getInitialMode(): 'pro' | 'demo' {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'demo' ? 'demo' : 'pro'
  } catch {
    return 'pro'
  }
}

export function QualityDashboard() {
  const [mode, setMode] = useState<'pro' | 'demo'>(getInitialMode)

  function switchMode(next: 'pro' | 'demo') {
    setMode(next)
    try { localStorage.setItem(STORAGE_KEY, next) } catch { /* noop */ }
  }

  if (mode === 'demo') {
    return <QualityDashboardDemo onSwitchPro={() => switchMode('pro')} />
  }

  return <QualityDashboardPro onSwitchDemo={() => switchMode('demo')} />
}

function QualityDashboardPro({ onSwitchDemo }: { onSwitchDemo: () => void }) {
  const {
    summary, stations,
    summaryLoading, stationsLoading,
    summaryError, stationsError,
    refresh,
  } = useQualityDashboard()

  return (
    <div style={{ padding: '24px', maxWidth: 1600, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: vars.color.textPrimary, margin: 0 }}>
          Dashboard de Qualidade
        </h1>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            onClick={onSwitchDemo}
            style={{
              padding: '5px 12px', borderRadius: 8, fontSize: 12, fontWeight: 600,
              border: `1px solid ${vars.color.borderDefault}`, background: vars.color.bgCard,
              color: vars.color.textSecondary, cursor: 'pointer', letterSpacing: '0.03em',
            }}
          >
            Demo
          </button>
          <button
            onClick={refresh}
            style={{
              padding: '6px 14px', borderRadius: 8,
              border: `1px solid ${vars.color.borderDefault}`, background: vars.color.bgCard,
              cursor: 'pointer', fontSize: 13, color: vars.color.textSecondary,
            }}
          >
            ↺ Atualizar
          </button>
        </div>
      </div>

      <DashboardHero
        summary={summary}
        loading={summaryLoading}
        error={summaryError}
        onRetry={refresh}
      />

      <div style={{ marginBottom: 16 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: vars.color.textSecondary }}>
          Estações ({stations.length})
        </span>
        {stationsLoading && stations.length > 0 && (
          <span style={{ fontSize: 12, color: vars.color.textMuted, marginLeft: 8 }}>atualizando…</span>
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
