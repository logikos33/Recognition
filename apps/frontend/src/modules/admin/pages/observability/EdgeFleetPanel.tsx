/**
 * EdgeFleetPanel — painel da frota de dispositivos edge (aba "Frota Edge" da
 * Observability do Admin). Movido de pages/epi/EpiSitesHealthPage (WS9).
 *
 * WS11: visão FROTA multi-tenant via GET /admin/observability/edge-fleet
 * (agrupamento por tenant + colunas GPU°C/decode FPS da migration 089),
 * com fallback tenant-scoped (/v1/edge/sites/health) se o endpoint novo
 * estiver indisponível. Drill-down de heartbeats preservado
 * (/v1/edge/sites/:id/heartbeats + heartbeat-summary).
 * Acesso: renderizado apenas dentro do AdminLayout (AdminRoute — superadmin).
 */
import { useState, useCallback, useMemo, useRef, KeyboardEvent } from 'react'
import { X, RefreshCw } from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as ChartTooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import { usePolling } from '../../../../hooks/usePolling'
import { chartColors } from '../../../../theme/chartColors'
import { vars } from '../../../../styles/theme.css'
import { edgeService } from '../../../../services/edgeService'
import { adminService } from '../../services/adminService'
import { Badge } from '../../../../components/ui/Badge/Badge'
import type { BadgeVariant } from '../../../../components/ui/Badge/Badge'
import { Tooltip } from '../../../../components/ui/Tooltip/Tooltip'
import type {
  EdgeOverview,
  FleetSite,
  Heartbeat,
  HeartbeatSummary,
  SiteStatus,
} from '../../../../types/edge'
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
  tenantGroupRow,
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
} from './EdgeFleetPanel.css'

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

