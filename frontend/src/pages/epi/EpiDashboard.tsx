/**
 * EpiDashboard — Página de dashboard do módulo EPI.
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { moduleService, type ModuleClass, type ModuleStats } from '../../services/moduleService'
import * as styles from './EpiDashboard.css'

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
    <div className={styles.statCard}>
      <div
        className={styles.statIconWrap}
        style={{ background: color + '22' }}
      >
        {icon}
      </div>
      <div>
        <div className={styles.statLabel}>{label}</div>
        <div className={styles.statValue}>{loading ? '—' : value}</div>
      </div>
    </div>
  )

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.moduleLabel}>Módulo</div>
        <h1 className={styles.moduleTitle}>🦺 EPI Monitor</h1>
        <p className={styles.moduleDesc}>Reconhecimento de Equipamentos de Proteção Individual</p>
      </div>

      {/* Stats */}
      <div className={styles.statsGrid}>
        {statCard('📷', 'Câmeras Ativas', stats?.cameras_active ?? 0, '#3b82f6')}
        {statCard('📊', 'Total Câmeras', stats?.cameras_total ?? 0, '#6366f1')}
        {statCard('🚨', 'Alertas Hoje', stats?.alerts_today ?? 0, '#ef4444')}
        {statCard('📅', 'Alertas Semana', stats?.alerts_week ?? 0, '#f59e0b')}
      </div>

      {/* Classes detectadas */}
      {classes.length > 0 && (
        <div className={styles.classesPanel}>
          <div className={styles.classesPanelTitle}>Classes Detectadas</div>
          <div className={styles.classesGrid}>
            {classes.map(cls => (
              <div
                key={cls.id}
                className={styles.classChip}
                style={{
                  background: cls.color + '18',
                  border: `1px solid ${cls.color}44`,
                }}
              >
                <div
                  className={styles.classDot}
                  style={{ background: cls.color }}
                />
                <span className={styles.className}>{cls.display_name}</span>
                {cls.is_violation && <span style={{ marginLeft: 'auto', fontSize: 10 }}>⚠️</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick links */}
      <div className={styles.quickLinksGrid}>
        {[
          { icon: '📷', label: 'Câmeras', path: '/epi/cameras' },
          { icon: '🚨', label: 'Alertas', path: '/epi/alerts' },
          { icon: '🎯', label: 'Monitoramento', path: '/monitoring' },
          { icon: '🤖', label: 'Treinamento', path: '/training' },
        ].map(link => (
          <button
            key={link.path}
            onClick={() => navigate(link.path)}
            className={styles.quickLinkBtn}
          >
            <div className={styles.quickLinkIcon}>{link.icon}</div>
            <div className={styles.quickLinkLabel}>{link.label}</div>
          </button>
        ))}
      </div>
    </div>
  )
}

export default EpiDashboard
