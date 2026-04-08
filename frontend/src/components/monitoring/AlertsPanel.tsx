/**
 * Painel de alertas em tempo real por câmera.
 * Usa o api client centralizado e getToken() — padrão do projeto.
 */
import { useEffect, useState } from 'react'
import { api, getToken } from '../../services/api'
import type { Alert } from '../../types'

interface AlertsPanelProps {
  cameraId: string
  maxAlerts?: number
}

export function AlertsPanel({ cameraId, maxAlerts = 10 }: AlertsPanelProps) {
  const [alerts, setAlerts] = useState<Alert[]>([])

  useEffect(() => {
    if (!getToken()) return

    api.get<{ success: boolean; data: Alert[] }>(
      `/cameras/${cameraId}/alerts?limit=${maxAlerts}`
    )
      .then(d => {
        if (d.success && Array.isArray(d.data)) setAlerts(d.data)
      })
      .catch(() => {})
  }, [cameraId, maxAlerts])

  const acknowledge = async (alertId: string) => {
    if (!getToken()) return
    try {
      await api.post(`/alerts/${alertId}/acknowledge`)
      setAlerts(prev =>
        prev.map(a => (a.id === alertId ? { ...a, acknowledged: true } : a))
      )
    } catch {
      // silently ignore — UI state unchanged on error
    }
  }

  if (alerts.length === 0) {
    return (
      <div style={{ padding: '16px', color: '#6b7280', fontSize: '14px' }}>
        Nenhum alerta registrado.
      </div>
    )
  }

  return (
    <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
      {alerts.map(alert => (
        <div
          key={alert.id}
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid #374151',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            background: alert.acknowledged ? 'transparent' : '#1f2937',
          }}
        >
          <div>
            <div style={{ color: '#f87171', fontSize: '13px', fontWeight: 500 }}>
              {alert.violations
                .filter(v => v.class.startsWith('no_'))
                .map(v => v.class)
                .join(', ')}
            </div>
            <div style={{ color: '#9ca3af', fontSize: '12px', marginTop: 2 }}>
              {new Date(alert.timestamp).toLocaleTimeString('pt-BR')}
            </div>
          </div>
          {!alert.acknowledged && (
            <button
              onClick={() => acknowledge(alert.id)}
              style={{
                background: '#374151',
                color: '#d1d5db',
                border: 'none',
                borderRadius: '4px',
                padding: '4px 8px',
                fontSize: '11px',
                cursor: 'pointer',
              }}
            >
              OK
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
