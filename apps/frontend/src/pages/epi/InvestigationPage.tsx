/**
 * InvestigationPage — busca investigativa de eventos (task-049, refeita no WS4).
 *
 * Layout:
 *   ┌─────────────────────────────────────────┐
 *   │  Filtros (módulo, classe, câmera, ...)  │
 *   ├─────────────────────────────────────────┤
 *   │  Timeline (BarChart recharts)           │
 *   ├─────────────────────────────────────────┤
 *   │  Lista de eventos (thumbnail + detalhe) │
 *   └─────────────────────────────────────────┘
 *
 * Usa api.ts para todas as chamadas — api.ts JÁ prefixa '/api', então os
 * paths daqui começam em '/v1/...' (NUNCA '/api/v1/...', que duplicaria o
 * prefixo e cairia no catch-all SPA do backend).
 * O envelope retornado é { success, data } — acessamos sempre res.data.
 * Containers/modal/badges via UI kit (WS1) — zero cor hardcoded.
 */
import { useState, useEffect, useCallback, type CSSProperties, type ReactNode } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip, ResponsiveContainer,
} from 'recharts'
import { ChevronDown, HelpCircle, Search } from 'lucide-react'
import { api } from '../../services/api'
import { vars } from '../../styles/theme.css'
import { useModules } from '../../hooks/useModules'
import { moduleService, type ModuleClass } from '../../services/moduleService'
import { PageHeader } from '../../components/ui/PageHeader/PageHeader'
import { Panel } from '../../components/ui/Panel/Panel'
import { Modal } from '../../components/ui/Modal/Modal'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import { Badge, type BadgeVariant } from '../../components/ui/Badge/Badge'
import { Input } from '../../components/ui/Input/Input'
import { Button } from '../../components/ui/Button/Button'
import { Tooltip } from '../../components/ui/Tooltip/Tooltip'
import { Popover } from '../../components/ui/Popover/Popover'
import { Banner } from '../../components/ui/Banner/Banner'

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

interface EventViolation {
  class: string
  confidence: number
}

interface EventItem {
  id: string
  camera_id: string | null
  camera_name?: string | null
  module_code: string | null
  confidence: number | null
  violations: EventViolation[]
  evidence_key: string | null
  created_at: string | null
  frame_url: string | null
  is_demo?: boolean
}

interface SearchResult {
  events: EventItem[]
  total: number
  page: number
  per_page: number
  pages: number
}

interface TimelineBucket {
  bucket: string | null
  count: number
}

interface TimelineResult {
  timeline: TimelineBucket[]
  bucket: string
}

interface ApiEnvelope<T> {
  success: boolean
  data: T
  error?: string
}

interface CameraOption {
  id: string
  name: string
}

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

/** Fallback estático quando módulo = 'Todos' (sem classes do backend). */
const FALLBACK_CLASS_OPTIONS = [
  'no_helmet', 'helmet', 'no_vest', 'vest',
  'no_gloves', 'gloves', 'no_glasses', 'glasses',
  'plate', 'truck', 'fuel_nozzle',
]

const BUCKET_OPTIONS = [
  { value: 'hour', label: 'Por hora' },
  { value: 'day',  label: 'Por dia' },
  { value: 'week', label: 'Por semana' },
]

