/**
 * EpiSitesHealthPage — painel de Sites & Saúde.
 * Consome /edge/overview, /edge/sites/health, /sites/:id/heartbeats, /heartbeat-summary.
 */
import { useState, useCallback, useRef, KeyboardEvent } from 'react'
import { X, RefreshCw } from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import { usePolling } from '../../hooks/usePolling'
import { edgeService } from '../../services/edgeService'
import { Badge } from '../../components/ui/Badge/Badge'
import type { BadgeVariant } from '../../components/ui/Badge/Badge'
import type {
  EdgeOverview,
  SiteHealth,
  Heartbeat,
  HeartbeatSummary,
  SiteStatus,
} from '../../types/edge'
import {
  container,
  pageHeader,
  pageTitle,
  pageSubtitle,
  overviewRow,
  overviewCard,
  overviewCardLabel,
  overviewCardValue,
  overviewCardValueSuccess,
  overviewCardValueWarning,
  overviewCardValueDanger,
  overviewCardSub,
  mainContent,
  tableSection,
  tableSectionHeader,
  tableSectionTitle,
  tableWrapper,
  table,
  th,
  td,
  tableRow,
  tableRowSelected,
  siteName,
  siteIdText,
  fpsValue,
  camerasCell,
  detailPanel,
  detailHeader,
  detailTitle,
  detailCloseBtn,
  detailBody,
  summaryGrid,
  summaryMetric,
  summaryMetricLabel,
  summaryMetricValue,
  summaryMetricValueSm,
  chartSectionTitle,
  centeredState,
  errorText,
  errorBanner,
  retryBtn,
} from './EpiSitesHealthPage.css'

/* ── Helpers ─────────────────────────────────────────────────────── */

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '—'
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'agora'
  if (mins < 60) return `há ${mins}min`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `há ${hrs}h`
  return `há ${Math.floor(hrs / 24)}d`
}

function fmtFps(fps: number | null | undefined): string {
  if (fps == null) return '—'
  return fps.toFixed(1)
}

function statusVariant(status: SiteStatus): BadgeVariant {
  switch (status) {
    case 'healthy':  return 'success'
    case 'degraded': return 'warning'
    case 'critical': return 'danger'
    case 'offline':  return 'neutral'
  }
}

function statusLabel(status: SiteStatus): string {
  switch (status) {
    case 'healthy':  return 'Saudável'
    case 'degraded': return 'Degradado'
    case 'critical': return 'Crítico'
    case 'offline':  return 'Offline'
  }
}

