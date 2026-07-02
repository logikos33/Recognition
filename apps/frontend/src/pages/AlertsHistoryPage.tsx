/**
 * AlertsHistoryPage — histórico de alertas com filtros, paginação e export CSV.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
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

interface Violation { class: string; confidence: number }
interface Alert {
  id: string; camera_id: string; camera_name?: string
  violations: Violation[]; acknowledged: boolean; created_at: string
  evidence_key?: string; confidence?: number
}
interface AlertsResponse {
  alerts: Alert[]; total: number; page: number; per_page: number; pages: number
}

const VIOLATION_LABELS: Record<string, string> = {
  no_helmet: 'Sem capacete', no_vest: 'Sem colete',
  no_gloves: 'Sem luvas', no_safety_glasses: 'Sem óculos', no_glasses: 'Sem óculos',
}

export function AlertsHistoryPage() {
  const toast = useToast()
  const [data, setData] = useState<AlertsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [ackingId, setAckingId] = useState<string | null>(null)
  const hoverTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null)
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null)
  const [filters, setFilters] = useState({
    camera_id: '', start_date: '', end_date: '', violation_type: '', acknowledged: '',
    page: 1, per_page: 20,
  })

  const loadAlerts = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filters.camera_id) params.set('camera_id', filters.camera_id)
      if (filters.start_date) params.set('start_date', filters.start_date)
      if (filters.end_date) params.set('end_date', filters.end_date)
      if (filters.violation_type) params.set('violation_type', filters.violation_type)
      if (filters.acknowledged !== '') params.set('acknowledged', filters.acknowledged)
      params.set('page', String(filters.page)); params.set('per_page', String(filters.per_page))
      const res = await api.get<{ data?: AlertsResponse }>(`/alerts?${params}`)
      const d = res.data || (res as unknown as AlertsResponse)
      setData({ alerts: d.alerts || [], total: d.total || 0, page: d.page || 1,
        per_page: d.per_page || 20, pages: d.pages || 1 })
    } catch (err) { console.error('Failed to load alerts:', err) }
    finally { setLoading(false) }
  }, [filters])

  useEffect(() => { loadAlerts() }, [loadAlerts])

  const exportCSV = async () => {
    setExporting(true)
    try {
      const params = new URLSearchParams()
      if (filters.camera_id) params.set('camera_id', filters.camera_id)
      if (filters.start_date) params.set('start_date', filters.start_date)
      if (filters.end_date) params.set('end_date', filters.end_date)
      if (filters.violation_type) params.set('violation_type', filters.violation_type)
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

  const openAlert = async (alert: Alert) => {
    setSelectedAlert(alert)
    setSnapshotUrl(null)
    if (alert.evidence_key) {
      try {
        const res = await api.get<{ data?: { snapshot_url: string } }>(`/alerts/${alert.id}/snapshot`)
        setSnapshotUrl(res.data?.snapshot_url || null)
      } catch { /* no snapshot */ }
    }
  }

  const setFilter = (key: string, value: string) =>
    setFilters(f => ({ ...f, [key]: value, page: 1 }))

  return (
    <div className={page}>
      <div className={pageHeader}>
        <h2 className={pageTitle}>Histórico de Alertas</h2>
        <Button variant="success" size="sm" onClick={exportCSV} disabled={exporting}>
          {exporting ? 'Exportando...' : 'Exportar CSV'}
        </Button>
      </div>

      <div className={filtersRow}>
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

      {loading ? <LoadingSpinner /> : !data || data.alerts.length === 0 ? (
        <div className={emptyBox}>Nenhum alerta encontrado</div>
      ) : (
        <>
          <div className={tableWrapper}>
            <table className={table}>
              <thead className={thead}>
                <tr>{['Data', 'Câmera', 'Violação', 'Confiança', 'Status', 'Ação'].map(h => (
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
                  return (
                    <tr
                      key={alert.id}
                      className={tr}
                      onClick={() => openAlert(alert)}
                      onMouseEnter={startHoverAck}
                      onMouseLeave={cancelHoverAck}
                      style={{ cursor: 'pointer' }}
                    >
                      <td className={tdDate}>{new Date(alert.created_at).toLocaleString('pt-BR')}</td>
                      <td className={tdCamera}>{alert.camera_name || alert.camera_id?.slice(0, 8)}</td>
                      <td className={tdViolation}>
                        {alert.violations.map(v => VIOLATION_LABELS[v.class] || v.class).join(', ')}
                      </td>
                      <td className={tdConf}>{v0?.confidence != null ? `${(v0.confidence * 100).toFixed(0)}%` : '—'}</td>
                      <td className={td}>
                        <span className={alert.acknowledged ? statusAck : statusPending}>
                          {alert.acknowledged ? 'Reconhecido' : 'Pendente'}
                        </span>
                      </td>
                      <td className={td}>
                        {!alert.acknowledged && (
                          <Button size="sm" variant="primary" onClick={() => acknowledge(alert.id)} disabled={ackingId === alert.id}>
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
      {/* Alert Detail Modal */}
      {selectedAlert && (
        <div
          onClick={() => setSelectedAlert(null)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000,
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
              <h3 style={{ margin: 0, color: vars.color.textPrimary, fontSize: '18px' }}>Detalhe do Alerta</h3>
              <button onClick={() => setSelectedAlert(null)} style={{ background: 'none', border: 'none', color: vars.color.textMuted, fontSize: '20px', cursor: 'pointer' }}>×</button>
            </div>

            {/* Snapshot with bounding boxes */}
            {snapshotUrl ? (
              <div style={{ position: 'relative', marginBottom: '16px', borderRadius: '8px', overflow: 'hidden' }}>
                <img src={snapshotUrl} alt="Evidência" style={{ width: '100%', display: 'block' }} />
                {selectedAlert.violations.map((v, i) => (
                  <div
                    key={i}
                    style={{
                      position: 'absolute',
                      left: '20%', top: '15%', width: '25%', height: '50%',
                      border: '3px solid #ef4444',
                      borderRadius: '4px',
                      animation: 'pulse 2s infinite',
                    }}
                  >
                    <span style={{
                      position: 'absolute', top: '-22px', left: '-2px',
                      background: '#ef4444', color: vars.color.textPrimary, fontSize: '11px',
                      padding: '2px 6px', borderRadius: '3px', whiteSpace: 'nowrap',
                    }}>
                      {VIOLATION_LABELS[v.class] || v.class} — {(v.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            ) : selectedAlert.evidence_key ? (
              <div style={{ background: vars.color.bgSurface, borderRadius: '8px', padding: '40px', textAlign: 'center', color: vars.color.textSecondary, marginBottom: '16px' }}>
                Carregando imagem...
              </div>
            ) : null}

            {/* Alert info */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', color: vars.color.borderDefault, fontSize: '14px' }}>
              <div><strong style={{ color: vars.color.textMuted }}>Câmera:</strong> {selectedAlert.camera_name || '—'}</div>
              <div><strong style={{ color: vars.color.textMuted }}>Data:</strong> {new Date(selectedAlert.created_at).toLocaleString('pt-BR')}</div>
              <div><strong style={{ color: vars.color.textMuted }}>Violações:</strong> {selectedAlert.violations.map(v => VIOLATION_LABELS[v.class] || v.class).join(', ')}</div>
              <div><strong style={{ color: vars.color.textMuted }}>Confiança:</strong> {selectedAlert.violations[0]?.confidence != null ? `${(selectedAlert.violations[0].confidence * 100).toFixed(0)}%` : '—'}</div>
              <div><strong style={{ color: vars.color.textMuted }}>Status:</strong> {selectedAlert.acknowledged ? 'Reconhecido' : 'Pendente'}</div>
            </div>

            {!selectedAlert.acknowledged && (
              <div style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
                <Button variant="primary" size="sm" onClick={() => { acknowledge(selectedAlert.id); setSelectedAlert(null) }}>
                  Reconhecer
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
