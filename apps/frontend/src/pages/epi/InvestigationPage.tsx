/**
 * InvestigationPage — busca investigativa de eventos (task-049).
 *
 * Layout:
 *   ┌─────────────────────────────────────────┐
 *   │  Filtros (class, período, confiança)    │
 *   ├─────────────────────────────────────────┤
 *   │  Timeline (BarChart recharts)           │
 *   ├─────────────────────────────────────────┤
 *   │  Lista de eventos (thumbnail + detalhe) │
 *   └─────────────────────────────────────────┘
 *
 * Usa api.ts para todas as chamadas (não fetch raw).
 * O envelope retornado é { success, data } — acessamos sempre res.data.
 */
import { useState, useEffect, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { api } from '../../services/api'
import { vars } from '../../styles/theme.css'

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

interface EventItem {
  id: string
  camera_id: string | null
  module_code: string | null
  confidence: number | null
  violations: string[]
  evidence_key: string | null
  created_at: string | null
  frame_url: string | null
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
  buckets: TimelineBucket[]
  bucket_size: string
}

interface ApiEnvelope<T> {
  success: boolean
  data: T
  error?: string
}

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

const CLASS_OPTIONS = [
  'no_helmet', 'helmet', 'no_vest', 'vest',
  'no_gloves', 'gloves', 'no_glasses', 'glasses',
  'plate', 'truck', 'fuel_nozzle',
]

const BUCKET_OPTIONS = [
  { value: 'hour', label: 'Por hora' },
  { value: 'day',  label: 'Por dia' },
  { value: 'week', label: 'Por semana' },
]

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
// Componente
// ---------------------------------------------------------------------------

export function InvestigationPage() {
  // --- Filtros ---
  const [selectedClasses, setSelectedClasses] = useState<string[]>([])
  const [moduleCode, setModuleCode]           = useState('')
  const [fromDate, setFromDate]               = useState('')
  const [toDate, setToDate]                   = useState('')
  const [minConfidence, setMinConfidence]     = useState('')
  const [bucket, setBucket]                   = useState('hour')
  const [page, setPage]                       = useState(1)

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

  // --- Construir query params comuns ---
  const commonParams = useCallback((): Record<string, string | string[]> => {
    const p: Record<string, string | string[]> = {}
    if (selectedClasses.length) p['class_name'] = selectedClasses
    if (moduleCode) p['module_code'] = moduleCode
    if (fromDate) p['from'] = fromDate + ':00'
    if (toDate)   p['to']   = toDate   + ':00'
    if (minConfidence) p['min_confidence'] = minConfidence
    return p
  }, [selectedClasses, moduleCode, fromDate, toDate, minConfidence])

  // --- Fetch da lista de eventos ---
  const fetchEvents = useCallback(async (pg: number) => {
    setLoadingList(true)
    setErrorMsg(null)
    try {
      const qs = buildQs({ ...commonParams(), page: String(pg), per_page: '20' })
      const res = await api.get<ApiEnvelope<SearchResult>>(`/api/v1/events/search${qs}`)
      if (res.success) {
        setEvents(res.data.events)
        setTotal(res.data.total)
        setPages(res.data.pages)
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
      const res = await api.get<ApiEnvelope<TimelineResult>>(`/api/v1/events/timeline${qs}`)
      if (res.success) {
        setTimelineBuckets(res.data.buckets)
      }
    } catch {
      // timeline é best-effort; não bloqueia a lista
    } finally {
      setLoadingChart(false)
    }
  }, [commonParams, bucket])

  // Busca inicial e ao mudar filtros
  useEffect(() => {
    setPage(1)
    fetchEvents(1)
    fetchTimeline()
  }, [fetchEvents, fetchTimeline])

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

  // Timeline data formatada para recharts
  const chartData = timelineBuckets.map((b) => ({
    name: formatBucketLabel(b.bucket, bucket),
    count: b.count,
  }))

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Cabeçalho */}
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '4px' }}>
        Investigação de Eventos
      </h1>
      <p style={{ color: vars.color.textSecondary, marginBottom: '24px', fontSize: '0.875rem' }}>
        Busque e analise eventos de todos os módulos ativos
      </p>

      {/* Filtros */}
      <div style={{
        background: vars.color.bgCard,
        border: `1px solid ${vars.color.borderDefault}`,
        borderRadius: '8px',
        padding: '16px',
        marginBottom: '20px',
      }}>
        <h2 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '12px', color: vars.color.textPrimary }}>
          Filtros
        </h2>

        {/* Classes de violação */}
        <div style={{ marginBottom: '12px' }}>
          <span style={{ fontSize: '0.75rem', color: vars.color.textSecondary, display: 'block', marginBottom: '6px' }}>
            Classe de detecção
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {CLASS_OPTIONS.map((cls) => (
              <button
                key={cls}
                onClick={() => toggleClass(cls)}
                style={{
                  padding: '3px 10px',
                  borderRadius: '12px',
                  border: '1px solid',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  background: selectedClasses.includes(cls) ? vars.color.primaryDark : vars.color.bgSurface,
                  color: selectedClasses.includes(cls) ? vars.color.textOnPrimary : vars.color.textPrimary,
                  borderColor: selectedClasses.includes(cls) ? vars.color.primaryDark : vars.color.borderDefault,
                }}
              >
                {cls}
              </button>
            ))}
          </div>
        </div>

        {/* Linha de campos */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.75rem', color: vars.color.textSecondary }}>Módulo</span>
            <select
              value={moduleCode}
              onChange={(e) => setModuleCode(e.target.value)}
              style={{ padding: '6px 8px', border: `1px solid ${vars.color.borderDefault}`, borderRadius: '6px', fontSize: '0.875rem' }}
            >
              <option value="">Todos</option>
              <option value="epi">EPI</option>
              <option value="fueling">Fueling</option>
              <option value="quality">Quality</option>
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.75rem', color: vars.color.textSecondary }}>De</span>
            <input
              type="datetime-local"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              style={{ padding: '6px 8px', border: `1px solid ${vars.color.borderDefault}`, borderRadius: '6px', fontSize: '0.875rem' }}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.75rem', color: vars.color.textSecondary }}>Até</span>
            <input
              type="datetime-local"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              style={{ padding: '6px 8px', border: `1px solid ${vars.color.borderDefault}`, borderRadius: '6px', fontSize: '0.875rem' }}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.75rem', color: vars.color.textSecondary }}>Confiança mín.</span>
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              placeholder="0.0 – 1.0"
              value={minConfidence}
              onChange={(e) => setMinConfidence(e.target.value)}
              style={{ padding: '6px 8px', border: `1px solid ${vars.color.borderDefault}`, borderRadius: '6px', fontSize: '0.875rem' }}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.75rem', color: vars.color.textSecondary }}>Agrupamento</span>
            <select
              value={bucket}
              onChange={(e) => setBucket(e.target.value)}
              style={{ padding: '6px 8px', border: `1px solid ${vars.color.borderDefault}`, borderRadius: '6px', fontSize: '0.875rem' }}
            >
              {BUCKET_OPTIONS.map((b) => (
                <option key={b.value} value={b.value}>{b.label}</option>
              ))}
            </select>
          </label>
        </div>

        {selectedClasses.length > 0 && (
          <button
            onClick={() => setSelectedClasses([])}
            style={{ marginTop: '8px', fontSize: '0.75rem', color: vars.color.textSecondary, background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
          >
            Limpar filtros de classe
          </button>
        )}
      </div>

      {/* Erro */}
      {errorMsg && (
        <div style={{ background: vars.color.dangerMuted, border: '1px solid #fca5a5', borderRadius: '6px', padding: '12px', marginBottom: '16px', color: vars.color.danger, fontSize: '0.875rem' }}>
          {errorMsg}
        </div>
      )}

      {/* Timeline chart */}
      <div style={{
        background: vars.color.bgCard,
        border: `1px solid ${vars.color.borderDefault}`,
        borderRadius: '8px',
        padding: '16px',
        marginBottom: '20px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h2 style={{ fontSize: '0.875rem', fontWeight: 600, color: vars.color.textPrimary }}>
            Volume de eventos
          </h2>
          <span style={{ fontSize: '0.75rem', color: vars.color.textMuted }}>
            {loadingChart ? 'Carregando…' : `${timelineBuckets.length} períodos`}
          </span>
        </div>
        {chartData.length === 0 && !loadingChart ? (
          <div style={{ height: '160px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: vars.color.textMuted, fontSize: '0.875rem' }}>
            Nenhum dado para o período selecionado
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={vars.color.borderDefault} />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: vars.color.textSecondary }} />
              <YAxis tick={{ fontSize: 11, fill: vars.color.textSecondary }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ fontSize: '0.75rem', borderRadius: '6px' }}
                formatter={(v) => [v ?? 0, 'Eventos']}
              />
              <Bar dataKey="count" fill={vars.color.primaryDark} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Lista de eventos */}
      <div style={{
        background: vars.color.bgCard,
        border: `1px solid ${vars.color.borderDefault}`,
        borderRadius: '8px',
        overflow: 'hidden',
      }}>
        <div style={{ padding: '12px 16px', borderBottom: `1px solid ${vars.color.borderDefault}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ fontSize: '0.875rem', fontWeight: 600, color: vars.color.textPrimary }}>
            Eventos {total > 0 && <span style={{ color: vars.color.textSecondary, fontWeight: 400 }}>({total} total)</span>}
          </h2>
          {loadingList && <span style={{ fontSize: '0.75rem', color: vars.color.textMuted }}>Buscando…</span>}
        </div>

        {events.length === 0 && !loadingList ? (
          <div style={{ padding: '40px', textAlign: 'center', color: vars.color.textMuted, fontSize: '0.875rem' }}>
            Nenhum evento encontrado para os filtros aplicados
          </div>
        ) : (
          <div>
            {events.map((ev) => (
              <div
                key={ev.id}
                style={{
                  display: 'flex',
                  gap: '12px',
                  alignItems: 'flex-start',
                  padding: '12px 16px',
                  borderBottom: `1px solid ${vars.color.borderDefault}`,
                  cursor: ev.frame_url ? 'pointer' : 'default',
                  background: selectedFrame?.id === ev.id ? vars.color.primaryAlpha : 'transparent',
                }}
                onClick={() => setSelectedFrame(ev.frame_url ? (selectedFrame?.id === ev.id ? null : ev) : null)}
              >
                {/* Thumbnail */}
                <div style={{
                  width: '72px',
                  height: '48px',
                  background: vars.color.bgSurface,
                  borderRadius: '4px',
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
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '4px' }}>
                    {ev.violations.map((v) => (
                      <span
                        key={v}
                        style={{
                          padding: '1px 8px',
                          borderRadius: '10px',
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          background: v.startsWith('no_') ? vars.color.dangerMuted : vars.color.successMuted,
                          color: v.startsWith('no_') ? '#991b1b' : '#166534',
                        }}
                      >
                        {v}
                      </span>
                    ))}
                    {ev.module_code && (
                      <span style={{ fontSize: '0.7rem', color: vars.color.textSecondary, marginLeft: 'auto' }}>
                        {ev.module_code}
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: '16px', fontSize: '0.75rem', color: vars.color.textSecondary }}>
                    <span>{formatDateTime(ev.created_at)}</span>
                    {ev.confidence !== null && (
                      <span>
                        {Math.round(ev.confidence * 100)}% confiança
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Paginação */}
        {pages > 1 && (
          <div style={{ padding: '12px 16px', display: 'flex', gap: '8px', justifyContent: 'center', borderTop: `1px solid ${vars.color.borderDefault}` }}>
            <button
              onClick={() => handlePageChange(page - 1)}
              disabled={page <= 1}
              style={{
                padding: '4px 12px',
                borderRadius: '4px',
                border: `1px solid ${vars.color.borderDefault}`,
                fontSize: '0.75rem',
                cursor: page <= 1 ? 'not-allowed' : 'pointer',
                background: page <= 1 ? vars.color.bgSurface : vars.color.bgCard,
                color: page <= 1 ? vars.color.textMuted : vars.color.textPrimary,
              }}
            >
              Anterior
            </button>
            <span style={{ padding: '4px 8px', fontSize: '0.75rem', color: vars.color.textSecondary }}>
              {page} / {pages}
            </span>
            <button
              onClick={() => handlePageChange(page + 1)}
              disabled={page >= pages}
              style={{
                padding: '4px 12px',
                borderRadius: '4px',
                border: `1px solid ${vars.color.borderDefault}`,
                fontSize: '0.75rem',
                cursor: page >= pages ? 'not-allowed' : 'pointer',
                background: page >= pages ? vars.color.bgSurface : vars.color.bgCard,
                color: page >= pages ? vars.color.textMuted : vars.color.textPrimary,
              }}
            >
              Próxima
            </button>
          </div>
        )}
      </div>

      {/* Modal de frame ampliado */}
      {selectedFrame?.frame_url && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setSelectedFrame(null)}
        >
          <div
            style={{ background: vars.color.bgCard, borderRadius: '8px', padding: '16px', maxWidth: '90vw', maxHeight: '90vh' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                {formatDateTime(selectedFrame.created_at)}
              </span>
              <button
                onClick={() => setSelectedFrame(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.25rem', color: vars.color.textSecondary }}
              >
                ✕
              </button>
            </div>
            <img
              src={selectedFrame.frame_url}
              alt="frame ampliado"
              style={{ maxWidth: '80vw', maxHeight: '70vh', objectFit: 'contain', borderRadius: '4px' }}
            />
            <div style={{ marginTop: '8px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {selectedFrame.violations.map((v) => (
                <span key={v} style={{
                  padding: '2px 10px', borderRadius: '10px', fontSize: '0.75rem', fontWeight: 600,
                  background: v.startsWith('no_') ? vars.color.dangerMuted : vars.color.successMuted,
                  color: v.startsWith('no_') ? '#991b1b' : '#166534',
                }}>{v}</span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default InvestigationPage
