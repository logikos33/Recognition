/**
 * FuelingPage — Módulo de controle de carregamento (carga e descarga).
 *
 * 3 abas:
 *   Dashboard  — KPIs + gráficos (operações diárias, tempo por baia, causas de não conformidade)
 *   Baias      — Grid de cards com status dinâmico por baia
 *   Eventos    — Tabela de detecções recentes
 *
 * Superadmin: dados de demonstração via /api/fueling/dashboard e /api/fueling/bays.
 * Demais roles: dados reais do tenant ou estado vazio enquanto módulo em configuração.
 */
import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { Package, Truck, RefreshCw, Activity, Gauge, Video } from 'lucide-react'
import { api } from '../../services/api'
import { useAuth } from '../../hooks/useAuth'
import { LoadingSpinner } from '../../components/shared/LoadingSpinner'
import { CameraPlayer } from '../../components/monitoring/CameraPlayer'
import type { Camera } from '../../types'
import { vars } from '../../styles/theme.css'

// ── Types ──────────────────────────────────────────────────────────────────────

interface DashboardKpis {
  total_carregado: number
  tempo_medio_minutos: number
  total_itens_movimentados: number
  itens_nao_conformes: number
  taxa_nao_conformidade: number
  eventos_nao_conformidade: number
  taxa_ocupacao_percent: number
}

interface DashboardData {
  no_data?: boolean
  kpis?: DashboardKpis
  top_baias_produtivas?: Array<{ baia: string; itens: number }>
  top_baias_perda?: Array<{ baia: string; perda: number }>
  series_operacoes_diarias?: Array<{ dia: string; operacoes: number }>
  series_tempo_por_baia?: Array<{ baia: string; tempo: number }>
  pizza_causas_perda?: Array<{ name: string; value: number }>
}

interface Bay {
  id: number
  nome: string
  status: 'active' | 'idle' | 'maintenance'
  operador: string | null
  placa: string | null
  total_itens: number
  progresso: number
}

interface FuelingEvent {
  id: string
  camera_id: string
  class_name: string
  confidence: number | null
  created_at: string | null
}

type Period = 'today' | 'week' | 'month'

// ── Constants ─────────────────────────────────────────────────────────────────

const PERIOD_LABELS: Record<Period, string> = { today: 'Hoje', week: 'Semana', month: 'Mês' }
const PIE_COLORS = ['#6366f1', '#f59e0b', vars.color.success, '#f87171']
const CLASS_LABELS: Record<string, string> = {
  truck: 'Caminhão', plate: 'Placa',
  forklift: 'Empilhadeira', product_box: 'Caixa', pallet: 'Pallet',
}
const BAY_STATUS_COLORS = { active: vars.color.success, idle: vars.color.textMuted, maintenance: '#f59e0b' }
const BAY_STATUS_LABELS = { active: 'Em operação', idle: 'Aguardando', maintenance: 'Manutenção' }

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtItens(v: number): string {
  return v >= 1000 ? `${(v / 1000).toFixed(1)}k un` : `${v} un`
}

