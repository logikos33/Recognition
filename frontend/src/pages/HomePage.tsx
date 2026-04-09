/**
 * HomePage — Dashboard global com reports e cards de módulos.
 * Max 200 linhas. Lógica em hooks dedicados.
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useModules, type Module } from '../hooks/useModules'
import { reportService, type HomeReports } from '../services/reportService'

const card = (bg: string): React.CSSProperties => ({
  background: bg, borderRadius: 12, padding: '20px 24px',
  display: 'flex', alignItems: 'center', gap: 16,
})
const iconBox = (color: string): React.CSSProperties => ({
  width: 44, height: 44, borderRadius: 10,
  background: color + '22', display: 'flex', alignItems: 'center',
  justifyContent: 'center', fontSize: 22, flexShrink: 0,
})

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function ReportCard({ icon, label, value, sub, color }: {
  icon: string; label: string; value: string; sub: string; color: string
}) {
  return (
    <div style={card('#1e293b')}>
      <div style={iconBox(color)}>{icon}</div>
      <div>
        <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 2 }}>{label}</div>
        <div style={{ fontSize: 24, fontWeight: 700, color: '#e2e8f0' }}>{value}</div>
        <div style={{ fontSize: 11, color: '#64748b' }}>{sub}</div>
      </div>
    </div>
  )
}

function ModuleCard({ mod, title, desc, icon, onClick, comingSoon }: {
  mod?: Module; title: string; desc: string; icon: string
  onClick?: () => void; comingSoon?: boolean
}) {
  return (
    <div
      onClick={onClick}
      style={{
        background: '#1e293b', borderRadius: 12, padding: 24,
        cursor: onClick ? 'pointer' : 'default', border: '1px solid #334155',
        opacity: comingSoon ? 0.7 : 1,
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => { if (onClick) (e.currentTarget as HTMLDivElement).style.borderColor = '#475569' }}
      onMouseLeave={e => (e.currentTarget as HTMLDivElement).style.borderColor = '#334155'}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
        <div style={{ fontSize: 36 }}>{icon}</div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ fontWeight: 700, fontSize: 16, color: '#e2e8f0' }}>{title}</span>
            {comingSoon && (
              <span style={{ fontSize: 10, background: '#334155', color: '#94a3b8', padding: '2px 6px', borderRadius: 4 }}>
                Em breve
              </span>
            )}
          </div>
          <p style={{ fontSize: 13, color: '#64748b', margin: 0, lineHeight: 1.5 }}>{desc}</p>
          {mod && (
            <div style={{ display: 'flex', gap: 16, marginTop: 12, fontSize: 12, color: '#94a3b8' }}>
              <span><strong style={{ color: '#e2e8f0' }}>{mod.cameras_count}</strong> câmeras</span>
              <span><strong style={{ color: '#e2e8f0' }}>{mod.alerts_today}</strong> alertas hoje</span>
            </div>
          )}
          {onClick && (
            <div style={{ marginTop: 12, fontSize: 12, color: '#3b82f6' }}>Acessar módulo →</div>
          )}
        </div>
      </div>
    </div>
  )
}

export function HomePage() {
  const navigate = useNavigate()
  const { loading: modulesLoading, hasModule, getModule } = useModules()
  const [reports, setReports] = useState<HomeReports | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    reportService.getHomeReports()
      .then(setReports)
      .catch(() => {/* silent — shows zeros */})
      .finally(() => setLoading(false))
  }, [])

  const cards = reports?.cards
  const chart = reports?.chart.alerts_by_hour ?? []
  const maxCount = Math.max(...chart.map(h => h.count), 1)

  if (loading || modulesLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 300 }}>
        <div style={{ color: '#64748b' }}>Carregando...</div>
      </div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0', margin: 0 }}>Dashboard</h1>
        <p style={{ fontSize: 13, color: '#64748b', margin: '4px 0 0' }}>Visão geral do sistema</p>
      </div>

      {/* Report cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 24 }}>
        <ReportCard icon="🚨" label="Alertas Hoje" value={fmt(cards?.alerts_today ?? 0)} sub={`${fmt(cards?.alerts_week ?? 0)} esta semana`} color="#ef4444" />
        <ReportCard icon="📷" label="Câmeras Ativas" value={String(cards?.cameras_active ?? 0)} sub={`de ${cards?.cameras_total ?? 0} total`} color="#3b82f6" />
        <ReportCard icon="⚡" label="Processamentos" value={fmt(cards?.processings_today ?? 0)} sub="frames hoje" color="#22c55e" />
        <ReportCard icon="👁" label="Objetos Identificados" value={fmt(cards?.objects_identified ?? 0)} sub="detecções hoje" color="#a855f7" />
      </div>

      {/* Chart */}
      <div style={{ background: '#1e293b', borderRadius: 12, padding: 24, marginBottom: 24 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 16 }}>Alertas — últimas 24h</div>
        {chart.length === 0 ? (
          <div style={{ color: '#475569', fontSize: 13, textAlign: 'center', padding: '24px 0' }}>Sem alertas registrados</div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 80 }}>
            {chart.map((h, i) => (
              <div
                key={i}
                title={`${h.count} alertas`}
                style={{
                  flex: 1, minWidth: 4, borderRadius: '2px 2px 0 0',
                  background: '#3b82f6',
                  height: `${Math.max(4, (h.count / maxCount) * 80)}px`,
                  transition: 'opacity 0.1s',
                  cursor: 'default',
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Module cards */}
      <div style={{ marginBottom: 12 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: '#e2e8f0', margin: '0 0 12px' }}>Módulos</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
          <ModuleCard
            mod={getModule('epi')}
            title="EPI Monitor"
            desc="Reconhecimento de Equipamentos de Proteção Individual em tempo real via câmeras CCTV."
            icon="🦺"
            onClick={hasModule('epi') ? () => navigate('/epi/dashboard') : undefined}
          />
          <ModuleCard
            title="Fueling Control"
            desc="Acompanhamento de abastecimento com OCR de placas e contagem automática de produtos."
            icon="⛽"
            comingSoon
          />
        </div>
      </div>
    </div>
  )
}

export default HomePage