function fmtTemp(temp: number | null | undefined): string {
  if (temp == null) return '—'
  return `${temp.toFixed(0)}°C`
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

interface OverviewCardsProps {
  overview: EdgeOverview
  sites: FleetSite[]
}

function OverviewCards({ overview, sites }: OverviewCardsProps) {
  // Health counts derivados da lista de sites da frota (derived_status por site)
  const healthy = sites.filter(s => s.status === 'healthy').length
  const degraded = sites.filter(s => s.status === 'degraded').length
  const critical = sites.filter(s => s.status === 'critical').length
  const offline  = sites.filter(s => s.status === 'offline').length

  return (
    <div className={overviewRow} role="region" aria-label="Resumo da frota">
      <div className={overviewCard} aria-label={`Sites saudáveis: ${healthy}`}>
        <span className={overviewCardLabel}>Sites Saudáveis</span>
        <span className={overviewCardValueSuccess}>{healthy}</span>
        <span className={overviewCardSub}>de {sites.length} sites</span>
      </div>
      <div className={overviewCard} aria-label={`Sites degradados: ${degraded}`}>
        <span className={overviewCardLabel}>Sites Degradados</span>
        <span className={degraded > 0 ? overviewCardValueWarning : overviewCardValue}>
          {degraded}
        </span>
      </div>
      <div className={overviewCard} aria-label={`Sites críticos: ${critical}`}>
        <span className={overviewCardLabel}>Sites Críticos</span>
        <span className={critical > 0 ? overviewCardValueDanger : overviewCardValue}>
          {critical}
        </span>
      </div>
      <div className={overviewCard} aria-label={`Sites offline: ${offline}`}>
        <span className={overviewCardLabel}>Sites Offline</span>
        <span className={offline > 0 ? overviewCardValueWarning : overviewCardValue}>
          {offline}
        </span>
      </div>
      <div className={overviewCard} aria-label={`Devices online: ${overview.devices_online} de ${overview.devices_total}`}>
        <span className={overviewCardLabel}>Devices Online</span>
        <span className={overviewCardValueSuccess}>{overview.devices_online}</span>
        <span className={overviewCardSub}>de {overview.devices_total} total</span>
      </div>
      <div className={overviewCard} aria-label={`Devices revogados: ${overview.devices_revoked}`}>
        <span className={overviewCardLabel}>Devices Revogados</span>
        <span className={overview.devices_revoked > 0 ? overviewCardValueDanger : overviewCardValue}>
          {overview.devices_revoked}
        </span>
      </div>
    </div>
  )
}

/* ── SiteDetailPanel ─────────────────────────────────────────────── */

interface DetailPanelProps {
  site: FleetSite
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
                  <Tooltip label="Percentual de heartbeats saudáveis nas últimas 24h — mede a disponibilidade do site no período">
                    <span className={summaryMetricLabel}>Uptime</span>
                  </Tooltip>
                  <span className={summaryMetricValue}>
                    {summary.uptime_percent.toFixed(0)}%
                  </span>
                </div>
                <div className={summaryMetric}>
                  <Tooltip label="Quadros por segundo processados pela inferência — abaixo do esperado indica sobrecarga ou problema na GPU">
                    <span className={summaryMetricLabel}>FPS Médio</span>
                  </Tooltip>
                  <span className={summaryMetricValue}>
                    {fmtFps(summary.avg_fps)}
                  </span>
                </div>
                <div className={summaryMetric}>
                  <Tooltip label="Quantidade de heartbeats recebidos nas últimas 24h — o agente envia um a cada ciclo de telemetria">
                    <span className={summaryMetricLabel}>HB (24h)</span>
                  </Tooltip>
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
                      stroke={chartColors.grid}
                    />
                    <XAxis
                      dataKey="time"
                      tick={{ fontSize: 10, fill: chartColors.axis }}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: chartColors.axis }}
                      domain={['auto', 'auto']}
                    />
                    <ChartTooltip
                      contentStyle={{
                        background: vars.color.bgElevated,
                        border: `1px solid ${vars.color.borderDefault}`,
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                      formatter={(v) => [typeof v === 'number' ? `${v.toFixed(1)} fps` : '—', 'FPS']}
                    />
                    <Line
                      type="monotone"
                      dataKey="fps"
                      stroke={chartColors.primary}
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

/* ── Linha da tabela de sites ────────────────────────────────────── */

interface SiteRowProps {
  site: FleetSite
  isSelected: boolean
  onOpen: (site: FleetSite) => void
}

function SiteRow({ site, isSelected, onOpen }: SiteRowProps) {
  const rowClass = isSelected ? `${tableRow} ${tableRowSelected}` : tableRow

  const handleKeyDown = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onOpen(site)
    }
  }

  return (
    <tr
      className={rowClass}
      onClick={() => onOpen(site)}
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
      <td className={td}>{fmtTemp(site.gpu_temp_c)}</td>
      <td className={td}>
        <span className={fpsValue}>{fmtFps(site.decode_fps)}</span>
      </td>
      <td className={td}>
        <span className={camerasCell}>
          {site.cameras_online}/{site.cameras_total}
        </span>
      </td>
    </tr>
  )
}

/* ── EdgeFleetPanel ──────────────────────────────────────────────── */

interface EdgeFleetPanelProps {
  /** Intervalo global de polling (0 = pausado — nenhum request sai). */
  refreshMs?: number
}

