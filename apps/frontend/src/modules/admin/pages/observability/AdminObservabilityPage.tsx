/**
 * AdminObservabilityPage — hub único de observability da plataforma (WS9).
 *
 * Abas deep-linkáveis via query param `?tab=`:
 *   - overview: saúde da plataforma (DB/Redis/R2/Celery) — absorve a antiga AdminHealthPage
 *   - edge: frota de dispositivos edge — painel movido de /epi/sites-health
 *
 * Fundação para o WS11 (dashboard BI completo de observability).
 */
import { RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { adminService } from '../../services/adminService'
import { PlatformHealthCard } from '../../components/PlatformHealthCard'
import { EdgeFleetPanel } from './EdgeFleetPanel'
import * as s from '../../components/admin.css'
import { vars } from '../../../../styles/theme.css'
import type { PlatformHealth } from '../../types/admin'

type ObservabilityTab = 'overview' | 'edge'

const TABS: { key: ObservabilityTab; label: string }[] = [
  { key: 'overview', label: 'Visão Geral' },
  { key: 'edge', label: 'Frota Edge' },
]

function parseTab(raw: string | null): ObservabilityTab {
  return raw === 'edge' ? 'edge' : 'overview'
}

/* ── Aba Visão Geral (ex-AdminHealthPage) ─────────────────────────────────── */

function OverviewTab() {
  const [health, setHealth] = useState<PlatformHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const load = () => {
    setLoading(true)
    adminService.getPlatformHealth()
      .then((r) => { setHealth(r); setLastUpdated(new Date()); setError(null) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div>
      <div className={s.flex} style={{ justifyContent: 'space-between', marginBottom: 16 }}>
        <div className={s.pageSubtitle}>
          Atualizado a cada 30s
          {lastUpdated && ` · Última verificação: ${lastUpdated.toLocaleTimeString('pt-BR')}`}
        </div>
        <button className={s.btnGhost} onClick={load} disabled={loading}>
          <RefreshCw size={14} /> Atualizar
        </button>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      {loading && !health ? (
        <div className={s.muted}>Carregando...</div>
      ) : health ? (
        <PlatformHealthCard health={health} />
      ) : null}
    </div>
  )
}

/* ── Página ───────────────────────────────────────────────────────────────── */

export function AdminObservabilityPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = parseTab(searchParams.get('tab'))

  const setTab = (next: ObservabilityTab) => {
    setSearchParams({ tab: next }, { replace: true })
  }

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Observability</div>
          <div className={s.pageSubtitle}>
            Saúde da plataforma e frota edge em um só lugar
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div
        className={s.flex}
        style={{ borderBottom: `1px solid ${vars.color.borderSubtle}`, marginBottom: 24, gap: 0 }}
        role="tablist"
        aria-label="Seções de observability"
      >
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: '8px 16px', background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 13, fontWeight: tab === t.key ? 600 : 400,
              borderBottom: tab === t.key ? `2px solid ${vars.color.primary}` : '2px solid transparent',
              color: tab === t.key ? vars.color.primary : 'inherit',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' ? <OverviewTab /> : <EdgeFleetPanel />}
    </div>
  )
}
