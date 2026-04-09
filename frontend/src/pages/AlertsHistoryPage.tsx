/**
 * AlertsHistoryPage — histórico de alertas com filtros, paginação e export CSV.
 */
import { useState, useEffect, useCallback } from 'react'
import { api } from '../services/api'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'

interface Violation {
  class: string
  confidence: number
}

interface Alert {
  id: string
  camera_id: string
  camera_name?: string
  violations: Violation[]
  acknowledged: boolean
  created_at: string
}

interface AlertsResponse {
  alerts: Alert[]
  total: number
  page: number
  per_page: number
  pages: number
}

const VIOLATION_LABELS: Record<string, string> = {
  no_helmet: 'Sem capacete',
  no_vest: 'Sem colete',
  no_gloves: 'Sem luvas',
  no_safety_glasses: 'Sem óculos',
  no_glasses: 'Sem óculos',
}

export function AlertsHistoryPage() {
  const [data, setData] = useState<AlertsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [ackingId, setAckingId] = useState<string | null>(null)

  const [filters, setFilters] = useState({
    camera_id: '',
    start_date: '',
    end_date: '',
    violation_type: '',
    acknowledged: '',
    page: 1,
    per_page: 20,
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
      params.set('page', String(filters.page))
      params.set('per_page', String(filters.per_page))

      const res = await api.get<any>(`/alerts?${params}`)
      const d = (res as any).data || res
      setData({
        alerts: d.alerts || [],
        total: d.total || 0,
        page: d.page || 1,
        per_page: d.per_page || 20,
        pages: d.pages || 1,
      })
    } catch (err) {
      console.error('Failed to load alerts:', err)
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => { loadAlerts() }, [loadAlerts])

  const exportCSV = async () => {
    setExporting(true)
    try {
      const token = localStorage.getItem('token')
      const apiBase = (import.meta as any).env?.VITE_API_URL || ''
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
      a.href = url
      a.download = 'alertas.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      alert('Erro ao exportar')
    } finally {
      setExporting(false)
    }
  }

  const acknowledge = async (alertId: string) => {
    setAckingId(alertId)
    try {
      await api.post(`/alerts/${alertId}/acknowledge`)
      await loadAlerts()
    } finally {
      setAckingId(null)
    }
  }

  const setFilter = (key: string, value: string) =>
    setFilters(f => ({ ...f, [key]: value, page: 1 }))

  const inp: React.CSSProperties = {
    padding: '8px 10px', borderRadius: 6, border: '1px solid #334155',
    background: '#0f172a', color: '#e2e8f0', fontSize: 13,
  }

  const btn = (bg: string): React.CSSProperties => ({
    padding: '8px 16px', borderRadius: 6, border: 'none',
    background: bg, color: '#fff', fontWeight: 600, fontSize: 13, cursor: 'pointer',
  })

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 style={{ color: '#e2e8f0', margin: 0 }}>Histórico de Alertas</h2>
        <button onClick={exportCSV} disabled={exporting} style={btn('#059669')}>
          {exporting ? 'Exportando...' : 'Exportar CSV'}
        </button>
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        <input style={inp} type="date" value={filters.start_date}
          onChange={e => setFilter('start_date', e.target.value)} placeholder="Data início" />
        <input style={inp} type="date" value={filters.end_date}
          onChange={e => setFilter('end_date', e.target.value)} placeholder="Data fim" />
        <select style={inp} value={filters.violation_type}
          onChange={e => setFilter('violation_type', e.target.value)}>
          <option value="">Todos os tipos</option>
          <option value="no_helmet">Sem capacete</option>
          <option value="no_vest">Sem colete</option>
          <option value="no_gloves">Sem luvas</option>
          <option value="no_safety_glasses">Sem óculos</option>
        </select>
        <select style={inp} value={filters.acknowledged}
          onChange={e => setFilter('acknowledged', e.target.value)}>
          <option value="">Todos os status</option>
          <option value="false">Pendente</option>
          <option value="true">Reconhecido</option>
        </select>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : !data || data.alerts.length === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#64748b', background: '#1e293b', borderRadius: 12 }}>
          Nenhum alerta encontrado
        </div>
      ) : (
        <>
          {/* Tabela */}
          <div style={{ background: '#1e293b', borderRadius: 12, overflow: 'hidden', border: '1px solid #334155' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#0f172a' }}>
                  {['Data', 'Câmera', 'Violação', 'Confiança', 'Status', 'Ação'].map(h => (
                    <th key={h} style={{ padding: '12px 16px', textAlign: 'left', color: '#64748b', fontSize: 12, fontWeight: 700 }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.alerts.map(alert => {
                  const violations = alert.violations || []
                  const mainViolation = violations[0] || {}
                  return (
                    <tr key={alert.id} style={{ borderTop: '1px solid #334155' }}>
                      <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: 13 }}>
                        {new Date(alert.created_at).toLocaleString('pt-BR')}
                      </td>
                      <td style={{ padding: '12px 16px', color: '#e2e8f0', fontSize: 13 }}>
                        {alert.camera_name || alert.camera_id?.slice(0, 8)}
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: 13 }}>
                        <span style={{ color: '#ef4444', fontWeight: 600 }}>
                          {violations.map(v => VIOLATION_LABELS[v.class] || v.class).join(', ')}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: 13 }}>
                        {mainViolation.confidence != null
                          ? `${(mainViolation.confidence * 100).toFixed(0)}%`
                          : '—'}
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: 13 }}>
                        <span style={{ color: alert.acknowledged ? '#22c55e' : '#f59e0b', fontWeight: 600 }}>
                          {alert.acknowledged ? 'Reconhecido' : 'Pendente'}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        {!alert.acknowledged && (
                          <button
                            onClick={() => acknowledge(alert.id)}
                            disabled={ackingId === alert.id}
                            style={{ ...btn('#2563eb'), padding: '4px 10px', fontSize: 12 }}
                          >
                            {ackingId === alert.id ? '...' : 'Reconhecer'}
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Paginação */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16 }}>
            <span style={{ color: '#64748b', fontSize: 13 }}>
              Total: {data.total} alertas
            </span>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button
                disabled={filters.page <= 1}
                onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}
                style={{ ...btn('#334155'), opacity: filters.page <= 1 ? 0.4 : 1 }}
              >
                ←
              </button>
              <span style={{ color: '#94a3b8', fontSize: 13 }}>
                {data.page} / {data.pages}
              </span>
              <button
                disabled={filters.page >= data.pages}
                onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}
                style={{ ...btn('#334155'), opacity: filters.page >= data.pages ? 0.4 : 1 }}
              >
                →
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
