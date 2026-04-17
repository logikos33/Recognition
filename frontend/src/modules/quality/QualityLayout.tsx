/**
 * Módulo de Qualidade — Layout raiz com submenu horizontal e breadcrumb.
 *
 * Redireciona para /modules se o tenant não tiver o módulo 'quality' habilitado.
 * Subrotas definidas internamente com React Router v6 <Routes>.
 */
import { useEffect } from 'react'
import { NavLink, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import {
  layoutRoot, topBar, topBarTitle, nav, navLink, navLinkActive,
  main, breadcrumb, breadcrumbSep,
} from './QualityLayout.css'

// Pages — importadas diretamente (bundle splitting feito pelo Vite por code-splitting no AppRoutes)
import { QualityDashboard } from './pages/QualityDashboard'
import { QualityInspectionsPage } from './pages/QualityInspectionsPage'
import { QualityInspectionDetail } from './pages/QualityInspectionDetail'
import { QualityAnnotationWorkspace } from './pages/QualityAnnotationWorkspace'
import { TrainingPage } from '../../pages/TrainingPage'
import { QualityCamerasPage } from './pages/QualityCamerasPage'
import { QualityAndonDisplay } from './pages/QualityAndonDisplay'

const NAV_ITEMS = [
  { to: '/quality/dashboard',    label: 'Dashboard' },
  { to: '/quality/inspections',  label: 'Inspeções' },
  { to: '/quality/cameras',      label: 'Câmeras' },
  { to: '/quality/training',     label: 'Treinamento' },
]

function BreadcrumbBar() {
  const location = useLocation()
  const parts = location.pathname.split('/').filter(Boolean)

  const labels: Record<string, string> = {
    quality: 'Qualidade',
    dashboard: 'Dashboard',
    inspections: 'Inspeções',
    cameras: 'Câmeras',
    training: 'Treinamento',
    annotate: 'Anotação',
    andon: 'Andon',
  }

  return (
    <div className={breadcrumb}>
      <span>Home</span>
      {parts.map((part, i) => {
        // Não exibir UUIDs no breadcrumb
        const isUuid = /^[0-9a-f-]{36}$/.test(part)
        return (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span className={breadcrumbSep}>/</span>
            <span>{isUuid ? '…' : (labels[part] ?? part)}</span>
          </span>
        )
      })}
    </div>
  )
}

export function QualityLayout() {
  const { hasModule } = useAuth()
  const navigate = useNavigate()

  // Redirecionar se o tenant não tem o módulo de qualidade
  useEffect(() => {
    if (!hasModule('quality')) {
      navigate('/modules', { replace: true })
    }
  }, [hasModule, navigate])

  if (!hasModule('quality')) return null

  return (
    <div className={layoutRoot}>
      {/* Top bar com submenu de navegação */}
      <header className={topBar}>
        <div className={topBarTitle}>
          <span>Qualidade</span>
        </div>

        <nav className={nav} aria-label="Submenu Qualidade">
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => isActive ? navLinkActive : navLink}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      {/* Breadcrumb */}
      <BreadcrumbBar />

      {/* Conteúdo principal */}
      <main className={main}>
        <Routes>
          {/* Rota padrão → dashboard */}
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<QualityDashboard />} />
          <Route path="inspections" element={<QualityInspectionsPage />} />
          <Route path="inspections/:id" element={<QualityInspectionDetail />} />
          <Route path="inspections/:inspectionId/annotate" element={<QualityAnnotationWorkspace />} />
          <Route path="cameras" element={<QualityCamerasPage />} />
          <Route path="training" element={<TrainingPage />} />
          {/* Andon — sem JWT, acesso por IP interno validado no backend */}
          <Route path="andon/:cameraId" element={<QualityAndonDisplay />} />
          {/* Catch-all */}
          <Route path="*" element={<Navigate to="dashboard" replace />} />
        </Routes>
      </main>
    </div>
  )
}