function fmtNum(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

function confidenceColor(c: number | null): string {
  if (c === null) return vars.color.textMuted
  if (c < 0.5) return '#ef4444'
  if (c < 0.7) return '#f59e0b'
  return vars.color.success
}

// ── Subcomponents ─────────────────────────────────────────────────────────────

/** Cartão de KPI individual */
function KpiCard({
  label, value, sub, accent = '#f1f5f9',
}: { label: string; value: string; sub?: string; accent?: string }) {
  return (
    <div style={{ background: vars.color.bgBase, border: `1px solid ${vars.color.bgSurface}`, borderRadius: 10, padding: '18px 22px' }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: vars.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: accent, fontFamily: 'monospace' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: vars.color.textMuted, marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

// ── BayCameraCard ─────────────────────────────────────────────────────────────

interface FeedInfo {
  type: 'hls' | 'demo_video'
  url: string
}

/**
 * BayCameraCard — mostra feed de câmera + dados de baia para a aba Monitoramento.
 * camera é opcional: se não houver câmera configurada para a baia, exibe placeholder.
 * Consulta /cameras/{id}/stream/info para escolher entre HLS real e vídeo demo.
 * A associação câmera ↔ baia é feita por índice de posição (cameras[i] → bays[i]).
 */
function BayCameraCard({ camera, bay, demoVideoUrl }: { camera?: Camera; bay: Bay; demoVideoUrl?: string }) {
  const [feedInfo, setFeedInfo] = useState<FeedInfo | null>(null)

  const apiBase = import.meta.env.VITE_API_URL || ''
  const hlsUrl = camera ? `${apiBase}/api/cameras/${camera.id}/stream/stream.m3u8` : ''

  // Busca tipo de feed apenas quando câmera está presente
  useEffect(() => {
    if (!camera) return
    let cancelled = false
    api.get<{ data: FeedInfo }>(`/cameras/${camera.id}/stream/info?module=fueling`)
      .then(res => { if (!cancelled && res?.data) setFeedInfo(res.data) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [camera?.id])

  const feedType = feedInfo?.type ?? 'hls'
  const feedUrl  = feedInfo?.url  ?? hlsUrl
  const statusColor = BAY_STATUS_COLORS[bay.status]
  const statusLabel = BAY_STATUS_LABELS[bay.status]

  return (
    <div style={{
      background: vars.color.bgBase,
      border: `1px solid ${bay.status === 'active' ? 'rgba(34,197,94,0.25)' : vars.color.bgSurface}`,
      borderRadius: 10,
      overflow: 'hidden',
    }}>
      {/* Cabeçalho: nome da baia + câmera (se tiver) + status */}
      <div style={{
        padding: '10px 14px', borderBottom: `1px solid ${vars.color.bgSurface}`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Video size={13} color={vars.color.textMuted} />
          <span style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9' }}>{bay.nome}</span>
          {camera && (
            <span style={{ fontSize: 11, color: vars.color.textMuted }}>{camera.name}</span>
          )}
        </div>
        <span style={{
          fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
          background: `${statusColor}22`, color: statusColor,
        }}>
          {statusLabel.toUpperCase()}
        </span>
      </div>

      {/* Feed de vídeo ou placeholder quando câmera não configurada */}
      <div style={{ aspectRatio: '16/9', background: '#020617', position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {camera ? (
          <CameraPlayer
            cameraId={camera.id}
            hlsUrl={hlsUrl}
            feedType={feedType}
            feedUrl={feedUrl}
            width={640}
            height={360}
          />
        ) : demoVideoUrl ? (
          <video
            src={demoVideoUrl}
            autoPlay
            loop
            muted
            playsInline
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <div style={{ textAlign: 'center', color: vars.color.borderStrong }}>
            <Video size={28} style={{ opacity: 0.3, marginBottom: 8 }} />
            <div style={{ fontSize: 11, fontWeight: 600 }}>Câmera não configurada</div>
          </div>
        )}
      </div>

      {/* Dados da baia abaixo do feed */}
      {bay && (
        <div style={{ padding: '12px 14px' }}>
          {bay.status === 'active' ? (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
                <div>
                  <div style={{ fontSize: 10, color: vars.color.textMuted, fontWeight: 600, textTransform: 'uppercase', marginBottom: 3 }}>Operador</div>
                  <div style={{ fontSize: 12, color: vars.color.textSecondary }}>{bay.operador ?? '—'}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: vars.color.textMuted, fontWeight: 600, textTransform: 'uppercase', marginBottom: 3 }}>Placa</div>
                  <div style={{ fontSize: 12, color: vars.color.textSecondary, fontFamily: 'monospace' }}>{bay.placa ?? '—'}</div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                <span style={{ fontSize: 10, color: vars.color.textMuted, fontWeight: 600, textTransform: 'uppercase' }}>Itens carregados</span>
                <span style={{ fontSize: 12, color: vars.color.success, fontFamily: 'monospace', fontWeight: 600 }}>
                  {fmtItens(bay.total_itens)}
                </span>
              </div>
              <div style={{ height: 5, background: vars.color.bgSurface, borderRadius: 3, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${bay.progresso}%`,
                  background: `linear-gradient(90deg, #6366f1, ${vars.color.success})`,
                  borderRadius: 3, transition: 'width 0.5s ease',
                }} />
              </div>
              <div style={{ fontSize: 10, color: vars.color.textMuted, marginTop: 3, textAlign: 'right' }}>{bay.progresso}%</div>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: '10px 0', color: vars.color.textMuted, fontSize: 12 }}>
              {bay.status === 'maintenance' ? 'Baia em manutenção' : 'Aguardando próxima operação'}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export function FuelingPage() {
  const { isSuperAdmin } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()

  // Tab ativa: lida do query param ?tab= para suportar deep-link via sidebar
  const [activeTab, setActiveTab] = useState(() => searchParams.get('tab') ?? 'dashboard')
  const [period, setPeriod] = useState<Period>('today')

  // Dashboard state
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [loadingDash, setLoadingDash] = useState(true)

  // Baias state
  const [bays, setBays] = useState<Bay[]>([])
  const [loadingBays, setLoadingBays] = useState(false)
  const [baysLoaded, setBaysLoaded] = useState(false)

  // Câmeras para o mosaico da aba Baias
  const [cameras, setCameras] = useState<Camera[]>([])
  const [camerasLoaded, setCamerasLoaded] = useState(false)

  // Demo video URL para superadmin (módulo fueling)
  const [moduleDemoUrl, setModuleDemoUrl] = useState<string | null>(null)

  // Eventos state (preserva lógica original)
  const [events, setEvents] = useState<FuelingEvent[]>([])
  const [loadingEvents, setLoadingEvents] = useState(false)
  const [eventsLoaded, setEventsLoaded] = useState(false)

  // ── Loaders ──

  const loadDashboard = useCallback(async (p: Period) => {
    setLoadingDash(true)
    try {
      const res = await api.get<any>(`/fueling/dashboard?period=${p}`)
      setDashboard(res?.data ?? res)
    } catch {
      setDashboard({ no_data: true })
    } finally {
      setLoadingDash(false)
    }
  }, [])

  const loadBays = useCallback(async () => {
    setLoadingBays(true)
    try {
      const res = await api.get<any>('/fueling/bays')
      setBays(res?.data?.bays ?? [])
      setBaysLoaded(true)
    } catch {
      setBays([])
      setBaysLoaded(true)
    } finally {
      setLoadingBays(false)
    }
  }, [])

  // Carrega câmeras para o mosaico da aba Baias
  const loadCameras = useCallback(async () => {
    if (camerasLoaded) return
    try {
      const res = await api.get<any>('/cameras')
      const list: Camera[] = res?.data?.cameras ?? res?.data ?? []
      setCameras(list.filter(c => c.is_active))
      setCamerasLoaded(true)
    } catch {
      setCamerasLoaded(true)
    }
  }, [camerasLoaded])

  // Busca vídeo demo do módulo fueling (apenas superadmin)
  useEffect(() => {
    if (!isSuperAdmin) return
    api.get<any>('/admin/demo-videos?module=fueling&per_page=1')
      .then(res => {
        const videos = res?.data?.videos ?? res?.data ?? []
        if (videos.length > 0) setModuleDemoUrl(videos[0].r2_url ?? null)
      })
      .catch(() => {})
  }, [isSuperAdmin])

  const loadEvents = useCallback(async () => {
    setLoadingEvents(true)
    try {
      const res = await api.get<any>('/fueling/events?limit=30')
      const data = res?.data ?? res
      setEvents(data?.events ?? [])
      setEventsLoaded(true)
    } catch {
      setEventsLoaded(true)
    } finally {
      setLoadingEvents(false)
    }
  }, [])

  // Carrega dashboard na montagem e quando o período muda
  useEffect(() => { loadDashboard(period) }, [period, loadDashboard])

  // Lazy-load de baias, câmeras e eventos ao trocar de aba
  useEffect(() => {
    if (activeTab === 'baias') {
      if (!baysLoaded) loadBays()
      if (!camerasLoaded) loadCameras()
    }
    if (activeTab === 'eventos' && !eventsLoaded) loadEvents()
  }, [activeTab, baysLoaded, camerasLoaded, eventsLoaded, loadBays, loadCameras, loadEvents])

  // Sincroniza activeTab com query param quando o URL muda externamente (ex: clique na sidebar)
  useEffect(() => {
    const tabFromUrl = searchParams.get('tab') ?? 'dashboard'
    if (tabFromUrl !== activeTab) setActiveTab(tabFromUrl)
  }, [searchParams]) // eslint-disable-line react-hooks/exhaustive-deps

  // Polling: dashboard a cada 60s, baias a cada 30s
  useEffect(() => {
    const interval = setInterval(() => {
      loadDashboard(period)
      if (baysLoaded) loadBays()
    }, 30000)
    return () => clearInterval(interval)
  }, [period, baysLoaded, loadDashboard, loadBays])

  const kpis = dashboard?.kpis

  // ── Styles helpers ──

  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: '8px 18px', borderRadius: 6, border: 'none',
    cursor: 'pointer', fontWeight: 600, fontSize: 13,
    background: active ? 'rgba(99,102,241,0.18)' : 'transparent',
    color: active ? '#a5b4fc' : vars.color.textMuted,
    transition: 'all 0.15s',
  })

  const periodBtnStyle = (active: boolean): React.CSSProperties => ({
    padding: '4px 12px', borderRadius: 5, border: 'none',
    cursor: 'pointer', fontSize: 12, fontWeight: 600,
    background: active ? 'rgba(99,102,241,0.2)' : 'transparent',
    color: active ? '#a5b4fc' : vars.color.textMuted,
  })

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>
      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Package size={22} style={{ color: '#f59e0b' }} />
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>
            Controle de Carregamento
          </h2>
          {isSuperAdmin && (
            <span style={{
              background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)',
              color: '#a5b4fc', borderRadius: 4, padding: '2px 8px', fontSize: 10, fontWeight: 700,
            }}>
              DEMO
            </span>
          )}
        </div>
        <button
          onClick={() => { loadDashboard(period); if (baysLoaded) loadBays(); if (eventsLoaded) loadEvents() }}
          style={{
            background: 'transparent', border: `1px solid ${vars.color.borderStrong}`, borderRadius: 6,
            color: vars.color.textSecondary, padding: '6px 12px', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 5, fontSize: 12,
          }}
        >
          <RefreshCw size={13} /> Atualizar
        </button>
      </div>

      {/* ── Tabs — sincroniza com URL param para que sidebar deep-links funcionem ── */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 24 }}>
        {[
          { key: 'dashboard', label: 'Dashboard' },
          { key: 'baias',     label: 'Monitoramento de Baias' },
          { key: 'eventos',   label: 'Eventos' },
        ].map(t => (
          <button
            key={t.key}
            style={tabStyle(activeTab === t.key)}
            onClick={() => { setActiveTab(t.key); setSearchParams({ tab: t.key }) }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ══════════════════════════════════ TAB: DASHBOARD ══════════════════════ */}
      {activeTab === 'dashboard' && (
        <div>
          {/* Seletor de período */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 24, background: vars.color.bgBase, border: `1px solid ${vars.color.bgSurface}`, borderRadius: 8, padding: 4, width: 'fit-content' }}>
            {(['today', 'week', 'month'] as Period[]).map(p => (
              <button key={p} style={periodBtnStyle(period === p)} onClick={() => setPeriod(p)}>
                {PERIOD_LABELS[p]}
              </button>
            ))}
          </div>

          {loadingDash ? (
            <LoadingSpinner />
          ) : dashboard?.no_data ? (
            /* Estado vazio para clientes sem dados */
            <div style={{ textAlign: 'center', padding: '64px 20px', color: vars.color.textMuted }}>
              <Package size={36} style={{ opacity: 0.25, marginBottom: 12 }} />
              <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: vars.color.textMuted }}>
                Nenhum dado de carregamento disponível
              </p>
              <p style={{ margin: '8px 0 0', fontSize: 13 }}>
                Configure câmeras de carregamento para visualizar métricas aqui.
              </p>
            </div>
          ) : kpis ? (
            <>
              {/* KPIs Row 1: volume, tempo, perda */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 14 }}>
                <KpiCard label="Total Carregado" value={fmtNum(kpis.total_carregado)} sub="caminhões no período" />
                <KpiCard label="Tempo Médio" value={`${kpis.tempo_medio_minutos} min`} sub="por carregamento" accent="#6366f1" />
                <KpiCard label="Itens Não Conformes" value={fmtNum(kpis.itens_nao_conformes)} sub={`${kpis.taxa_nao_conformidade}% do total`} accent="#f87171" />
                <KpiCard label="Itens Movimentados" value={fmtNum(kpis.total_itens_movimentados)} sub="unidades no período" accent={vars.color.success} />
              </div>

              {/* KPIs Row 2: NC, taxa ocupação */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 28 }}>
                <KpiCard label="Não Conformidades" value={String(kpis.eventos_nao_conformidade)} sub="eventos registrados" accent="#f59e0b" />
                <KpiCard label="Taxa de Ocupação" value={`${kpis.taxa_ocupacao_percent}%`} sub="das baias no período" accent="#6366f1" />
                <div style={{ background: vars.color.bgBase, border: `1px solid ${vars.color.bgSurface}`, borderRadius: 10, padding: '18px 22px', display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Activity size={20} color="#6366f1" />
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: vars.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Status do Módulo</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: vars.color.success, marginTop: 4 }}>● Ativo</div>
                  </div>
                </div>
              </div>

              {/* Gráficos */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
                {/* Volume Diário — LineChart */}
                <div style={{ background: vars.color.bgBase, border: `1px solid ${vars.color.bgSurface}`, borderRadius: 10, padding: '18px 20px' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: vars.color.textSecondary, marginBottom: 16 }}>Operações Diárias</div>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={dashboard.series_operacoes_diarias}>
                      <CartesianGrid strokeDasharray="3 3" stroke={vars.color.bgSurface} />
                      <XAxis dataKey="dia" tick={{ fill: vars.color.textMuted, fontSize: 10 }} />
                      <YAxis tick={{ fill: vars.color.textMuted, fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{ background: vars.color.bgBase, border: `1px solid ${vars.color.borderStrong}`, borderRadius: 6, fontSize: 12 }}
                        formatter={(v: unknown) => [`${Number(v).toLocaleString('pt-BR')} un`, 'Operações']}
                      />
                      <Line type="monotone" dataKey="operacoes" stroke="#6366f1" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Tempo por Baia — BarChart */}
                <div style={{ background: vars.color.bgBase, border: `1px solid ${vars.color.bgSurface}`, borderRadius: 10, padding: '18px 20px' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: vars.color.textSecondary, marginBottom: 16 }}>Tempo Médio por Baia (min)</div>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={dashboard.series_tempo_por_baia}>
                      <CartesianGrid strokeDasharray="3 3" stroke={vars.color.bgSurface} />
                      <XAxis dataKey="baia" tick={{ fill: vars.color.textMuted, fontSize: 10 }} />
                      <YAxis tick={{ fill: vars.color.textMuted, fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{ background: vars.color.bgBase, border: `1px solid ${vars.color.borderStrong}`, borderRadius: 6, fontSize: 12 }}
                        formatter={(v: unknown) => [`${v} min`, 'Tempo médio']}
                      />
                      <Bar dataKey="tempo" fill="#6366f1" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                {/* Causas de Perda — PieChart */}
                <div style={{ background: vars.color.bgBase, border: `1px solid ${vars.color.bgSurface}`, borderRadius: 10, padding: '18px 20px' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: vars.color.textSecondary, marginBottom: 16 }}>Causas de Não Conformidade</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <ResponsiveContainer width={160} height={160}>
                      <PieChart>
                        <Pie
                          data={dashboard.pizza_causas_perda} dataKey="value"
                          cx="50%" cy="50%" innerRadius={45} outerRadius={70}
                        >
                          {dashboard.pizza_causas_perda?.map((_, i) => (
                            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{ background: vars.color.bgBase, border: `1px solid ${vars.color.borderStrong}`, borderRadius: 6, fontSize: 12 }}
                          formatter={(v: unknown) => [`${v}%`, '']}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                    <div style={{ flex: 1 }}>
                      {dashboard.pizza_causas_perda?.map((item, i) => (
                        <div key={item.name} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                          <div style={{ width: 10, height: 10, borderRadius: 2, background: PIE_COLORS[i % PIE_COLORS.length], flexShrink: 0 }} />
                          <span style={{ fontSize: 12, color: vars.color.textSecondary, flex: 1 }}>{item.name}</span>
                          <span style={{ fontSize: 12, fontWeight: 600, color: '#f1f5f9', fontFamily: 'monospace' }}>{item.value}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Top Baias */}
                <div style={{ background: vars.color.bgBase, border: `1px solid ${vars.color.bgSurface}`, borderRadius: 10, padding: '18px 20px' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: vars.color.textSecondary, marginBottom: 16 }}>Top Baias</div>
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 11, color: vars.color.textMuted, fontWeight: 600, textTransform: 'uppercase', marginBottom: 8 }}>
                      Mais produtivas
                    </div>
                    {dashboard.top_baias_produtivas?.map((b, i) => (
                      <div key={b.baia} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontSize: 12, color: vars.color.textSecondary }}>{i + 1}. {b.baia}</span>
                        <span style={{ fontSize: 12, fontFamily: 'monospace', color: vars.color.success }}>{fmtItens(b.itens)}</span>
                      </div>
                    ))}
                  </div>
                  <div style={{ borderTop: `1px solid ${vars.color.bgSurface}`, paddingTop: 14 }}>
                    <div style={{ fontSize: 11, color: vars.color.textMuted, fontWeight: 600, textTransform: 'uppercase', marginBottom: 8 }}>
                      Maior perda
                    </div>
                    {dashboard.top_baias_perda?.map((b, i) => (
                      <div key={b.baia} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontSize: 12, color: vars.color.textSecondary }}>{i + 1}. {b.baia}</span>
                        <span style={{ fontSize: 12, fontFamily: 'monospace', color: '#f87171' }}>{fmtItens(b.perda)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </>
          ) : null}
        </div>
      )}

      {/* ══════════════════════════════════ TAB: BAIAS ══════════════════════════ */}
      {activeTab === 'baias' && (
        <div>
          {loadingBays ? (
            <LoadingSpinner />
          ) : bays.length > 0 ? (
            /* Mosaico: 3 colunas fixas no desktop → 2 linhas para as 6 baias */
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
              {bays.map((bay, idx) => (
                <BayCameraCard key={bay.id} bay={bay} camera={cameras[idx]} demoVideoUrl={moduleDemoUrl ?? undefined} />
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '64px 20px', color: vars.color.textMuted }}>
              <Gauge size={36} style={{ opacity: 0.25, marginBottom: 12 }} />
              <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: vars.color.textMuted }}>
                Nenhuma baia configurada
              </p>
              <p style={{ margin: '8px 0 0', fontSize: 13 }}>
                Configure câmeras de carregamento para monitorar as baias aqui.
              </p>
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════ TAB: EVENTOS ════════════════════════ */}
      {activeTab === 'eventos' && (
        <div>
          {loadingEvents ? (
            <LoadingSpinner />
          ) : (
            <div style={{ background: vars.color.bgBase, border: `1px solid ${vars.color.bgSurface}`, borderRadius: 10, overflow: 'hidden' }}>
              <div style={{ padding: '14px 20px', borderBottom: `1px solid ${vars.color.bgSurface}`, fontSize: 13, fontWeight: 600, color: vars.color.textSecondary }}>
                Eventos Recentes
              </div>

              {events.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '48px 20px', color: vars.color.textMuted }}>
                  <Truck size={32} style={{ opacity: 0.25, marginBottom: 10 }} />
                  <p style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Sem eventos registrados ainda</p>
                  <p style={{ margin: '6px 0 0', fontSize: 12 }}>
                    Os eventos aparecerão aqui quando câmeras de carregamento forem configuradas.
                  </p>
                </div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${vars.color.bgSurface}` }}>
                      {['Classe', 'Confiança', 'Câmera', 'Horário'].map(col => (
                        <th key={col} style={{
                          padding: '10px 20px', textAlign: 'left', fontSize: 11,
                          fontWeight: 600, color: vars.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em',
                        }}>
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((evt, idx) => (
                      <tr key={evt.id} style={{
                        borderBottom: idx < events.length - 1 ? `1px solid ${vars.color.bgBase}` : 'none',
                        background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)',
                      }}>
                        <td style={{ padding: '11px 20px', fontSize: 13, color: '#f1f5f9', fontWeight: 500 }}>
                          {CLASS_LABELS[evt.class_name] ?? evt.class_name}
                        </td>
                        <td style={{ padding: '11px 20px', fontSize: 13, fontFamily: 'monospace', color: confidenceColor(evt.confidence) }}>
                          {evt.confidence !== null ? `${Math.round(evt.confidence * 100)}%` : '—'}
                        </td>
                        <td style={{ padding: '11px 20px', fontSize: 12, color: vars.color.textMuted, fontFamily: 'monospace' }}>
                          {evt.camera_id.slice(0, 12)}
                        </td>
                        <td style={{ padding: '11px 20px', fontSize: 12, color: vars.color.textMuted }}>
                          {evt.created_at ? new Date(evt.created_at).toLocaleString('pt-BR') : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
