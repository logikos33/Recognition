/**
 * EpiInvestigation — busca investigativa de eventos de EPI.
 *
 * Filtros: intervalo de data/hora, câmera (multi-select), classe, confiança mínima.
 * Resultado: grid de evidências com thumbnail, data, câmera, classe e confiança.
 * Timeline: densidade de eventos por hora no período selecionado.
 */
import { useState, useEffect, useCallback } from 'react'
import { api } from '../../services/api'
import { Button } from '../../components/ui/Button/Button'
import { LoadingSpinner } from '../../components/shared/LoadingSpinner'
import {
  page, pageHeader, pageTitle, pageSubtitle,
  filtersCard, filtersGrid, filterLabel, filterInput, filterSelect,
  sliderRow, slider, sliderValue, filtersActions,
  timelineCard, timelineTitle, timelineBars, timelineBar, timelineEmpty,
  resultsHeader, resultsCount,
  grid, evidenceCard, thumbnailBox, thumbnail, thumbnailPlaceholder,
  cardBody, cardCamera, cardDate, cardTags, tagViolation, tagConf,
  pagination, paginationText, paginationControls, pageNum, emptyBox,
} from './EpiInvestigation.css'
import { vars } from '../../styles/theme.css'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Violation {
  class: string
  confidence: number
}

interface EpiEvent {
  id: string
  camera_id: string
  camera_name: string
  module_code: string
  violations: Violation[]
  confidence: number
  evidence_key: string | null
  acknowledged: boolean
  created_at: string
}

interface SearchResponse {
  events: EpiEvent[]
  total: number
  page: number
  per_page: number
  pages: number
}

interface TimelineBucket {
  bucket: string
  count: number
}

interface TimelineResponse {
  timeline: TimelineBucket[]
  bucket: string
}

