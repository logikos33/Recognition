/**
 * AlertsHistoryPage — histórico de alertas com filtros, paginação e export CSV.
 */
import { useState, useEffect, useCallback } from 'react'
import toast from 'react-hot-toast'
import { api } from '../services/api'
import { Button } from '../components/ui/Button/Button'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import {
  page, pageHeader, pageTitle, filtersRow, filterInput, emptyBox,
  tableWrapper, table, thead, th, tr, td, tdDate, tdCamera, tdViolation, tdConf,
  statusAck, statusPending, pagination, paginationText, paginationControls, pageNum,
} from './AlertsHistoryPage.css'

interface Violation { class: string; confidence: number }
interface Alert {
  id: string; camera_id: string; camera_name?: string
  violations: Violation[]; acknowledged: boolean; created_at: string
}
interface AlertsResponse {
  alerts: Alert[]; total: number; page: number; per_page: number; pages: number
}

const VIOLATION_LABELS: Record<string, string> = {
  no_helmet: 'Sem capacete', no_vest: 'Sem colete',
  no_gloves: 'Sem luvas', no_safety_glasses: 'Sem óculos', no_glasses: 'Sem óculos',
}

export function AlertsHistoryPage() {
  const [data, setData] = useState<AlertsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [ackingId, setAckingId] = useState<string | null>(null)
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
      const token = localStorage.getItem('token')
      const apiBase = import.meta.env.VITE_API_URL || ''
      const params = new URLSearchParams()
      if (filters.camera_id) params.set('camera_id', filters.camera_id)
      if (filters.start_date) params.set('start_date', filters.start_date)
      if (filters.end_date) params.set('end_date', filters.end_date)
      if (filters.violation_type) params.set('violation_type', filters.violation_type)
      const res = await fetch(`${apiBase}/api/alerts/export?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const blob = await res.blob()
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
                  return (
                    <tr key={alert.id} className={tr}>
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
    </div>
  )
}
