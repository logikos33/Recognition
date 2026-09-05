import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, ShieldCheck, AlertTriangle, Zap, Brain } from 'lucide-react'
import { api } from '../../services/api'
import { usePolling } from '../../hooks/usePolling'
import { KPICard } from './KPICard'
import { row, drawer, drawerTitle, drawerList, drawerItem, drawerLink } from './KPIRow.css'
import { vars } from '../../styles/theme.css'

interface DashboardStats {
  cameras_active?: number
  cameras_total?: number
  compliance_rate?: number | null
  alerts_today?: number
  alerts_last_hour?: number
  alerts_prev_hour?: number
  active_model_name?: string | null
  active_model_map50?: number | null
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
      api.get<{ data?: { stats?: DashboardStats } }>('/modules/epi/stats'),
    ])

    const merged: DashboardStats = {}

    if (camRes.status === 'fulfilled') {
      const data = camRes.value as any
      const cams = Array.isArray(data?.data) ? data.data : (data?.data?.cameras || data?.cameras || [])
      merged.cameras_total = cams.length
      merged.cameras_active = cams.filter((c: { stream_status?: string; is_active?: boolean }) => c.stream_status === 'active' || c.is_active).length
    }

    if (statsRes.status === 'fulfilled') {
      // BUG-1 fix: backend devolve data.stats.{...} (modules/routes.py) —
      // leitura tolerante a payload achatado para retrocompatibilidade.
      const payload = (statsRes.value as any)?.data
      const data: DashboardStats = payload?.stats ?? payload ?? {}
      merged.alerts_today = data?.alerts_today ?? 0
      merged.compliance_rate = data?.compliance_rate
      merged.alerts_last_hour = data?.alerts_last_hour
      merged.alerts_prev_hour = data?.alerts_prev_hour
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

  const compliance = stats.compliance_rate
  const complianceColor = compliance == null ? '#a1a1aa' /* allow: neutro quando sem dado */ : compliance >= 90 ? '#10b981' : compliance >= 70 ? '#f59e0b' : '#ef4444' // allow: compliance threshold semantics
  const alertsToday = stats.alerts_today ?? 0
  const aph = stats.alerts_last_hour ?? 0
  const prevAph = stats.alerts_prev_hour ?? 0
  const aphTrend: 'up' | 'down' | undefined = aph > prevAph ? 'up' : aph < prevAph ? 'down' : undefined
  const modelName = stats.active_model_name ? displayModelName(stats.active_model_name) : '—'

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
          info="Câmeras com stream ativo em relação ao total cadastrado no módulo."
        />
        <KPICard
          icon={<ShieldCheck size={20} color={complianceColor} />}
          iconBg={`${complianceColor}22`}
          title="Taxa de Conformidade"
          mainValue={compliance != null ? `${compliance}%` : '—'}
          sub="ultimas 24h"
          onClick={() => toggle('compliance')}
          active={expanded === 'compliance'}
          info="Percentual de horas-câmera monitoradas sem violação nas últimas 24h. Fórmula: 100 × (1 − horas-câmera com violação ÷ (câmeras ativas × 24))."
        />
        <KPICard
          icon={<AlertTriangle size={20} color={"#ef4444" /* allow: semantic danger */} />}
          iconBg="rgba(239, 68, 68, 0.15)"
          title="Alertas Hoje"
          mainValue={alertsToday}
          pulse={alertsToday > 0}
          onClick={() => toggle('alerts')}
          active={expanded === 'alerts'}
          info="Total de alertas do módulo desde a meia-noite (horário do servidor)."
        />
        <KPICard
          icon={<Zap size={20} color={"#f59e0b" /* allow: semantic warning */} />}
          iconBg="rgba(245, 158, 11, 0.15)"
          title="Alertas/Hora"
          mainValue={aph}
          trend={aphTrend}
          trendLabel={aphTrend ? `vs ${prevAph}` : undefined}
          info="Alertas registrados na última hora, comparados com a hora anterior."
        />
        <KPICard
          icon={<Brain size={20} color={vars.color.primaryLight} />}
          iconBg={vars.color.primaryAlpha}
          title="Modelo Ativo"
          mainValue={modelName}
          sub={
            stats.active_model_map50
              ? `mAP50: ${(stats.active_model_map50 * 100).toFixed(1)}%`
              : stats.active_model_name
                ? 'sem métricas'
                : 'nenhum modelo ativo'
          }
          info="Modelo de detecção ativo no seu ambiente e sua precisão (mAP50) medida na validação."
        />
      </div>

      {/* Expandable drawers */}
      {expanded === 'alerts' && (
        <div className={drawer}>
          <span className={drawerTitle}>Ultimos Alertas</span>
          {recentAlerts.length === 0 ? (
            <span style={{ fontSize: 12, color: vars.color.textMuted }}>Nenhum alerta recente</span>
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