interface CameraOption {
  id: string
  name: string
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CLASS_LABELS: Record<string, string> = {
  no_helmet: 'Sem capacete',
  no_vest: 'Sem colete',
  no_gloves: 'Sem luvas',
  no_glasses: 'Sem óculos',
  no_safety_glasses: 'Sem óculos',
  helmet: 'Com capacete',
  vest: 'Com colete',
}

const CLASS_OPTIONS = [
  { value: 'no_helmet', label: 'Sem capacete' },
  { value: 'no_vest', label: 'Sem colete' },
  { value: 'no_gloves', label: 'Sem luvas' },
  { value: 'no_glasses', label: 'Sem óculos' },
]

function fmtLabel(cls: string): string {
  return CLASS_LABELS[cls] ?? cls
}

function fmtConf(v: number): string {
  return `${(v * 100).toFixed(0)}%`
}

function fmtDate(s: string): string {
  return new Date(s).toLocaleString('pt-BR')
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function defaultFrom(): string {
  const d = new Date()
  d.setHours(d.getHours() - 24)
  return d.toISOString().slice(0, 16)
}

function defaultTo(): string {
  return new Date().toISOString().slice(0, 16)
}

// ---------------------------------------------------------------------------
// Timeline sub-component
// ---------------------------------------------------------------------------

function Timeline({ buckets }: { buckets: TimelineBucket[] }) {
  if (!buckets.length) {
    return <div className={timelineEmpty}>Nenhum evento no período</div>
  }
  const max = Math.max(...buckets.map(b => b.count), 1)
  return (
    <div className={timelineBars} title="Densidade de eventos por hora">
      {buckets.map(b => (
        <div
          key={b.bucket}
          className={timelineBar}
          style={{ height: `${Math.round((b.count / max) * 100)}%` }}
          title={`${fmtDate(b.bucket)}: ${b.count} evento${b.count !== 1 ? 's' : ''}`}
        />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Evidence card
// ---------------------------------------------------------------------------

function EvidenceCard({
  event,
  onClick,
}: {
  event: EpiEvent
  onClick: (e: EpiEvent) => void
}) {
  const [imgUrl, setImgUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!event.evidence_key) return
    let cancelled = false
    api
      .get<{ data?: { snapshot_url: string } }>(`/alerts/${event.id}/snapshot`)
      .then(res => {
        if (!cancelled) setImgUrl(res.data?.snapshot_url ?? null)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [event.id, event.evidence_key])

  return (
    <div className={evidenceCard} onClick={() => onClick(event)}>
      <div className={thumbnailBox}>
        {imgUrl ? (
          <img src={imgUrl} alt="Evidência" className={thumbnail} loading="lazy" />
        ) : (
          <span className={thumbnailPlaceholder}>📷</span>
        )}
      </div>
      <div className={cardBody}>
        <div className={cardCamera}>{event.camera_name || event.camera_id.slice(0, 8)}</div>
        <div className={cardDate}>{fmtDate(event.created_at)}</div>
        <div className={cardTags}>
          {event.violations.map((v, i) => (
            <span key={i} className={tagViolation}>{fmtLabel(v.class)}</span>
          ))}
          <span className={tagConf}>{fmtConf(event.confidence)}</span>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Detail modal
// ---------------------------------------------------------------------------

function EventModal({
  event,
  onClose,
}: {
  event: EpiEvent
  onClose: () => void
}) {
  const [imgUrl, setImgUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!event.evidence_key) return
    api
      .get<{ data?: { snapshot_url: string } }>(`/alerts/${event.id}/snapshot`)
      .then(res => setImgUrl(res.data?.snapshot_url ?? null))
      .catch(() => {})
  }, [event.id, event.evidence_key])

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: vars.color.overlay /* TODO-WS1: converter para Modal do kit */, zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: '#1a1d23', borderRadius: '12px', maxWidth: '720px', width: '100%',
          maxHeight: '90vh', overflow: 'auto', padding: '24px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ margin: 0, color: vars.color.textPrimary, fontSize: '18px' }}>Detalhe do Evento</h3>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: vars.color.textMuted, fontSize: '20px', cursor: 'pointer' }}
          >×</button>
        </div>

        {imgUrl ? (
          <img
            src={imgUrl}
            alt="Evidência"
            style={{ width: '100%', borderRadius: '8px', marginBottom: '16px', display: 'block' }}
          />
        ) : event.evidence_key ? (
          <div style={{
            background: vars.color.bgSurface, borderRadius: '8px', padding: '40px',
            textAlign: 'center', color: vars.color.textSecondary, marginBottom: '16px',
          }}>
            Carregando imagem...
          </div>
        ) : null}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', color: vars.color.borderDefault, fontSize: '14px' }}>
          <div><strong style={{ color: vars.color.textMuted }}>Câmera:</strong> {event.camera_name || '—'}</div>
          <div><strong style={{ color: vars.color.textMuted }}>Data:</strong> {fmtDate(event.created_at)}</div>
          <div>
            <strong style={{ color: vars.color.textMuted }}>Violações:</strong>{' '}
            {event.violations.map(v => fmtLabel(v.class)).join(', ')}
          </div>
          <div>
            <strong style={{ color: vars.color.textMuted }}>Confiança:</strong>{' '}
            {event.violations[0]?.confidence != null ? fmtConf(event.violations[0].confidence) : '—'}
          </div>
          <div><strong style={{ color: vars.color.textMuted }}>Módulo:</strong> {event.module_code}</div>
          <div>
            <strong style={{ color: vars.color.textMuted }}>Status:</strong>{' '}
            {event.acknowledged ? 'Reconhecido' : 'Pendente'}
          </div>
        </div>

        {event.evidence_key && imgUrl && (
          <div style={{ marginTop: '16px' }}>
            <a
              href={imgUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#6366f1', fontSize: '13px' }}
            >
              Abrir frame original ↗
            </a>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function EpiInvestigation() {
  const [filters, setFilters] = useState({
    from: defaultFrom(),
    to: defaultTo(),
    camera_ids: '',
    classes: '',
    min_confidence: 0,
    page: 1,
    per_page: 24,
  })

  const [cameras, setCameras] = useState<CameraOption[]>([])
  const [results, setResults] = useState<SearchResponse | null>(null)
  const [timeline, setTimeline] = useState<TimelineBucket[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedEvent, setSelectedEvent] = useState<EpiEvent | null>(null)
  // Load cameras for dropdown
  useEffect(() => {
    api
      .get<{ data?: { cameras?: CameraOption[] } }>('/cameras')
      .then(res => {
        const cams = res.data?.cameras ?? (res as unknown as { cameras: CameraOption[] }).cameras ?? []
        setCameras(cams)
      })
      .catch(() => {})
  }, [])

  const search = useCallback(async (page = 1) => {
    setLoading(true)
    try {
      const p = new URLSearchParams()
      if (filters.from) p.set('from', new Date(filters.from).toISOString())
      if (filters.to) p.set('to', new Date(filters.to).toISOString())
      if (filters.camera_ids) p.set('camera_ids', filters.camera_ids)
      if (filters.classes) p.set('classes', filters.classes)
      if (filters.min_confidence > 0) p.set('min_confidence', String(filters.min_confidence / 100))
      p.set('page', String(page))
      p.set('per_page', String(filters.per_page))

      const [searchRes, timelineRes] = await Promise.all([
        api.get<{ data?: SearchResponse }>(`/events/search?${p}`),
        filters.from && filters.to
          ? api.get<{ data?: TimelineResponse }>(
              `/events/timeline?from=${new Date(filters.from).toISOString()}&to=${new Date(filters.to).toISOString()}${filters.camera_ids ? `&camera_ids=${filters.camera_ids}` : ''}${filters.classes ? `&classes=${filters.classes}` : ''}`
            )
          : Promise.resolve(null),
      ])

      const d = searchRes.data ?? (searchRes as unknown as SearchResponse)
      setResults({
        events: d.events ?? [],
        total: d.total ?? 0,
        page: d.page ?? page,
        per_page: d.per_page ?? filters.per_page,
        pages: d.pages ?? 1,
      })

      if (timelineRes) {
        const td = timelineRes.data ?? (timelineRes as unknown as TimelineResponse)
        setTimeline(td.timeline ?? [])
      }
    } catch {
      // errors handled by api.ts interceptor
    } finally {
      setLoading(false)
    }
  }, [filters])

  // Initial load
  useEffect(() => {
    search(1)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const setFilter = (key: string, value: string | number) =>
    setFilters(f => ({ ...f, [key]: value }))

  const handleSearch = () => search(1)

  const handlePageChange = (p: number) => {
    setFilters(f => ({ ...f, page: p }))
    search(p)
  }

  return (
    <div className={page}>
      <div className={pageHeader}>
        <div>
          <h2 className={pageTitle}>Investigação</h2>
          <p className={pageSubtitle}>
            Busque eventos por câmera, período, classe e confiança
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className={filtersCard}>
        <div className={filtersGrid}>
          <div>
            <label className={filterLabel}>De</label>
            <input
              className={filterInput}
              type="datetime-local"
              value={filters.from}
              onChange={e => setFilter('from', e.target.value)}
            />
          </div>
          <div>
            <label className={filterLabel}>Até</label>
            <input
              className={filterInput}
              type="datetime-local"
              value={filters.to}
              onChange={e => setFilter('to', e.target.value)}
            />
          </div>
          <div>
            <label className={filterLabel}>Câmera</label>
            <select
              className={filterSelect}
              value={filters.camera_ids}
              onChange={e => setFilter('camera_ids', e.target.value)}
            >
              <option value="">Todas as câmeras</option>
              {cameras.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={filterLabel}>Classe</label>
            <select
              className={filterSelect}
              value={filters.classes}
              onChange={e => setFilter('classes', e.target.value)}
            >
              <option value="">Todas as classes</option>
              {CLASS_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={filterLabel}>Confiança mínima: {filters.min_confidence}%</label>
            <div className={sliderRow}>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={filters.min_confidence}
                onChange={e => setFilter('min_confidence', Number(e.target.value))}
                className={slider}
              />
              <span className={sliderValue}>{filters.min_confidence}%</span>
            </div>
          </div>
        </div>

        <div className={filtersActions}>
          <Button variant="secondary" size="sm" onClick={() => {
            setFilters(f => ({
              ...f,
              from: defaultFrom(), to: defaultTo(),
              camera_ids: '', classes: '', min_confidence: 0, page: 1,
            }))
          }}>
            Limpar
          </Button>
          <Button variant="primary" size="sm" onClick={handleSearch} disabled={loading}>
            {loading ? 'Buscando...' : 'Buscar'}
          </Button>
        </div>
      </div>

      {/* Timeline */}
      <div className={timelineCard}>
        <div className={timelineTitle}>Densidade de eventos no período</div>
        {loading ? (
          <div className={timelineEmpty}><LoadingSpinner /></div>
        ) : (
          <Timeline buckets={timeline} />
        )}
      </div>

      {/* Results */}
      {loading ? (
        <LoadingSpinner />
      ) : !results || results.events.length === 0 ? (
        <div className={emptyBox}>
          Nenhum evento encontrado para os filtros selecionados
        </div>
      ) : (
        <>
          <div className={resultsHeader}>
            <span className={resultsCount}>
              {results.total} evento{results.total !== 1 ? 's' : ''} encontrado{results.total !== 1 ? 's' : ''}
            </span>
          </div>

          <div className={grid}>
            {results.events.map(ev => (
              <EvidenceCard key={ev.id} event={ev} onClick={setSelectedEvent} />
            ))}
          </div>

          <div className={pagination}>
            <span className={paginationText}>
              Página {results.page} de {results.pages}
            </span>
            <div className={paginationControls}>
              <Button
                size="sm"
                variant="secondary"
                disabled={results.page <= 1}
                onClick={() => handlePageChange(results.page - 1)}
              >←</Button>
              <span className={pageNum}>{results.page} / {results.pages}</span>
              <Button
                size="sm"
                variant="secondary"
                disabled={results.page >= results.pages}
                onClick={() => handlePageChange(results.page + 1)}
              >→</Button>
            </div>
          </div>
        </>
      )}

      {selectedEvent && (
        <EventModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />
      )}
    </div>
  )
}

export default EpiInvestigation
