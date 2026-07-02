/**
 * AdminObservabilityPage — dashboard BI consolidado de observability (WS11).
 *
 * Layout top-down inspirado em RED/USE: visão geral (status + KPIs + séries)
 * → drill-down por área (Infra, Frota Edge, Workers, Streams).
 *
 * Abas deep-linkáveis via `?tab=`:
 *   overview — KPIs da API, status dos serviços, séries de erro/latência, migrations
 *   infra    — DB (pg_stat_activity), Redis, R2, filas Celery com drill-down
 *   edge     — frota multi-tenant (EdgeFleetPanel)
 *   workers  — workers GPU on-premise (restart com ConfirmDialog)
 *   streams  — status agregado de streams (uma request, sem N+1)
 *
 * Polling global: seletor Pausado/10s/30s/1m/5m (localStorage
 * `obs.refreshInterval`) + Pausar/Retomar; janela histórica 1h/6h/24h/7d
 * (localStorage `obs.window`). Pausado ⇒ NENHUM request automático sai.
 */
import { useCallback, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { usePolling } from '../../../../hooks/usePolling'
import { useToast } from '../../../../components/ui/Toast/useToast'
import { Tooltip } from '../../../../components/ui/Tooltip/Tooltip'
import { Badge } from '../../../../components/ui/Badge/Badge'
import type { BadgeVariant } from '../../../../components/ui/Badge/Badge'
import { Banner } from '../../../../components/ui/Banner/Banner'
import { Skeleton } from '../../../../components/ui/Skeleton/Skeleton'
import { adminService } from '../../services/adminService'
import { chartColors } from '../../../../theme/chartColors'
import { vars } from '../../../../styles/theme.css'
import * as s from '../../components/admin.css'
import type { ObsWindow, ObservabilitySummary } from '../../types/admin'
import { ObservabilityHeader, REFRESH_OPTIONS, WINDOW_OPTIONS } from './ObservabilityHeader'
import { TimeseriesChart } from './TimeseriesChart'
import { EdgeFleetPanel } from './EdgeFleetPanel'
import { InfraPanel } from './InfraPanel'
import { StreamsPanel } from './StreamsPanel'
import { WorkersPanel } from './WorkersPanel'

type ObservabilityTab = 'overview' | 'infra' | 'edge' | 'workers' | 'streams'

const TABS: { key: ObservabilityTab; label: string }[] = [
  { key: 'overview', label: 'Visão Geral' },
  { key: 'infra', label: 'Infra' },
  { key: 'edge', label: 'Frota Edge' },
  { key: 'workers', label: 'Workers' },
  { key: 'streams', label: 'Streams' },
]

function parseTab(raw: string | null): ObservabilityTab {
  return TABS.some((t) => t.key === raw) ? (raw as ObservabilityTab) : 'overview'
}

const REFRESH_STORAGE_KEY = 'obs.refreshInterval'
const WINDOW_STORAGE_KEY = 'obs.window'

function loadStoredInterval(): number {
  const raw = window.localStorage.getItem(REFRESH_STORAGE_KEY)
  const n = raw == null ? Number.NaN : Number(raw)
  return REFRESH_OPTIONS.some((o) => o.value === n) ? n : 30_000
}

function loadStoredWindow(): ObsWindow {
  const raw = window.localStorage.getItem(WINDOW_STORAGE_KEY)
  return WINDOW_OPTIONS.some((o) => o.value === raw) ? (raw as ObsWindow) : '24h'
}

function serviceBadgeVariant(status: string | undefined): BadgeVariant {
  switch (status) {
    case 'healthy':  return 'success'
    case 'degraded': return 'warning'
    case 'critical': return 'danger'
    default:         return 'neutral'
  }
}

/* ── KPI card com tooltip pt-BR ───────────────────────────────────────────── */

interface KpiCardProps {
  label: string
  value: string
  tooltip: string
  sub?: string
  danger?: boolean
}

function KpiCard({ label, value, tooltip, sub, danger }: KpiCardProps) {
  return (
    <Tooltip label={tooltip}>
      <div className={s.metricCard} aria-label={`${label}: ${value}`}>
        <div
          className={s.metricValue}
          style={danger ? { color: vars.color.danger } : undefined}
        >
          {value}
        </div>
        <div className={s.metricLabel}>{label}</div>
        {sub && <div className={s.muted}>{sub}</div>}
      </div>
    </Tooltip>
  )
}

/* ── Aba Visão Geral ──────────────────────────────────────────────────────── */

const SERVICE_LABELS: Record<string, string> = {
  database: 'Banco de dados',
  redis: 'Redis',
  r2: 'Armazenamento (R2)',
  celery: 'Filas (Celery)',
}

interface OverviewTabProps {
  summary: ObservabilitySummary | null
  windowSel: ObsWindow
  refreshMs: number
  paused: boolean
}

function OverviewTab({ summary, windowSel, refreshMs, paused }: OverviewTabProps) {
  if (!summary) {
    if (paused) {
      return (
        <Banner variant="info">
          Atualização pausada — selecione um intervalo de atualização ou clique
          em &quot;Coletar agora&quot; para carregar os dados.
        </Banner>
      )
    }
    return (
      <div className={s.metricsGrid}>
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} variant="rect" height={92} />
        ))}
      </div>
    )
  }

  const queuesBehind = summary.celery.queues.filter((q) => q.depth > 0).length
  const migrationsPending = summary.migrations.pending.length

  return (
    <div>
      {/* KPIs principais — topo-esquerda = mais importante (RED da API) */}
      <div className={s.metricsGrid} style={{ marginBottom: 16 }}>
        <KpiCard
          label="Requisições (1h)"
          value={String(summary.api.req_1h)}
          tooltip="Total de requisições atendidas pela API na última hora (health checks e streams excluídos)"
        />
        <KpiCard
          label="Taxa de erro"
          value={`${summary.api.err_rate_pct.toFixed(1)}%`}
          danger={summary.api.err_rate_pct > 5}
          tooltip="Percentual de respostas com erro (4xx/5xx) sobre o total da última hora — acima de 5% merece investigação"
        />
        <KpiCard
          label="Latência média"
          value={`${summary.api.avg_ms.toFixed(0)} ms`}
          tooltip="Tempo médio de resposta da API na última hora — quanto menor, mais rápida a experiência de quem usa"
        />
        <KpiCard
          label="Workers GPU"
          value={`${summary.workers.online}/${summary.workers.total}`}
          danger={summary.workers.online < summary.workers.total}
          tooltip="Workers de GPU on-premise enviando heartbeat agora / total registrado — worker offline cai para processamento na nuvem"
        />
        <KpiCard
          label="Sites offline"
          value={String(summary.edge.sites_offline)}
          sub={`de ${summary.edge.sites_total} sites`}
          danger={summary.edge.sites_offline > 0}
          tooltip="Sites edge sem heartbeat há mais de 2 minutos — câmeras desses locais podem estar sem monitoramento"
        />
        <KpiCard
          label="Filas em atraso"
          value={String(queuesBehind)}
          danger={queuesBehind > 0}
          tooltip="Filas de processamento com tarefas aguardando — cresce quando os workers não dão vazão ao volume"
        />
      </div>

      {/* Status por serviço */}
      <div className={s.card} style={{ marginBottom: 16 }}>
        <div className={s.cardTitle}>Serviços</div>
        <div className={s.flex} style={{ flexWrap: 'wrap', gap: 12 }}>
          {Object.entries(summary.services).map(([key, svc]) => (
            <Tooltip
              key={key}
              label={
                svc.details
                  ? `${SERVICE_LABELS[key] ?? key}: ${svc.details}`
                  : `Tempo de resposta do serviço: ${svc.latency_ms != null ? `${svc.latency_ms} ms` : 'não medido'}`
              }
            >
              <span className={s.flex} style={{ gap: 6 }}>
                <Badge variant={serviceBadgeVariant(svc.status)}>
                  {SERVICE_LABELS[key] ?? key}
                </Badge>
                {svc.latency_ms != null && (
                  <span className={s.muted}>{svc.latency_ms} ms</span>
                )}
              </span>
            </Tooltip>
          ))}
        </div>
      </div>

      {/* Séries temporais da API */}
      <div className={s.twoColumn} style={{ marginBottom: 16 }}>
        <TimeseriesChart
          key={`err-${windowSel}`}
          title="Erros da API (5xx)"
          tooltip="Respostas com erro do servidor por coleta (1 min) — picos indicam instabilidade na API"
          scope="api"
          metric="http_5xx"
          window={windowSel}
          refreshMs={refreshMs}
          color={chartColors.danger}
        />
        <TimeseriesChart
          key={`lat-${windowSel}`}
          title="Latência média da API"
          tooltip="Tempo médio de resposta (ms) por coleta — tendência de alta indica sobrecarga"
          scope="api"
          metric="http_avg_ms"
          window={windowSel}
          refreshMs={refreshMs}
          unit=" ms"
        />
      </div>

      {/* Migrations */}
      <div className={s.card}>
        <div className={s.flex} style={{ marginBottom: 8 }}>
          <span className={s.cardTitle} style={{ marginBottom: 0 }}>Migrations</span>
          <Tooltip label="Versão do banco de dados: última migration aplicada vs arquivos no repositório — pendências indicam deploy incompleto">
            <Badge variant={migrationsPending > 0 ? 'warning' : 'success'}>
              {migrationsPending > 0 ? `${migrationsPending} pendente(s)` : 'Em dia'}
            </Badge>
          </Tooltip>
        </div>
        <div className={s.flex} style={{ flexWrap: 'wrap', gap: 16 }}>
          <span className={s.muted}>
            Última aplicada: <span className={s.mono}>{summary.migrations.latest_applied ?? '—'}</span>
          </span>
          <span className={s.muted}>
            Aplicadas: {summary.migrations.applied_count}
            {summary.migrations.files_count != null && ` de ${summary.migrations.files_count} arquivos`}
          </span>
          {migrationsPending > 0 && (
            <span className={s.mono}>{summary.migrations.pending.join(', ')}</span>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── Página ───────────────────────────────────────────────────────────────── */

export function AdminObservabilityPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = parseTab(searchParams.get('tab'))
  const toast = useToast()

  const [intervalMs, setIntervalMs] = useState<number>(loadStoredInterval)
  const [paused, setPaused] = useState(false)
  const [windowSel, setWindowSel] = useState<ObsWindow>(loadStoredWindow)
  const [summary, setSummary] = useState<ObservabilitySummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [collecting, setCollecting] = useState(false)

  // 0 = Pausado no seletor; botão Pausar também zera o polling
  const effectiveMs = paused ? 0 : intervalMs

  const loadSummary = useCallback(async () => {
    try {
      const data = await adminService.getObservabilitySummary()
      setSummary(data)
      setError(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar resumo')
      throw e // propaga para o backoff do usePolling
    }
  }, [])

  usePolling(loadSummary, effectiveMs > 0 ? effectiveMs : 30_000, {
    enabled: effectiveMs > 0,
  })

  const setTab = (next: ObservabilityTab) => {
    setSearchParams({ tab: next }, { replace: true })
  }

  const handleIntervalChange = (ms: number) => {
    setIntervalMs(ms)
    window.localStorage.setItem(REFRESH_STORAGE_KEY, String(ms))
  }

  const handleWindowChange = (w: ObsWindow) => {
    setWindowSel(w)
    window.localStorage.setItem(WINDOW_STORAGE_KEY, w)
  }

  const handleCollectNow = async () => {
    setCollecting(true)
    try {
      const res = await adminService.collectObservabilityNow()
      toast.success('Snapshot coletado', `${res.points_recorded} pontos gravados`)
      await loadSummary().catch(() => undefined)
    } catch (e: unknown) {
      toast.error(
        'Falha ao coletar',
        e instanceof Error ? e.message : 'Erro inesperado',
      )
    } finally {
      setCollecting(false)
    }
  }

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Observability</div>
          <div className={s.pageSubtitle}>
            Saúde da plataforma, infraestrutura, frota edge, workers e streams em um só lugar
          </div>
        </div>
      </div>

      <ObservabilityHeader
        status={summary?.status ?? null}
        collectedAt={summary?.collected_at ?? null}
        intervalMs={intervalMs}
        paused={paused}
        windowSel={windowSel}
        collecting={collecting}
        onIntervalChange={handleIntervalChange}
        onTogglePause={() => setPaused((p) => !p)}
        onWindowChange={handleWindowChange}
        onCollectNow={handleCollectNow}
      />

      {error && <div className={s.alertBanner.danger}>{error}</div>}

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

      {tab === 'overview' && (
        <OverviewTab
          summary={summary}
          windowSel={windowSel}
          refreshMs={effectiveMs}
          paused={effectiveMs === 0}
        />
      )}
      {tab === 'infra' && (
        <InfraPanel summary={summary} windowSel={windowSel} refreshMs={effectiveMs} />
      )}
      {tab === 'edge' && <EdgeFleetPanel refreshMs={effectiveMs} />}
      {tab === 'workers' && <WorkersPanel refreshMs={effectiveMs} />}
      {tab === 'streams' && <StreamsPanel refreshMs={effectiveMs} />}
    </div>
  )
}
