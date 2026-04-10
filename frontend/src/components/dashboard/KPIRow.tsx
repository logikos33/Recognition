import { useState, useCallback } from 'react'
import { Camera, ShieldCheck, AlertTriangle, Zap, Brain } from 'lucide-react'
import { api } from '../../services/api'
import { usePolling } from '../../hooks/usePolling'
import { KPICard } from './KPICard'
import { row } from './KPIRow.css'

interface DashboardStats {
  cameras_active?: number
  cameras_total?: number
  compliance_rate?: number
  alerts_today?: number
  detections_per_hour?: number
  detections_prev_hour?: number
  active_model_name?: string
  active_model_map50?: number
}

export function KPIRow() {
  const [stats, setStats] = useState<DashboardStats>({})

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
      merged.cameras_active = cams.filter((c: any) => c.stream_status === 'active' || c.is_active).length
    }

    if (statsRes.status === 'fulfilled') {
      const data = (statsRes.value as any)?.data || statsRes.value
      merged.alerts_today = data?.alerts_today ?? 0
      merged.compliance_rate = data?.compliance_rate
      merged.detections_per_hour = data?.detections_per_hour
      merged.detections_prev_hour = data?.detections_prev_hour
      merged.active_model_name = data?.active_model_name
      merged.active_model_map50 = data?.active_model_map50
    }

    setStats(merged)
  }, [])

  usePolling(load, 30000)

  const compliance = stats.compliance_rate ?? 0
  const complianceColor = compliance >= 90 ? '#10b981' : compliance >= 70 ? '#f59e0b' : '#ef4444'
  const alertsToday = stats.alerts_today ?? 0
  const dph = stats.detections_per_hour ?? 0
  const prevDph = stats.detections_prev_hour ?? 0
  const dphTrend: 'up' | 'down' | undefined = dph > prevDph ? 'up' : dph < prevDph ? 'down' : undefined

  return (
    <div className={row}>
      <KPICard
        icon={<Camera size={20} color="#22d3ee" />}
        iconBg="rgba(6, 182, 212, 0.15)"
        title="Câmeras Ativas"
        mainValue={stats.cameras_active ?? 0}
        sub={`de ${stats.cameras_total ?? 0} total`}
      />
      <KPICard
        icon={<ShieldCheck size={20} color={complianceColor} />}
        iconBg={`${complianceColor}22`}
        title="Taxa de Conformidade"
        mainValue={compliance ? `${compliance}%` : '—'}
        sub="últimas 24h"
      />
      <KPICard
        icon={<AlertTriangle size={20} color="#ef4444" />}
        iconBg="rgba(239, 68, 68, 0.15)"
        title="Alertas Hoje"
        mainValue={alertsToday}
        pulse={alertsToday > 0}
      />
      <KPICard
        icon={<Zap size={20} color="#f59e0b" />}
        iconBg="rgba(245, 158, 11, 0.15)"
        title="Detecções/Hora"
        mainValue={dph}
        trend={dphTrend}
        trendLabel={dphTrend ? `vs ${prevDph}` : undefined}
      />
      <KPICard
        icon={<Brain size={20} color="#a78bfa" />}
        iconBg="rgba(139, 92, 246, 0.15)"
        title="Modelo Ativo"
        mainValue={stats.active_model_name ?? 'YOLOv8n'}
        sub={stats.active_model_map50 ? `mAP50: ${(stats.active_model_map50 * 100).toFixed(1)}%` : 'base model'}
      />
    </div>
  )
}
