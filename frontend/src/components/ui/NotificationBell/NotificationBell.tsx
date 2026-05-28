import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../../services/api'
import { vars } from '../../../styles/theme.css'
import {
  bellWrap,
  bellBtn,
  badge,
  panel,
  panelHeader,
  panelTitle,
  panelBody,
  alertCard,
  alertIcon,
  alertContent,
  alertCamera,
  alertViolation,
  alertTime,
  emptyPanel,
  viewAllBtn,
} from './NotificationBell.css'

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
}

const VIOLATION_LABELS: Record<string, string> = {
  no_helmet: 'Sem capacete',
  no_vest: 'Sem colete',
  no_gloves: 'Sem luvas',
  no_safety_glasses: 'Sem óculos',
  no_glasses: 'Sem óculos',
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'agora'
  if (mins < 60) return `há ${mins}min`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `há ${hrs}h`
  return `há ${Math.floor(hrs / 24)}d`
}

export function NotificationBell() {
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  const { data } = useQuery({
    queryKey: ['alerts-unack'],
    queryFn: () => api.get<{ data?: AlertsResponse } & AlertsResponse>(
      '/alerts?acknowledged=false&per_page=10&page=1'
    ),
    refetchInterval: 30000,
    staleTime: 20000,
  })

  const alerts: Alert[] = data?.data?.alerts ?? (data as AlertsResponse | undefined)?.alerts ?? []
  const count = Math.min(alerts.length, 99)

  useEffect(() => {
    if (!isOpen) return

    function handleMouseDown(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [isOpen])

  return (
    <div className={bellWrap} ref={wrapRef}>
      <button
        className={bellBtn}
        onClick={() => setIsOpen(v => !v)}
        aria-label="Notificações"
      >
        <Bell
          size={18}
          color={isOpen ? vars.color.primary : vars.color.textSecondary}
        />
        {count > 0 && (
          <span className={badge}>{count > 99 ? '99+' : count}</span>
        )}
      </button>

      {isOpen && (
        <div className={panel}>
          <div className={panelHeader}>
            <span className={panelTitle}>Notificações</span>
            <span style={{ fontSize: 11, color: vars.color.textDim }}>
              {count} pendente{count !== 1 ? 's' : ''}
            </span>
          </div>

          <div className={panelBody}>
            {alerts.length === 0 ? (
              <div className={emptyPanel}>Nenhum alerta pendente</div>
            ) : (
              alerts.map(alert => (
                <div key={alert.id} className={alertCard}>
                  <div className={alertIcon}>
                    <span style={{ color: vars.color.warning, fontSize: 14 }}>⚠</span>
                  </div>
                  <div className={alertContent}>
                    <div className={alertCamera}>
                      {alert.camera_name ?? 'Câmera'}
                    </div>
                    <div className={alertViolation}>
                      {alert.violations
                        .map(v => VIOLATION_LABELS[v.class] ?? v.class)
                        .join(', ')}
                    </div>
                    <div className={alertTime}>{timeAgo(alert.created_at)}</div>
                  </div>
                </div>
              ))
            )}
          </div>

          <button
            className={viewAllBtn}
            onClick={() => {
              navigate('/epi/alerts')
              setIsOpen(false)
            }}
          >
            Ver todos os alertas →
          </button>
        </div>
      )}
    </div>
  )
}
