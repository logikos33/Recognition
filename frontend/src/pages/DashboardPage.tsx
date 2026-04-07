/**
 * DashboardPage — overview with real stats from backend API.
 */
import { useState, useEffect } from 'react'
import { api } from '../services/api'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'

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

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      const res = await api.get<any>('/v1/dashboard/stats')
      setStats(res.data)
    } catch {
      // Fallback: try old endpoints
      try {
        const [cams, vids, jobs] = await Promise.all([
          api.get<any>('/cameras').catch(() => ({ data: [] })),
          api.get<any>('/training/videos').catch(() => ({ data: [] })),
          api.get<any>('/training/jobs').catch(() => ({ data: [] })),
        ])
        setStats({
          cameras_total: (cams.data || []).length,
          videos_total: (vids.data || []).length,
          videos_extracted: 0,
          frames_total: 0, frames_annotated: 0,
          jobs_total: (jobs.data || []).length, jobs_running: 0,
          models_total: 0, models_active: 0,
          alerts_24h: 0, alerts_pending: 0,
          class_distribution: [],
        })
      } catch {}
    } finally {
      setLoading(false)
    }
  }

  const exportExcel = async () => {
    try {
      const token = localStorage.getItem('token')
      const apiBase = (import.meta as any).env?.VITE_API_URL
        ? `${(import.meta as any).env.VITE_API_URL}/api`
        : '/api'
      const res = await fetch(`${apiBase}/v1/reports/export?days=30`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('Export failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'epi-alertas-30d.xlsx'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err: any) {
      alert(err.message || 'Erro ao exportar')
    }
  }

  if (loading) return <LoadingSpinner />

  const s = stats || {} as DashboardStats
  const cards = [
    { label: 'Cameras', value: s.cameras_total, sub: 'cadastradas', color: '#2563eb' },
    { label: 'Videos', value: s.videos_total, sub: `${s.videos_extracted || 0} extraidos`, color: '#8b5cf6' },
    { label: 'Frames', value: s.frames_total, sub: `${s.frames_annotated || 0} anotados`, color: '#f59e0b' },
    { label: 'Treinamentos', value: s.jobs_total, sub: `${s.jobs_running || 0} em execucao`, color: '#22c55e' },
    { label: 'Modelos', value: s.models_total, sub: `${s.models_active || 0} ativos`, color: '#ec4899' },
    { label: 'Alertas (24h)', value: s.alerts_24h, sub: `${s.alerts_pending || 0} pendentes`, color: '#ef4444' },
  ]

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ color: '#e2e8f0', margin: 0 }}>Dashboard</h2>
        <button onClick={exportExcel} style={{
          padding: '8px 16px', borderRadius: 8, border: '1px solid #334155',
          background: '#1e293b', color: '#94a3b8', fontSize: 13, cursor: 'pointer',
        }}>
          Exportar Excel
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 14 }}>
        {cards.map(card => (
          <div key={card.label} style={{
            padding: 20, background: '#1e293b', borderRadius: 12,
            border: '1px solid #334155',
          }}>
            <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 6 }}>{card.label}</div>
            <div style={{ fontSize: 32, fontWeight: 800, color: card.color }}>{card.value ?? 0}</div>
            <div style={{ color: '#64748b', fontSize: 12, marginTop: 4 }}>{card.sub}</div>
          </div>
        ))}
      </div>

      {s.class_distribution && s.class_distribution.length > 0 && (
        <div style={{
          marginTop: 24, padding: 20, background: '#1e293b',
          borderRadius: 12, border: '1px solid #334155',
        }}>
          <h3 style={{ color: '#e2e8f0', marginBottom: 12, fontSize: 15 }}>Distribuicao de Classes</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            {s.class_distribution.map(item => (
              <div key={item.class} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ color: '#94a3b8', fontSize: 13, minWidth: 120 }}>{item.class}</span>
                <div style={{ flex: 1, height: 8, background: '#334155', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', background: '#2563eb', borderRadius: 4,
                    width: `${Math.min(100, (item.count / Math.max(...s.class_distribution.map(c => c.count))) * 100)}%`,
                  }} />
                </div>
                <span style={{ color: '#64748b', fontSize: 12, minWidth: 40, textAlign: 'right' }}>{item.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{
        marginTop: 24, padding: 20, background: '#1e293b',
        borderRadius: 12, border: '1px solid #334155',
      }}>
        <h3 style={{ color: '#e2e8f0', marginBottom: 12, fontSize: 15 }}>Status do Sistema</h3>
        <div style={{ display: 'grid', gap: 6 }}>
          {[
            ['API V2', 'Online', '#22c55e'],
            ['Database', 'Conectado', '#22c55e'],
            ['Redis', 'Conectado', '#22c55e'],
            ['Arquitetura', 'Microservicos V2', '#64748b'],
          ].map(([label, value, color]) => (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: 13 }}>
              <span>{label}</span>
              <span style={{ color, fontWeight: 600 }}>{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
