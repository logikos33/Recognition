/**
 * AlertsHistoryPage — histórico de alertas com filtros, paginação e export CSV.
 * Filtros inicializáveis via query params (deep-link do sino de notificações):
 * ?camera_id=&acknowledged=&violation_type=&start_date=&end_date=&highlight=<alert_id>
 * &kind=violation|compliance (ADR-0063 — a tela abre em `violation`).
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams, useNavigate, NavLink } from 'react-router-dom'
import { useToast } from '../components/ui/Toast/useToast'
import { api } from '../services/api'
import { Button } from '../components/ui/Button/Button'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import {
  page, pageHeader, pageTitle, filtersRow, filterInput, emptyBox,
  tableWrapper, table, thead, th, tr, td, tdDate, tdCamera, tdViolation, tdConf,
  statusAck, statusPending, pagination, paginationText, paginationControls, pageNum,
} from './AlertsHistoryPage.css'
import { vars } from '../styles/theme.css'
import { labelForClass } from '../utils/labels'
import { ProcedenciaBadge } from '../components/shared/ProcedenciaBadge'

interface Violation { class: string; confidence: number }
interface Alert {
  id: string; camera_id: string; camera_name?: string
  violations: Violation[]; acknowledged: boolean; created_at: string
  /** Hora REAL da captura do frame (alerts.timestamp) — pode divergir de created_at. */
  timestamp?: string
  evidence_key?: string; confidence?: number
  /** ADR-0063: 'compliance' = EPI EM USO (telemetria); 'violation' = evento alertável. */
  event_kind?: 'violation' | 'compliance'
}
interface AlertsResponse {
  alerts: Alert[]; total: number; page: number; per_page: number; pages: number
}
interface AreaRate { area: string; compliance: number; violation: number }