export function EdgeFleetPanel({ refreshMs = 30_000 }: EdgeFleetPanelProps) {
  const [overview, setOverview] = useState<EdgeOverview | null>(null)
  const [sites, setSites] = useState<FleetSite[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSite, setSelectedSite] = useState<FleetSite | null>(null)
  const [heartbeats, setHeartbeats] = useState<Heartbeat[]>([])
  const [summary, setSummary] = useState<HeartbeatSummary | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const firstLoad = useRef(true)

  const loadData = useCallback(async () => {
    try {
      const [fleetRes, ovRes] = await Promise.allSettled([
        adminService.getEdgeFleet(),
        edgeService.getOverview(),
      ])

      let fleet: FleetSite[]
      if (fleetRes.status === 'fulfilled') {
        fleet = fleetRes.value
      } else {
        // Fallback tenant-scoped: endpoint de frota indisponível
        const sh = await edgeService.getSitesHealth()
        fleet = sh.map((site) => ({ ...site, tenant_id: '', tenant_name: '' }))
      }
      setSites(fleet)
      setOverview(ovRes.status === 'fulfilled' ? ovRes.value : null)
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar dados da frota')
      throw err // propaga para o backoff do usePolling
    } finally {
      if (firstLoad.current) {
        firstLoad.current = false
        setLoading(false)
      }
    }
  }, [])

  const openDetail = useCallback(async (site: FleetSite) => {
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

  usePolling(loadData, refreshMs > 0 ? refreshMs : 30_000, { enabled: refreshMs > 0 })

  // Agrupamento por tenant (visão frota multi-tenant)
  const groups = useMemo(() => {
    const map = new Map<string, FleetSite[]>()
    for (const site of sites) {
      const key = site.tenant_name || ''
      const arr = map.get(key) ?? []
      arr.push(site)
      map.set(key, arr)
    }
    return [...map.entries()]
  }, [sites])
  const showGroups = groups.some(([name]) => name !== '')

  /* ── Paused before first load ── */
  if (loading && refreshMs <= 0) {
    return (
      <div className={container}>
        <div className={centeredState} role="status">
          Atualização pausada — selecione um intervalo ou tente manualmente.
          <button className={retryBtn} onClick={() => void loadData().catch(() => undefined)} type="button">
            Carregar agora
          </button>
        </div>
      </div>
    )
  }

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
  if (error && sites.length === 0) {
    return (
      <div className={container}>
        <div className={centeredState} role="alert">
          <span className={errorText}>{error}</span>
          <button className={retryBtn} onClick={() => void loadData().catch(() => undefined)} type="button">
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
          <h2 className={pageTitle}>Frota Edge</h2>
          <p className={pageSubtitle}>
            Monitoramento em tempo real da frota de dispositivos edge — todos os tenants
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
      {overview && <OverviewCards overview={overview} sites={sites} />}

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
                    <th className={th} scope="col">
                      <Tooltip label="Temperatura da GPU no site — acima de ~85°C há risco de throttling e queda de FPS">
                        <span>GPU °C</span>
                      </Tooltip>
                    </th>
                    <th className={th} scope="col">
                      <Tooltip label="Quadros de vídeo decodificados por segundo — abaixo do FPS das câmeras indica gargalo de decode">
                        <span>Decode</span>
                      </Tooltip>
                    </th>
                    <th className={th} scope="col">Câmeras</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map(([tenantName, tenantSites]) => (
                    <FragmentGroup
                      key={tenantName || '—'}
                      tenantName={tenantName}
                      showHeader={showGroups}
                      sites={tenantSites}
                      selectedId={selectedSite?.site_id ?? null}
                      onOpen={openDetail}
                    />
                  ))}
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

/* ── Grupo de linhas por tenant ──────────────────────────────────── */

interface FragmentGroupProps {
  tenantName: string
  showHeader: boolean
  sites: FleetSite[]
  selectedId: string | null
  onOpen: (site: FleetSite) => void
}

function FragmentGroup({ tenantName, showHeader, sites, selectedId, onOpen }: FragmentGroupProps) {
  return (
    <>
      {showHeader && (
        <tr aria-label={`Tenant ${tenantName || 'sem tenant'}`}>
          <td className={tenantGroupRow} colSpan={7}>
            {tenantName || 'Sem tenant'} ({sites.length})
          </td>
        </tr>
      )}
      {sites.map((site) => (
        <SiteRow
          key={site.site_id}
          site={site}
          isSelected={selectedId === site.site_id}
          onOpen={onOpen}
        />
      ))}
    </>
  )
}
