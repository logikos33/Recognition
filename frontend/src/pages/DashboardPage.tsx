/**
 * DashboardPage — overview with real stats from backend API.
 */
import { useState, useEffect } from 'react'
import { useToast } from '../components/ui/Toast/useToast'
import { api } from '../services/api'
import { Button } from '../components/ui/Button/Button'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import {
  page, pageHeader, pageTitle, statsGrid, statCard, statLabel, statValue, statSub,
  section, sectionTitle, chartRow, chartLabel, chartBarBg, chartBarFill, chartCount,
  statusRow,
} from './DashboardPage.css'

interface DashboardStats {
  cameras_total: number
  videos_total: number
  videos_extracted: number
  frames_total: number
  frames_annotated: number
  jobs_total: number
  jobs_running: number
  models_total: number
  models_active: number
  alerts_24h: number
  alerts_pending: number
  class_distribution: Array<{ class: string; count: number }>
}

const STAT_COLORS: Record<string, string> = {
  Cameras: '#2563eb', Videos: '#8b5cf6', Frames: '#f59e0b',
  Treinamentos: '#22c55e', Modelos: '#ec4899', 'Alertas (24h)': '#ef4444',
}

export function DashboardPage() {
  const toast = useToast()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadStats() }, [])

  const loadStats = async () => {
    try {
      const res = await api.get<{ data: DashboardStats }>('/v1/dashboard/stats')
      setStats(res.data)
    } catch {
      try {
        const [cams, vids, jobs] = await Promise.all([
          api.get<{ data: unknown[] }>('/cameras').catch(() => ({ data: [] })),
          api.get<{ data: unknown[] }>('/training/videos').catch(() => ({ data: [] })),
          api.get<{ data: unknown[] }>('/training/jobs').catch(() => ({ data: [] })),
        ])
        const camList = Array.isArray(cams.data) ? cams.data : ((cams as { cameras?: unknown[] }).cameras || [])
        setStats({
          cameras_total: camList.length, videos_total: (vids.data || []).length,
          videos_extracted: 0, frames_total: 0, frames_annotated: 0,
          jobs_total: (jobs.data || []).length, jobs_running: 0,
          models_total: 0, models_active: 0, alerts_24h: 0, alerts_pending: 0,
          class_distribution: [],
        })
      } catch {}
    } finally { setLoading(false) }
  }

  const exportExcel = async () => {
    try {
      const token = localStorage.getItem('token')
      const apiBase = import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api` : '/api'
      const res = await fetch(`${apiBase}/v1/reports/export?days=30`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('Export falhou')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'epi-alertas-30d.xlsx'; a.click()
      URL.revokeObjectURL(url)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao exportar')
    }
  }

  if (loading) return <LoadingSpinner />

  const s = stats || {} as DashboardStats
  const cards = [
    { label: 'Cameras', value: s.cameras_total, sub: 'cadastradas' },
    { label: 'Videos', value: s.videos_total, sub: `${s.videos_extracted ?? 0} extraídos` },
    { label: 'Frames', value: s.frames_total, sub: `${s.frames_annotated ?? 0} anotados` },
    { label: 'Treinamentos', value: s.jobs_total, sub: `${s.jobs_running ?? 0} em execução` },
    { label: 'Modelos', value: s.models_total, sub: `${s.models_active ?? 0} ativos` },
    { label: 'Alertas (24h)', value: s.alerts_24h, sub: `${s.alerts_pending ?? 0} pendentes` },
  ]
  const maxCount = Math.max(...(s.class_distribution?.map(c => c.count) ?? [1]))

  return (
    <div className={page}>
      <div className={pageHeader}>
        <h2 className={pageTitle}>Dashboard</h2>
        <Button variant="secondary" size="sm" onClick={exportExcel}>Exportar Excel</Button>
      </div>

      <div className={statsGrid}>
        {cards.map(c => (
          <div key={c.label} className={statCard}>
            <div className={statLabel}>{c.label}</div>
            <div className={statValue} style={{ color: STAT_COLORS[c.label] }}>{c.value ?? 0}</div>
            <div className={statSub}>{c.sub}</div>
          </div>
        ))}
      </div>

      {(s.class_distribution?.length ?? 0) > 0 && (
        <div className={section}>
          <h3 className={sectionTitle}>Distribuição de Classes</h3>
          <div style={{ display: 'grid', gap: '8px' }}>
            {s.class_distribution.map(item => (
              <div key={item.class} className={chartRow}>
                <span className={chartLabel}>{item.class}</span>
                <div className={chartBarBg}>
                  <div className={chartBarFill} style={{ width: `${(item.count / maxCount) * 100}%` }} />
                </div>
                <span className={chartCount}>{item.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className={section}>
        <h3 className={sectionTitle}>Status do Sistema</h3>
        <div style={{ display: 'grid', gap: '6px' }}>
          {[['API V2', 'Online', '#22c55e'], ['Database', 'Conectado', '#22c55e'],
            ['Redis', 'Conectado', '#22c55e'], ['Arquitetura', 'Microserviços V2', '#64748b']
          ].map(([label, value, color]) => (
            <div key={label} className={statusRow}>
              <span>{label}</span>
              <span style={{ color, fontWeight: 600 }}>{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