function fmtChartTime(ts: string): string {
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/* ── OverviewCards ───────────────────────────────────────────────── */

function OverviewCards({ overview }: { overview: EdgeOverview }) {
  return (
    <div className={overviewRow} role="region" aria-label="Resumo da frota">
      <div className={overviewCard} aria-label={`Sites saudáveis: ${overview.sites_healthy}`}>
        <span className={overviewCardLabel}>Sites Saudáveis</span>
        <span className={overviewCardValueSuccess}>{overview.sites_healthy}</span>
        <span className={overviewCardSub}>de {overview.sites_total} sites</span>
      </div>
      <div className={overviewCard} aria-label={`Sites degradados: ${overview.sites_degraded}`}>
        <span className={overviewCardLabel}>Sites Degradados</span>
        <span className={overview.sites_degraded > 0 ? overviewCardValueWarning : overviewCardValue}>
          {overview.sites_degraded}
        </span>
      </div>
      <div className={overviewCard} aria-label={`Sites críticos: ${overview.sites_critical}`}>
        <span className={overviewCardLabel}>Sites Críticos</span>
        <span className={overview.sites_critical > 0 ? overviewCardValueDanger : overviewCardValue}>
          {overview.sites_critical}
        </span>
      </div>
      <div className={overviewCard} aria-label={`Sites offline: ${overview.sites_offline}`}>
        <span className={overviewCardLabel}>Sites Offline</span>
        <span className={overview.sites_offline > 0 ? overviewCardValueWarning : overviewCardValue}>
          {overview.sites_offline}
        </span>
      </div>
      <div className={overviewCard} aria-label={`Devices online: ${overview.devices_online} de ${overview.devices_total}`}>
        <span className={overviewCardLabel}>Devices Online</span>
        <span className={overviewCardValueSuccess}>{overview.devices_online}</span>
        <span className={overviewCardSub}>de {overview.devices_total} total</span>
      </div>
      <div className={overviewCard} aria-label={`Devices offline: ${overview.devices_offline}`}>
        <span className={overviewCardLabel}>Devices Offline</span>
        <span className={overview.devices_offline > 0 ? overviewCardValueDanger : overviewCardValue}>
          {overview.devices_offline}
        </span>
      </div>
    </div>
  )
}

/* ── SiteDetailPanel ─────────────────────────────────────────────── */

interface DetailPanelProps {
  site: SiteHealth
  heartbeats: Heartbeat[]
  summary: HeartbeatSummary | null
  loading: boolean
  onClose: () => void
}

function SiteDetailPanel({ site, heartbeats, summary, loading, onClose }: DetailPanelProps) {
  const chartData = heartbeats
    .filter(h => h.fps != null)
    .slice(-24)
    .map(h => ({ time: fmtChartTime(h.timestamp), fps: h.fps as number }))

  return (
    <aside
      className={detailPanel}
      aria-label={`Detalhes do site ${site.site_name}`}
      data-testid="site-detail-panel"
    >
      <div className={detailHeader}>
        <h3 className={detailTitle} title={site.site_name}>
          {site.site_name}
        </h3>
        <button
          className={detailCloseBtn}
          onClick={onClose}
          aria-label="Fechar detalhes do site"
          type="button"
        >
          <X size={16} aria-hidden="true" />
        </button>
      </div>

      <div className={detailBody}>
        {loading ? (
          <div className={centeredState} role="status" aria-live="polite" aria-busy="true">
            <RefreshCw size={16} aria-hidden="true" />
            Carregando detalhes...
          </div>
        ) : (
          <>
            {summary && (
              <div className={summaryGrid} aria-label="Métricas do site">
                <div className={summaryMetric}>
                  <span className={summaryMetricLabel}>Uptime</span>
                  <span className={summaryMetricValue}>
                    {summary.uptime_percent.toFixed(0)}%
                  </span>
                </div>
                <div className={summaryMetric}>
                  <span className={summaryMetricLabel}>FPS Médio</span>
                  <span className={summaryMetricValue}>
                    {fmtFps(summary.avg_fps)}
                  </span>
                </div>
                <div className={summaryMetric}>
                  <span className={summaryMetricLabel}>HB (24h)</span>
                  <span className={summaryMetricValue}>
                    {summary.last_24h_heartbeats}
                  </span>
                </div>
                <div className={summaryMetric}>
                  <span className={summaryMetricLabel}>Último HB</span>
                  <span className={summaryMetricValueSm}>
                    {timeAgo(summary.last_heartbeat)}
                  </span>
                </div>
              </div>
            )}

            <div>
              <div className={chartSectionTitle}>FPS — últimas 24 entradas</div>
              {chartData.length === 0 ? (
                <div className={centeredState} style={{ padding: '16px 0', flex: 'unset' }}>
                  Sem dados de heartbeat
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={160}>
                  <LineChart
                    data={chartData}
                    margin={{ top: 4, right: 8, left: -20, bottom: 0 }}
                    aria-label="Gráfico de FPS ao longo do tempo"
                    role="img"
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.06)"
                    />
                    <XAxis
                      dataKey="time"
                      tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.4)' }}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.4)' }}
                      domain={['auto', 'auto']}
                    />
                    <Tooltip
                      contentStyle={{
                        background: '#1a1a2e',
                        border: '1px solid rgba(255,255,255,0.12)',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                      formatter={(v) => [typeof v === 'number' ? `${v.toFixed(1)} fps` : '—', 'FPS']}
                    />
                    <Line
                      type="monotone"
                      dataKey="fps"
                      stroke="#06b6d4"
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </>
        )}
      </div>
    </aside>
  )
}

/* ── EpiSitesHealthPage ──────────────────────────────────────────── */

export function EpiSitesHealthPage() {
  const [overview, setOverview] = useState<EdgeOverview | null>(null)
  const [sites, setSites] = useState<SiteHealth[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSite, setSelectedSite] = useState<SiteHealth | null>(null)
  const [heartbeats, setHeartbeats] = useState<Heartbeat[]>([])
  const [summary, setSummary] = useState<HeartbeatSummary | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const firstLoad = useRef(true)

  const loadData = useCallback(async () => {
    try {
      const [ov, sh] = await Promise.all([
        edgeService.getOverview(),
        edgeService.getSitesHealth(),
      ])
      setOverview(ov)
      setSites(sh)
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar dados da frota')
    } finally {
      if (firstLoad.current) {
        firstLoad.current = false
        setLoading(false)
      }
    }
  }, [])

  usePolling(loadData, 30000)

  const openDetail = useCallback(async (site: SiteHealth) => {
    setSelectedSite(site)
    setDetailLoading(true)
    setHeartbeats([])
    setSummary(null)
    try {
      const [hb, sm] = await Promise.all([
        edgeService.getSiteHeartbeats(site.site_id),
        edgeService.getHeartbeatSummary(site.site_id),
      ])
      setHeartbeats(hb)
      setSummary(sm)
    } catch {
      // detail errors non-critical; chart shows empty state
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const closeDetail = useCallback(() => {
    setSelectedSite(null)
    setHeartbeats([])
    setSummary(null)
  }, [])

  /* ── Loading state ── */
  if (loading) {
    return (
      <div className={container}>
        <div className={centeredState} role="status" aria-live="polite" aria-busy="true">
          <RefreshCw size={18} aria-hidden="true" />
          Carregando dados da frota...
        </div>
      </div>
    )
  }

  /* ── Full error (no data at all) ── */
  if (error && !overview) {
    return (
      <div className={container}>
        <div className={centeredState} role="alert">
          <span className={errorText}>{error}</span>
          <button className={retryBtn} onClick={loadData} type="button">
            Tentar novamente
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={container}>
      {/* Header */}
      <div className={pageHeader}>
        <div>
          <h1 className={pageTitle}>Sites &amp; Saúde</h1>
          <p className={pageSubtitle}>
            Monitoramento em tempo real da frota de dispositivos edge
          </p>
        </div>
      </div>

      {/* Partial error banner */}
      {error && (
        <div role="alert" className={errorBanner}>
          {error}
        </div>
      )}

      {/* Overview cards */}
      {overview && <OverviewCards overview={overview} />}

      {/* Main content */}
      <div className={mainContent}>
        <section className={tableSection} aria-label="Lista de sites">
          <div className={tableSectionHeader}>
            <span className={tableSectionTitle}>
              Sites ({sites.length})
            </span>
          </div>

          <div className={tableWrapper}>
            {sites.length === 0 ? (
              <div className={centeredState}>Nenhum site encontrado</div>
            ) : (
              <table
                className={table}
                aria-label="Sites e status de saúde da frota"
              >
                <thead>
                  <tr>
                    <th className={th} scope="col">Site</th>
                    <th className={th} scope="col">Status</th>
                    <th className={th} scope="col">Último HB</th>
                    <th className={th} scope="col">FPS</th>
                    <th className={th} scope="col">Câmeras</th>
                  </tr>
                </thead>
                <tbody>
                  {sites.map(site => {
                    const isSelected = selectedSite?.site_id === site.site_id
                    const rowClass = isSelected
                      ? `${tableRow} ${tableRowSelected}`
                      : tableRow

                    const handleKeyDown = (e: KeyboardEvent<HTMLTableRowElement>) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        openDetail(site)
                      }
                    }

                    return (
                      <tr
                        key={site.site_id}
                        className={rowClass}
                        onClick={() => openDetail(site)}
                        onKeyDown={handleKeyDown}
                        tabIndex={0}
                        aria-selected={isSelected}
                        aria-label={`Site ${site.site_name}, status ${statusLabel(site.status)}`}
                        data-testid={`site-row-${site.site_id}`}
                      >
                        <td className={td}>
                          <div className={siteName}>{site.site_name}</div>
                          <div className={siteIdText}>{site.site_id}</div>
                        </td>
                        <td className={td}>
                          <Badge variant={statusVariant(site.status)}>
                            {statusLabel(site.status)}
                          </Badge>
                        </td>
                        <td className={td}>{timeAgo(site.last_heartbeat)}</td>
                        <td className={td}>
                          <span className={fpsValue}>{fmtFps(site.fps)}</span>
                        </td>
                        <td className={td}>
                          <span className={camerasCell}>
                            {site.cameras_online}/{site.cameras_total}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {selectedSite && (
          <SiteDetailPanel
            site={selectedSite}
            heartbeats={heartbeats}
            summary={summary}
            loading={detailLoading}
            onClose={closeDetail}
          />
        )}
      </div>
    </div>
  )
}