const MODULE_LABELS: Record<string, string> = {
  epi: 'EPI',
  fueling: 'Abastecimento',
  quality: 'Qualidade',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildQs(params: Record<string, string | string[]>): string {
  const parts: string[] = []
  for (const [key, val] of Object.entries(params)) {
    if (Array.isArray(val)) {
      val.forEach((v) => parts.push(`${encodeURIComponent(key + '[]')}=${encodeURIComponent(v)}`))
    } else if (val !== '') {
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(val)}`)
    }
  }
  return parts.length ? '?' + parts.join('&') : ''
}

/** Formata Date para o value de <input type="datetime-local"> (hora local). */
function toLocalInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** Default do período: últimos 7 dias (a timeline exige from/to). */
function defaultFrom(): string {
  return toLocalInputValue(new Date(Date.now() - 7 * 24 * 3600 * 1000))
}

function defaultTo(): string {
  return toLocalInputValue(new Date())
}

function formatBucketLabel(bucket: string | null, size: string): string {
  if (!bucket) return ''
  try {
    const d = new Date(bucket)
    if (size === 'hour')  return d.toLocaleString('pt-BR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    if (size === 'week')  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' })
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  } catch {
    return bucket
  }
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('pt-BR')
  } catch {
    return iso
  }
}

// ---------------------------------------------------------------------------
// Sub-componentes
// ---------------------------------------------------------------------------

/** Rótulo de filtro com tooltip explicativo (Contrato de Operabilidade). */
function FilterLabel({ text, tip }: { text: string; tip: string }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: '0.75rem', color: vars.color.textSecondary,
    }}>
      {text}
      <Tooltip label={tip}>
        <HelpCircle size={12} style={{ color: vars.color.textMuted, cursor: 'help' }} aria-label={`Ajuda: ${text}`} />
      </Tooltip>
    </span>
  )
}

const selectStyle: CSSProperties = {
  padding: '8px 10px',
  background: vars.color.bgSurface,
  color: vars.color.textPrimary,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: 6,
  fontSize: '0.875rem',
  width: '100%',
  boxSizing: 'border-box',
}

const fieldColStyle: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
}

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------

export function InvestigationPage() {
  const { modules } = useModules()

  // --- Filtros ---
  const [selectedClasses, setSelectedClasses]     = useState<string[]>([])
  const [moduleCode, setModuleCode]               = useState('')
  const [moduleClasses, setModuleClasses]         = useState<ModuleClass[]>([])
  const [cameras, setCameras]                     = useState<CameraOption[]>([])
  const [selectedCameraIds, setSelectedCameraIds] = useState<string[]>([])
  const [fromDate, setFromDate]                   = useState(defaultFrom)
  const [toDate, setToDate]                       = useState(defaultTo)
  const [minConfidencePct, setMinConfidencePct]   = useState('')
  const [bucket, setBucket]                       = useState('hour')
  const [page, setPage]                           = useState(1)

  // --- Estado de dados ---
  const [events, setEvents]           = useState<EventItem[]>([])
  const [total, setTotal]             = useState(0)
  const [pages, setPages]             = useState(1)
  const [timelineBuckets, setTimelineBuckets] = useState<TimelineBucket[]>([])
  const [loadingList, setLoadingList] = useState(false)
  const [loadingChart, setLoadingChart] = useState(false)
  const [errorMsg, setErrorMsg]       = useState<string | null>(null)

  // --- Preview de frame selecionado ---
  const [selectedFrame, setSelectedFrame] = useState<EventItem | null>(null)

  const dateError = fromDate && toDate && fromDate > toDate
    ? 'Data inicial após a final'
    : undefined

  // --- Câmeras do tenant (filtro portado da antiga página órfã de investigação) ---
  useEffect(() => {
    api.get<ApiEnvelope<{ cameras?: CameraOption[] }>>('/cameras')
      .then((res) => setCameras(res.data?.cameras ?? []))
      .catch(() => setCameras([]))
  }, [])

  // --- Classes do módulo selecionado (display_name pt-BR do backend) ---
  useEffect(() => {
    setSelectedClasses([])
    if (!moduleCode) {
      setModuleClasses([])
      return
    }
    let cancelled = false
    moduleService.getClasses(moduleCode)
      .then((classes) => { if (!cancelled) setModuleClasses(classes) })
      .catch(() => { if (!cancelled) setModuleClasses([]) })
    return () => { cancelled = true }
  }, [moduleCode])

  // --- Construir query params comuns (from/to SEMPRE presentes) ---
  const commonParams = useCallback((): Record<string, string | string[]> => {
    const p: Record<string, string | string[]> = {}
    if (selectedClasses.length) p['class_name'] = selectedClasses
    if (selectedCameraIds.length) p['camera_id'] = selectedCameraIds
    if (moduleCode) p['module_code'] = moduleCode
    p['from'] = (fromDate || defaultFrom()) + ':00'
    p['to']   = (toDate   || defaultTo())   + ':00'
    const pct = Number(minConfidencePct)
    if (minConfidencePct !== '' && !Number.isNaN(pct)) {
      p['min_confidence'] = String(Math.min(100, Math.max(0, pct)) / 100)
    }
    return p
  }, [selectedClasses, selectedCameraIds, moduleCode, fromDate, toDate, minConfidencePct])

  // --- Fetch da lista de eventos ---
  const fetchEvents = useCallback(async (pg: number) => {
    setLoadingList(true)
    setErrorMsg(null)
    try {
      const qs = buildQs({ ...commonParams(), page: String(pg), per_page: '20' })
      const res = await api.get<ApiEnvelope<SearchResult>>(`/v1/events/search${qs}`)
      if (res.success) {
        setEvents(res.data.events ?? [])
        setTotal(res.data.total ?? 0)
        setPages(res.data.pages ?? 1)
      } else {
        setErrorMsg(res.error ?? 'Erro ao buscar eventos')
      }
    } catch {
      setErrorMsg('Não foi possível conectar à API')
    } finally {
      setLoadingList(false)
    }
  }, [commonParams])

  // --- Fetch da timeline ---
  const fetchTimeline = useCallback(async () => {
    setLoadingChart(true)
    try {
      const qs = buildQs({ ...commonParams(), bucket })
      const res = await api.get<ApiEnvelope<TimelineResult>>(`/v1/events/timeline${qs}`)
      if (res.success) {
        setTimelineBuckets(res.data.timeline ?? [])
      }
    } catch {
      // timeline é best-effort; não bloqueia a lista
    } finally {
      setLoadingChart(false)
    }
  }, [commonParams, bucket])

  // Busca inicial e ao mudar filtros (bloqueia apenas se o período for inválido)
  useEffect(() => {
    if (dateError) return
    setPage(1)
    fetchEvents(1)
    fetchTimeline()
  }, [fetchEvents, fetchTimeline, dateError])

  // Mudança de página
  const handlePageChange = (p: number) => {
    setPage(p)
    fetchEvents(p)
  }

  // Toggle de classe
  const toggleClass = (cls: string) => {
    setSelectedClasses((prev) =>
      prev.includes(cls) ? prev.filter((c) => c !== cls) : [...prev, cls]
    )
  }

  // Toggle de câmera
  const toggleCamera = (id: string) => {
    setSelectedCameraIds((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    )
  }

  const clearFilters = () => {
    setSelectedClasses([])
    setSelectedCameraIds([])
    setModuleCode('')
    setFromDate(defaultFrom())
    setToDate(defaultTo())
    setMinConfidencePct('')
  }

  // Chips de classe: do módulo selecionado (backend) ou fallback estático
  const classChips: { name: string; label: string; isViolation: boolean }[] =
    moduleCode && moduleClasses.length > 0
      ? moduleClasses.map((c) => ({
          name: c.class_name,
          label: c.display_name || c.class_name,
          isViolation: c.is_violation,
        }))
      : FALLBACK_CLASS_OPTIONS.map((n) => ({
          name: n,
          label: n,
          isViolation: n.startsWith('no_'),
        }))

  const violationInfo = (cls: string): { label: string; variant: BadgeVariant } => {
    const known = moduleClasses.find((c) => c.class_name === cls)
    if (known) {
      return {
        label: known.display_name || cls,
        variant: known.is_violation ? 'danger' : 'success',
      }
    }
    return { label: cls, variant: cls.startsWith('no_') ? 'danger' : 'success' }
  }

  // Timeline data formatada para recharts
  const chartData = timelineBuckets.map((b) => ({
    name: formatBucketLabel(b.bucket, bucket),
    count: b.count,
  }))

  const hasActiveFilters =
    selectedClasses.length > 0 || selectedCameraIds.length > 0 ||
    moduleCode !== '' || minConfidencePct !== ''

  const renderViolationBadges = (ev: EventItem): ReactNode => (
    <>
      {(ev.violations ?? []).map((v, idx) => {
        const info = violationInfo(v.class)
        return (
          <Badge key={`${v.class}-${idx}`} variant={info.variant}>
            {info.label} · {Math.round((v.confidence ?? 0) * 100)}%
          </Badge>
        )
      })}
    </>
  )

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <PageHeader
        title="Investigação de Eventos"
        subtitle="Busque e analise eventos de todos os módulos ativos"
      />

      {/* Filtros */}
      <Panel title="Filtros" variant="card">
        {/* Classes de detecção */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 6 }}>
            <FilterLabel
              text="Classe de detecção"
              tip="Filtra por classe detectada pela IA (ex.: sem capacete). Selecione um módulo para ver os nomes traduzidos."
            />
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {classChips.map((cls) => (
              <button
                key={cls.name}
                onClick={() => toggleClass(cls.name)}
                style={{
                  padding: '3px 10px',
                  borderRadius: 12,
                  border: '1px solid',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  background: selectedClasses.includes(cls.name) ? vars.color.primaryDark : vars.color.bgSurface,
                  color: selectedClasses.includes(cls.name) ? vars.color.textOnPrimary : vars.color.textPrimary,
                  borderColor: selectedClasses.includes(cls.name) ? vars.color.primaryDark : vars.color.borderDefault,
                }}
              >
                {cls.label}
              </button>
            ))}
          </div>
        </div>

        {/* Linha de campos */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12 }}>
          <div style={fieldColStyle}>
            <FilterLabel
              text="Módulo"
              tip="Mostra só eventos do módulo escolhido. A lista vem dos módulos ativos do seu ambiente."
            />
            <select
              value={moduleCode}
              onChange={(e) => setModuleCode(e.target.value)}
              style={selectStyle}
              aria-label="Módulo"
            >
              <option value="">Todos</option>
              {modules.map((m) => (
                <option key={m.module_code} value={m.module_code}>
                  {MODULE_LABELS[m.module_code] ?? m.module_code}
                </option>
              ))}
            </select>
          </div>

          <div style={fieldColStyle}>
            <FilterLabel
              text="Câmeras"
              tip="Restringe a busca a câmeras específicas. Sem seleção, todas as câmeras entram no resultado."
            />
            <Popover
              trigger={
                <Button variant="secondary" size="md" style={{ justifyContent: 'space-between', width: '100%' }}>
                  {selectedCameraIds.length > 0 ? `Câmeras (${selectedCameraIds.length})` : 'Todas as câmeras'}
                  <ChevronDown size={14} />
                </Button>
              }
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 220, maxHeight: 240, overflowY: 'auto' }}>
                {cameras.length === 0 ? (
                  <span style={{ fontSize: '0.8rem', color: vars.color.textMuted, padding: '4px 2px' }}>
                    Nenhuma câmera cadastrada
                  </span>
                ) : (
                  cameras.map((cam) => (
                    <label
                      key={cam.id}
                      style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.8rem', color: vars.color.textPrimary, cursor: 'pointer' }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedCameraIds.includes(cam.id)}
                        onChange={() => toggleCamera(cam.id)}
                      />
                      {cam.name}
                    </label>
                  ))
                )}
              </div>
            </Popover>
          </div>

          <div style={fieldColStyle}>
            <FilterLabel
              text="De"
              tip="Início do período de busca. Por padrão, os últimos 7 dias."
            />
            <Input
              type="datetime-local"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              error={dateError}
              aria-label="Data inicial"
            />
          </div>

          <div style={fieldColStyle}>
            <FilterLabel
              text="Até"
              tip="Fim do período de busca. Por padrão, agora."
            />
            <Input
              type="datetime-local"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              aria-label="Data final"
            />
          </div>

          <div style={fieldColStyle}>
            <FilterLabel
              text="Confiança mín. (%)"
              tip="Confiança mínima da detecção — valores altos mostram só eventos mais certos."
            />
            <Input
              type="number"
              min={0}
              max={100}
              step={5}
              placeholder="ex.: 70"
              value={minConfidencePct}
              onChange={(e) => setMinConfidencePct(e.target.value)}
              aria-label="Confiança mínima em porcentagem"
            />
          </div>

          <div style={fieldColStyle}>
            <FilterLabel
              text="Agrupamento"
              tip="Agrupa o gráfico por período. Para 'Por semana', amplie o período para ver mais barras."
            />
            <select
              value={bucket}
              onChange={(e) => setBucket(e.target.value)}
              style={selectStyle}
              aria-label="Agrupamento do gráfico"
            >
              {BUCKET_OPTIONS.map((b) => (
                <option key={b.value} value={b.value}>{b.label}</option>
              ))}
            </select>
          </div>
        </div>

        {dateError && (
          <p style={{ margin: '8px 0 0', fontSize: '0.75rem', color: vars.color.danger }}>
            {dateError}
          </p>
        )}

        {hasActiveFilters && (
          <div style={{ marginTop: 10 }}>
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Limpar filtros
            </Button>
          </div>
        )}
      </Panel>

      {/* Erro */}
      {errorMsg && (
        <Banner variant="danger" onDismiss={() => setErrorMsg(null)}>
          {errorMsg}
        </Banner>
      )}

      {/* Timeline chart */}
      <Panel
        title="Volume de eventos"
        variant="card"
        actions={
          <span style={{ fontSize: '0.75rem', color: vars.color.textMuted }}>
            {loadingChart ? 'Carregando…' : `${timelineBuckets.length} períodos`}
          </span>
        }
      >
        {chartData.length === 0 && !loadingChart ? (
          <div style={{ height: 160, display: 'flex', alignItems: 'center', justifyContent: 'center', color: vars.color.textMuted, fontSize: '0.875rem' }}>
            Nenhum dado para o período selecionado
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={vars.color.borderDefault} />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: vars.color.textSecondary }} />
              <YAxis tick={{ fontSize: 11, fill: vars.color.textSecondary }} allowDecimals={false} />
              <ChartTooltip
                contentStyle={{ fontSize: '0.75rem', borderRadius: 6 }}
                formatter={(v) => [v ?? 0, 'Eventos']}
              />
              <Bar dataKey="count" fill={vars.color.primaryDark} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Panel>

      {/* Lista de eventos */}
      <Panel
        title={
          <>
            Eventos{' '}
            {total > 0 && (
              <span style={{ color: vars.color.textSecondary, fontWeight: 400 }}>({total} total)</span>
            )}
          </>
        }
        variant="card"
        padding="none"
        actions={loadingList ? (
          <span style={{ fontSize: '0.75rem', color: vars.color.textMuted }}>Buscando…</span>
        ) : undefined}
      >
        {events.length === 0 && !loadingList ? (
          <EmptyState
            icon={<Search size={28} />}
            title="Nenhum evento encontrado"
            description="Ajuste os filtros ou amplie o período de busca."
          />
        ) : (
          <div>
            {events.map((ev) => (
              <div
                key={ev.id}
                style={{
                  display: 'flex',
                  gap: 12,
                  alignItems: 'flex-start',
                  padding: '12px 16px',
                  borderBottom: `1px solid ${vars.color.borderDefault}`,
                  cursor: ev.frame_url ? 'pointer' : 'default',
                  background: selectedFrame?.id === ev.id ? vars.color.primaryAlpha : 'transparent',
                }}
                onClick={() => setSelectedFrame(ev.frame_url ? ev : null)}
              >
                {/* Thumbnail */}
                <div style={{
                  width: 72,
                  height: 48,
                  background: vars.color.bgSurface,
                  borderRadius: 4,
                  flexShrink: 0,
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  {ev.frame_url ? (
                    <img
                      src={ev.frame_url}
                      alt="frame"
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none'
                      }}
                    />
                  ) : (
                    <span style={{ fontSize: '0.625rem', color: vars.color.textMuted }}>sem frame</span>
                  )}
                </div>

                {/* Detalhes */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 4 }}>
                    {renderViolationBadges(ev)}
                    {ev.is_demo && <Badge variant="accent">Demo</Badge>}
                    {ev.module_code && (
                      <span style={{ fontSize: '0.7rem', color: vars.color.textSecondary, marginLeft: 'auto' }}>
                        {MODULE_LABELS[ev.module_code] ?? ev.module_code}
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 16, fontSize: '0.75rem', color: vars.color.textSecondary, flexWrap: 'wrap' }}>
                    <span>{formatDateTime(ev.created_at)}</span>
                    {ev.camera_name && <span>{ev.camera_name}</span>}
                    {ev.confidence !== null && (
                      <span>{Math.round(ev.confidence * 100)}% confiança</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Paginação */}
        {pages > 1 && (
          <div style={{ padding: '12px 16px', display: 'flex', gap: 8, justifyContent: 'center', alignItems: 'center', borderTop: `1px solid ${vars.color.borderDefault}` }}>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handlePageChange(page - 1)}
              disabled={page <= 1}
            >
              Anterior
            </Button>
            <span style={{ padding: '4px 8px', fontSize: '0.75rem', color: vars.color.textSecondary }}>
              {page} / {pages}
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handlePageChange(page + 1)}
              disabled={page >= pages}
            >
              Próxima
            </Button>
          </div>
        )}
      </Panel>

      {/* Modal de frame ampliado (Modal do kit — WS1) */}
      <Modal
        open={Boolean(selectedFrame?.frame_url)}
        onClose={() => setSelectedFrame(null)}
        title={selectedFrame ? formatDateTime(selectedFrame.created_at) : 'Evento'}
        maxWidth="880px"
      >
        {selectedFrame?.frame_url && (
          <div>
            <img
              src={selectedFrame.frame_url}
              alt="frame ampliado"
              style={{ maxWidth: '100%', maxHeight: '65vh', objectFit: 'contain', borderRadius: 4 }}
            />
            <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {renderViolationBadges(selectedFrame)}
              {selectedFrame.is_demo && <Badge variant="accent">Demo</Badge>}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default InvestigationPage
