/**
 * EpiDashboard — Página de dashboard do módulo EPI.
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { moduleService, type ModuleClass, type ModuleStats } from '../../services/moduleService'

export function EpiDashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<ModuleStats | null>(null)
  const [classes, setClasses] = useState<ModuleClass[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      moduleService.getStats('epi'),
      moduleService.getClasses('epi'),
    ])
      .then(([s, c]) => { setStats(s); setClasses(c) })
      .catch(() => {/* silent */})
      .finally(() => setLoading(false))
  }, [])

  const statCard = (icon: string, label: string, value: number | string, color: string) => (
    <div style={{ background: '#1e293b', borderRadius: 10, padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ fontSize: 24, width: 40, height: 40, borderRadius: 8, background: color + '22', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 11, color: '#64748b' }}>{label}</div>
        <div style={{ fontSize: 20, fontWeight: 700, color: '#e2e8f0' }}>{loading ? '—' : value}</div>
      </div>
    </div>
  )

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: 1 }}>Módulo</div>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0', margin: '4px 0 0' }}>🦺 EPI Monitor</h1>
        <p style={{ fontSize: 13, color: '#64748b', margin: '4px 0 0' }}>Reconhecimento de Equipamentos de Proteção Individual</p>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 24 }}>
        {statCard('📷', 'Câmeras Ativas', stats?.cameras_active ?? 0, '#3b82f6')}
        {statCard('📊', 'Total Câmeras', stats?.cameras_total ?? 0, '#6366f1')}
        {statCard('🚨', 'Alertas Hoje', stats?.alerts_today ?? 0, '#ef4444')}
        {statCard('📅', 'Alertas Semana', stats?.alerts_week ?? 0, '#f59e0b')}
      </div>

      {/* Classes detectadas */}
      {classes.length > 0 && (
        <div style={{ background: '#1e293b', borderRadius: 12, padding: 24, marginBottom: 24 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 16 }}>Classes Detectadas</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 8 }}>
            {classes.map(cls => (
              <div
                key={cls.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 12px', borderRadius: 8,
                  background: cls.color + '18', border: `1px solid ${cls.color}44`,
                }}
              >
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: cls.color, flexShrink: 0 }} />
                <span style={{ fontSize: 12, color: '#e2e8f0', fontWeight: 500 }}>{cls.display_name}</span>
                {cls.is_violation && <span style={{ marginLeft: 'auto', fontSize: 10 }}>⚠️</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick links */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
        {[
          { icon: '📷', label: 'Câmeras', path: '/epi/cameras', color: '#3b82f6' },
          { icon: '🚨', label: 'Alertas', path: '/epi/alerts', color: '#ef4444' },
          { icon: '🎯', label: 'Monitoramento', path: '/monitoring', color: '#22c55e' },
          { icon: '🤖', label: 'Treinamento', path: '/training', color: '#a855f7' },
        ].map(link => (
          <button
            key={link.path}
            onClick={() => navigate(link.path)}
            style={{
              background: '#1e293b', border: '1px solid #334155', borderRadius: 10,
              padding: '16px 20px', cursor: 'pointer', textAlign: 'left',
              transition: 'border-color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget as HTMLButtonElement).style.borderColor = '#475569'}
            onMouseLeave={e => (e.currentTarget as HTMLButtonElement).style.borderColor = '#334155'}
          >
            <div style={{ fontSize: 22, marginBottom: 6 }}>{link.icon}</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0' }}>{link.label}</div>
          </button>
        ))}
      </div>
    </div>
  )
}

export default EpiDashboard