export function AlertsHistoryPage() {
  const toast = useToast()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [data, setData] = useState<AlertsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [ackingId, setAckingId] = useState<string | null>(null)
  const hoverTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())
  // Filtros inicializados dos query params (deep-link) — depois viram estado local
  const [filters, setFilters] = useState(() => ({
    camera_id: searchParams.get('camera_id') ?? '',
    start_date: searchParams.get('start_date') ?? '',
    end_date: searchParams.get('end_date') ?? '',
    violation_type: searchParams.get('violation_type') ?? '',
    acknowledged: searchParams.get('acknowledged') ?? '',
    // ADR-0063: a tela abre em VIOLAÇÕES. EPI presente é conformidade —
    // telemetria, não alerta. O backend continua com default "todos".
    kind: searchParams.get('kind') ?? 'violation',
    page: 1, per_page: 20,
  }))
  const [areas, setAreas] = useState<AreaRate[]>([])
  // Alerta a destacar (deep-link do sino) — outline temporário + scroll
  const [highlightId, setHighlightId] = useState<string | null>(
    () => searchParams.get('highlight')
  )
  const highlightRef = useRef<HTMLTableRowElement | null>(null)

  const loadAlerts = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filters.camera_id) params.set('camera_id', filters.camera_id)
      if (filters.start_date) params.set('start_date', filters.start_date)
      if (filters.end_date) params.set('end_date', filters.end_date)
      if (filters.violation_type) params.set('violation_type', filters.violation_type)
      if (filters.acknowledged !== '') params.set('acknowledged', filters.acknowledged)
      if (filters.kind) params.set('kind', filters.kind)
      params.set('page', String(filters.page)); params.set('per_page', String(filters.per_page))
      const res = await api.get<{ data?: AlertsResponse }>(`/alerts?${params}`)
      const d = res.data || (res as unknown as AlertsResponse)
      setData({ alerts: d.alerts || [], total: d.total || 0, page: d.page || 1,
        per_page: d.per_page || 20, pages: d.pages || 1 })
    } catch (err) { console.error('Failed to load alerts:', err) }
    finally { setLoading(false) }
  }, [filters])

  useEffect(() => { loadAlerts() }, [loadAlerts])

  // Taxa de uso por área — só faz sentido (e só é buscada) na aba de
  // conformidade, que é justamente onde "EPI presente" vira número útil.
  useEffect(() => {
    if (filters.kind !== 'compliance') return
    const p = new URLSearchParams()
    if (filters.start_date) p.set('start_date', filters.start_date)
    if (filters.end_date) p.set('end_date', filters.end_date)
    api.get<{ data?: { areas: AreaRate[] } }>(`/alerts/usage-rate?${p}`)
      .then(r => setAreas(r.data?.areas ?? []))
      .catch(() => setAreas([]))
  }, [filters.kind, filters.start_date, filters.end_date])

  // Deep-link: rola até o alerta destacado e remove o destaque após alguns segundos
  useEffect(() => {
    if (!highlightId || !data) return
    const el = highlightRef.current
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const timer = setTimeout(() => setHighlightId(null), 4000)
    return () => clearTimeout(timer)
  }, [data, highlightId])

  const exportCSV = async () => {
    setExporting(true)
    try {
      const params = new URLSearchParams()
      if (filters.camera_id) params.set('camera_id', filters.camera_id)
      if (filters.start_date) params.set('start_date', filters.start_date)
      if (filters.end_date) params.set('end_date', filters.end_date)
      if (filters.violation_type) params.set('violation_type', filters.violation_type)
      // O CSV sai com o mesmo recorte que está na tela (ADR-0063).
      if (filters.kind) params.set('kind', filters.kind)
      const blob = await api.downloadBlob(`/alerts/export?${params}`)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'alertas.csv'; a.click(); URL.revokeObjectURL(url)
    } catch { toast.error('Erro ao exportar') }
    finally { setExporting(false) }
  }

  const acknowledge = async (alertId: string) => {
    setAckingId(alertId)
    try { await api.post(`/alerts/${alertId}/acknowledge`); await loadAlerts() }
    finally { setAckingId(null) }
  }

  const setFilter = (key: string, value: string) =>
    setFilters(f => ({ ...f, [key]: value, page: 1 }))

  return (
    <div className={page}>
      <div className={pageHeader}>
        <h2 className={pageTitle}>
          {filters.kind === 'compliance' ? 'Conformidade — EPI em uso'
            : filters.kind === 'violation' ? 'Violações de EPI'
              : 'Histórico de Eventos'}
        </h2>
        <Button variant="success" size="sm" onClick={exportCSV} disabled={exporting}>
          {exporting ? 'Exportando...' : 'Exportar CSV'}
        </Button>
      </div>

      <div className={filtersRow}>
        <select
          className={filterInput}
          aria-label="Tipo de evento"
          value={filters.kind}
          onChange={e => setFilter('kind', e.target.value)}
        >
          <option value="violation">Violações</option>
          <option value="compliance">Conformidade (EPI em uso)</option>
          <option value="">Todos os eventos</option>
        </select>
        <input
          className={filterInput}
          type="text"
          placeholder="ID da câmera"
          aria-label="Filtrar por câmera"
          value={filters.camera_id}
          onChange={e => setFilter('camera_id', e.target.value)}
        />
        <input className={filterInput} type="date" value={filters.start_date} onChange={e => setFilter('start_date', e.target.value)} />
        <input className={filterInput} type="date" value={filters.end_date} onChange={e => setFilter('end_date', e.target.value)} />
        <select className={filterInput} value={filters.violation_type} onChange={e => setFilter('violation_type', e.target.value)}>
          <option value="">Todos os tipos</option>
          <option value="no_helmet">Sem capacete</option>
          <option value="no_vest">Sem colete</option>
          <option value="no_gloves">Sem luvas</option>
          <option value="no_safety_glasses">Sem óculos</option>
        </select>
        <select className={filterInput} value={filters.acknowledged} onChange={e => setFilter('acknowledged', e.target.value)}>
          <option value="">Todos os status</option>
          <option value="false">Pendente</option>
          <option value="true">Reconhecido</option>
        </select>
      </div>

      {/* Painel de taxa de uso — o consumidor útil de "EPI presente".
          Área = cameras.location (a câmera é a proxy de área hoje). */}
      {filters.kind === 'compliance' && areas.length > 0 && (
        <div className={tableWrapper} style={{ marginBottom: '16px' }}>
          <table className={table}>
            <thead className={thead}>
              <tr>{['Área', 'EPI em uso', 'Violações', 'Taxa de uso'].map(h => (
                <th key={h} className={th}>{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {areas.map(a => {
                const total = a.compliance + a.violation
                return (
                  <tr key={a.area} className={tr}>
                    <td className={td}>{a.area}</td>
                    <td className={td}>{a.compliance}</td>
                    <td className={td}>{a.violation}</td>
                    <td className={tdConf}>
                      {total ? `${Math.round((a.compliance / total) * 100)}%` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {loading ? <LoadingSpinner /> : !data || data.alerts.length === 0 ? (
        <div className={emptyBox}>Nenhum alerta encontrado</div>
      ) : (
        <>
          <div className={tableWrapper}>
            <table className={table}>
              <thead className={thead}>
                {/* "Evento", não "Violação": a coluna também mostra
                    conformidade quando o filtro pede (ADR-0063). */}
                <tr>{['Data', 'Câmera', 'Evento', 'Confiança', 'Status', 'Ação'].map(h => (
                  <th key={h} className={th}>{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {data.alerts.map(alert => {
                  const v0 = alert.violations?.[0]
                  const startHoverAck = () => {
                    if (alert.acknowledged || hoverTimers.current.has(alert.id)) return
                    const timer = setTimeout(() => {
                      hoverTimers.current.delete(alert.id)
                      acknowledge(alert.id)
                    }, 1000)
                    hoverTimers.current.set(alert.id, timer)
                  }
                  const cancelHoverAck = () => {
                    const timer = hoverTimers.current.get(alert.id)
                    if (timer) { clearTimeout(timer); hoverTimers.current.delete(alert.id) }
                  }
                  const isHighlighted = alert.id === highlightId
                  return (
                    <tr
                      key={alert.id}
                      ref={isHighlighted ? highlightRef : undefined}
                      className={tr}
                      onClick={() => navigate(`/epi/alerts/${alert.id}`)}
                      onMouseEnter={startHoverAck}
                      onMouseLeave={cancelHoverAck}
                      style={{
                        cursor: 'pointer',
                        ...(isHighlighted
                          ? { outline: `2px solid ${vars.color.primary}`, outlineOffset: '-2px' }
                          : {}),
                      }}
                    >
                      <td className={tdDate}>
                        {new Date(alert.timestamp ?? alert.created_at).toLocaleString('pt-BR')}{' '}
                        <ProcedenciaBadge capturadoEm={alert.timestamp} gravadoEm={alert.created_at} />
                      </td>
                      <td className={tdCamera}>
                        {/* Link real (não só onClick na <tr>): teclado e
                            "copiar endereço do link" saem de graça. */}
                        <NavLink to={`/epi/alerts/${alert.id}`} style={{ color: 'inherit' }}>
                          {alert.camera_name || alert.camera_id?.slice(0, 8)}
                        </NavLink>
                      </td>
                      <td className={tdViolation}>
                        {alert.event_kind === 'compliance' && (
                          <span
                            title="EPI em uso — conformidade, não violação"
                            style={{ color: vars.color.success, marginRight: '6px' }}
                          >✓</span>
                        )}
                        {alert.violations.map(v => labelForClass(v.class)).join(', ')}
                      </td>
                      <td className={tdConf}>{v0?.confidence != null ? `${(v0.confidence * 100).toFixed(0)}%` : '—'}</td>
                      <td className={td}>
                        <span className={alert.acknowledged ? statusAck : statusPending}>
                          {alert.acknowledged ? 'Reconhecido' : 'Pendente'}
                        </span>
                      </td>
                      <td className={td}>
                        {!alert.acknowledged && (
                          <Button size="sm" variant="primary" onClick={e => { e.stopPropagation(); acknowledge(alert.id) }} disabled={ackingId === alert.id}>
                            {ackingId === alert.id ? '...' : 'Reconhecer'}
                          </Button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className={pagination}>
            <span className={paginationText}>Total: {data.total} alertas</span>
            <div className={paginationControls}>
              <Button size="sm" variant="secondary" disabled={filters.page <= 1}
                onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}>←</Button>
              <span className={pageNum}>{data.page} / {data.pages}</span>
              <Button size="sm" variant="secondary" disabled={filters.page >= data.pages}
                onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}>→</Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
