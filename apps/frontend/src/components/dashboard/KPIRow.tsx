import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, ShieldCheck, AlertTriangle, Zap, Brain } from 'lucide-react'
import { api } from '../../services/api'
import { usePolling } from '../../hooks/usePolling'
import { KPICard } from './KPICard'
import { row, drawer, drawerTitle, drawerList, drawerItem, drawerLink } from './KPIRow.css'

interface DashboardStats {
  cameras_active?: number
  cameras_total?: number
  compliance_rate?: number
  alerts_today?: number
  detections_per_hour?: number
  detections_prev_hour?: number
  active_model_name?: string
  active_model_map50?: number
  compliance_by_class?: Record<string, number>
}

interface AlertSummary {
  id: string
  camera_name?: string
  violation_type?: string
  created_at: string
}

function displayModelName(name: string): string {
  return name.replace(/yolo26n/gi, 'LGKV26n').replace(/yolo26s/gi, 'LGKV26s').replace(/yolo26m/gi, 'LGKV26m')
}

type ExpandedCard = 'alerts' | 'compliance' | null

export function KPIRow() {
  const [stats, setStats] = useState<DashboardStats>({})
  const [expanded, setExpanded] = useState<ExpandedCard>(null)
  const [recentAlerts, setRecentAlerts] = useState<AlertSummary[]>([])
  const navigate = useNavigate()

  const load = useCallback(async () => {
    const [camRes, statsRes] = await Promise.allSettled([
      api.get<{ data: { cameras: Array<{ is_active: boolean; stream_status?: string }> } }>('/cameras'),
      api.get<{ data: DashboardStats }>('/modules/epi/stats'),
    ])

    const merged: DashboardStats = {}

    if (camRes.status === 'fulfilled') {
      const data = camRes.value as any
      const cams = Array.isArray(data?.data) ? data.data : (data?.data?.cameras || data?.cameras || [])
      merged.cameras_total = cams.length
      merged.cameras_active = cams.filter((c: { stream_status?: string; is_active?: boolean }) => c.stream_status === 'active' || c.is_active).length
    }

    if (statsRes.status === 'fulfilled') {
      const data = (statsRes.value as any)?.data || statsRes.value
      merged.alerts_today = data?.alerts_today ?? 0
      merged.compliance_rate = data?.compliance_rate
      merged.detections_per_hour = data?.detections_per_hour
      merged.detections_prev_hour = data?.detections_prev_hour
      merged.active_model_name = data?.active_model_name
      merged.active_model_map50 = data?.active_model_map50
      merged.compliance_by_class = data?.compliance_by_class
    }

    setStats(merged)
  }, [])

  usePolling(load, 30000)

  // Load recent alerts when alerts drawer is opened
  useEffect(() => {
    if (expanded !== 'alerts') return
    api.get<any>('/alerts?page=1&per_page=10').then(res => {
      const data = res as any
      const list = data?.data?.alerts || data?.alerts || data?.data || []
      setRecentAlerts(Array.isArray(list) ? list.slice(0, 10) : [])
    }).catch(() => {})
  }, [expanded])

  const toggle = (card: ExpandedCard) => setExpanded(prev => prev === card ? null : card)

  const compliance = stats.compliance_rate ?? 0
  const complianceColor = compliance >= 90 ? '#10b981' : compliance >= 70 ? '#f59e0b' : '#ef4444' // allow: compliance threshold semantics
  const alertsToday = stats.alerts_today ?? 0
  const dph = stats.detections_per_hour ?? 0
  const prevDph = stats.detections_prev_hour ?? 0
  const dphTrend: 'up' | 'down' | undefined = dph > prevDph ? 'up' : dph < prevDph ? 'down' : undefined
  const modelName = displayModelName(stats.active_model_name ?? 'LGKV8n')

  const complianceByClass = stats.compliance_by_class || {}

  return (
    <div>
      <div className={row}>
        <KPICard
          icon={<Camera size={20} color={"#22d3ee" /* allow: brand cyan */} />}
          iconBg="rgba(6, 182, 212, 0.15)"
          title="Cameras Ativas"
          mainValue={stats.cameras_active ?? 0}
          sub={`de ${stats.cameras_total ?? 0} total`}
        />
        <KPICard
          icon={<ShieldCheck size={20} color={complianceColor} />}
          iconBg={`${complianceColor}22`}
          title="Taxa de Conformidade"
          mainValue={compliance ? `${compliance}%` : '—'}
          sub="ultimas 24h"
          onClick={() => toggle('compliance')}
          active={expanded === 'compliance'}
        />
        <KPICard
          icon={<AlertTriangle size={20} color={"#ef4444" /* allow: semantic danger */} />}
          iconBg="rgba(239, 68, 68, 0.15)"
          title="Alertas Hoje"
          mainValue={alertsToday}
          pulse={alertsToday > 0}
          onClick={() => toggle('alerts')}
          active={expanded === 'alerts'}
        />
        <KPICard
          icon={<Zap size={20} color={"#f59e0b" /* allow: semantic warning */} />}
          iconBg="rgba(245, 158, 11, 0.15)"
          title="Deteccoes/Hora"
          mainValue={dph}
          trend={dphTrend}
          trendLabel={dphTrend ? `vs ${prevDph}` : undefined}
        />
        <KPICard
          icon={<Brain size={20} color={"#a78bfa" /* allow: decorative accent */} />}
          iconBg="rgba(139, 92, 246, 0.15)"
          title="Modelo Ativo"
          mainValue={modelName}
          sub={stats.active_model_map50 ? `mAP50: ${(stats.active_model_map50 * 100).toFixed(1)}%` : 'base model'}
        />
      </div>

      {/* Expandable drawers */}
      {expanded === 'alerts' && (
        <div className={drawer}>
          <span className={drawerTitle}>Ultimos Alertas</span>
          {recentAlerts.length === 0 ? (
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)' }}>Nenhum alerta recente</span>
          ) : (
            <div className={drawerList}>
              {recentAlerts.map(a => (
                <div key={a.id} className={drawerItem}>
                  <span style={{ fontSize: 11, opacity: 0.5, minWidth: 50 }}>
                    {new Date(a.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span>{a.camera_name || '—'}</span>
                  <span style={{ opacity: 0.6 }}>{a.violation_type || 'violacao'}</span>
                </div>
              ))}
            </div>
          )}
          <button className={drawerLink} onClick={() => navigate('/epi/alerts')}>
            Ver todos →
          </button>
        </div>
      )}

      {expanded === 'compliance' && (
        <div className={drawer}>
          <span className={drawerTitle}>Conformidade por EPI</span>
          <div className={drawerList}>
            {Object.keys(complianceByClass).length > 0 ? (
              Object.entries(complianceByClass).map(([cls, pct]) => (
                <div key={cls} className={drawerItem}>
                  <span style={{ flex: 1, textTransform: 'capitalize' }}>{cls.replace(/_/g, ' ')}</span>
                  <span style={{ fontWeight: 700, color: (pct as number) >= 90 ? '#10b981' : (pct as number) >= 70 ? '#f59e0b' : '#ef4444' /* allow: compliance threshold */ }}>
                    {(pct as number).toFixed(1)}%
                  </span>
                </div>
              ))
            ) : (
              <>
                {['Capacete', 'Colete', 'Oculos', 'Luvas'].map(epi => (
                  <div key={epi} className={drawerItem}>
                    <span style={{ flex: 1 }}>{epi}</span>
                    <span style={{ opacity: 0.4 }}>—</span>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
