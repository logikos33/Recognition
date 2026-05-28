/**
 * Painel de alertas em tempo real por câmera.
 * Usa o api client centralizado e getToken() — padrão do projeto.
 */
import { useEffect, useState } from 'react'
import { api, getToken } from '../../services/api'
import type { Alert } from '../../types'
import { Button } from '../ui/Button/Button'
import { empty, list, alertRow, alertBody, violationText, timestampText } from './AlertsPanel.css'

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
    return <div className={empty}>Nenhum alerta registrado.</div>
  }

  return (
    <div className={list}>
      {alerts.map(alert => (
        <div key={alert.id} className={alertRow({ acknowledged: alert.acknowledged })}>
          <div className={alertBody}>
            <span className={violationText}>
              {alert.violations
                .filter(v => v.class.startsWith('no_'))
                .map(v => v.class)
                .join(', ')}
            </span>
            <span className={timestampText}>
              {new Date(alert.timestamp).toLocaleTimeString('pt-BR')}
            </span>
          </div>
          {!alert.acknowledged && (
            <Button variant="secondary" size="sm" onClick={() => acknowledge(alert.id)}>
              OK
            </Button>
          )}
        </div>
      ))}
    </div>
  )
}
