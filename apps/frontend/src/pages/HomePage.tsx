/**
 * HomePage — Dashboard global com reports e cards de módulos.
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useModules, type Module } from '../hooks/useModules'
import { reportService, type HomeReports } from '../services/reportService'
import {
  page, pageHeader, pageTitle, pageSubtitle, cardsGrid,
  reportCard, reportIconBox, reportLabel, reportValue, reportSub,
  chartCard, chartTitle, chartEmpty, chartBars, chartBar,
  modulesSection, modulesSectionTitle, modulesGrid,
  moduleCardClickable, moduleCardDisabled, moduleCardInner,
  moduleCardTitle, moduleCardDesc, moduleCardStats, moduleCardCta,
  comingSoonBadge, loadingBox,
} from './HomePage.css'
import { vars } from '../styles/theme.css'

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function ReportCard({ icon, label, value, sub, color }: {
  icon: string; label: string; value: string; sub: string; color: string
}) {
  return (
    <div className={reportCard}>
      <div className={reportIconBox} style={{ background: color + '22' }}>{icon}</div>
      <div>
        <div className={reportLabel}>{label}</div>
        <div className={reportValue}>{value}</div>
        <div className={reportSub}>{sub}</div>
      </div>
    </div>
  )
}

function ModuleCard({ mod, title, desc, icon, onClick, comingSoon }: {
  mod?: Module; title: string; desc: string; icon: string; onClick?: () => void; comingSoon?: boolean
}) {
  const cls = comingSoon ? moduleCardDisabled : onClick ? moduleCardClickable : moduleCardDisabled
  return (
    <div className={cls} onClick={onClick}>
      <div className={moduleCardInner}>
        <div style={{ fontSize: 36 }}>{icon}</div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <span className={moduleCardTitle}>{title}</span>
            {comingSoon && <span className={comingSoonBadge}>Em breve</span>}
          </div>
          <p className={moduleCardDesc}>{desc}</p>
          {mod && (
            <div className={moduleCardStats}>
              <span><strong style={{ color: 'inherit' }}>{mod.cameras_count}</strong> câmeras</span>
              <span><strong style={{ color: 'inherit' }}>{mod.alerts_today}</strong> alertas hoje</span>
            </div>
          )}
          {onClick && <div className={moduleCardCta}>Acessar módulo →</div>}
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

  const chart = reports?.chart.alerts_by_hour ?? []
  const maxCount = Math.max(...chart.map(h => h.count), 1)

  if (loading || modulesLoading) {
    return <div className={loadingBox}>Carregando...</div>
  }

  const c = reports?.cards
  return (
    <div className={page}>
      <div className={pageHeader}>
        <h1 className={pageTitle}>Dashboard</h1>
        <p className={pageSubtitle}>Visão geral do sistema</p>
      </div>

      <div className={cardsGrid}>
        <ReportCard icon="🚨" label="Alertas Hoje" value={fmt(c?.alerts_today ?? 0)} sub={`${fmt(c?.alerts_week ?? 0)} esta semana`} color="#ef4444" />
        <ReportCard icon="📷" label="Câmeras Ativas" value={String(c?.cameras_active ?? 0)} sub={`de ${c?.cameras_total ?? 0} total`} color={vars.color.primary} />
        <ReportCard icon="⚡" label="Processamentos" value={fmt(c?.processings_today ?? 0)} sub="frames hoje" color={vars.color.success} />
        <ReportCard icon="👁" label="Objetos Identificados" value={fmt(c?.objects_identified ?? 0)} sub="detecções hoje" color="#a855f7" />
      </div>

      <div className={chartCard}>
        <div className={chartTitle}>Alertas — últimas 24h</div>
        {chart.length === 0 ? (
          <div className={chartEmpty}>Sem alertas registrados</div>
        ) : (
          <div className={chartBars}>
            {chart.map((h, i) => (
              <div key={i} className={chartBar} title={`${h.count} alertas`}
                style={{ height: `${Math.max(4, (h.count / maxCount) * 80)}px` }} />
            ))}
          </div>
        )}
      </div>

      <div className={modulesSection}>
        <h2 className={modulesSectionTitle}>Módulos</h2>
        <div className={modulesGrid}>
          <ModuleCard mod={getModule('epi')} title="EPI" icon="🦺"
            desc="Reconhecimento de EPIs em tempo real via câmeras CCTV."
            onClick={hasModule('epi') ? () => navigate('/epi/dashboard') : undefined} />
          <ModuleCard mod={getModule('quality')} title="Qualidade Industrial" icon="🔬"
            desc="Controle de qualidade com inspeção visual YOLO, CEP e relatórios de turno."
            onClick={hasModule('quality') ? () => navigate('/quality/dashboard') : undefined} />
          <ModuleCard title="Fueling Control" icon="⛽" comingSoon
            desc="Acompanhamento de abastecimento com OCR de placas e contagem automática." />
        </div>
      </div>
    </div>
  )
}

export default HomePage
