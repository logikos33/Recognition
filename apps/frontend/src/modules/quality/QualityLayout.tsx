/**
 * Módulo de Qualidade — Layout raiz com submenu horizontal.
 *
 * Redireciona para /modules se o tenant não tiver o módulo 'quality' habilitado.
 * Subrotas definidas internamente com React Router v6 <Routes>.
 */
import { useEffect, lazy, Suspense } from 'react'
import { NavLink, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useAppStore } from '../../stores/appStore'
import {
  layoutRoot, topBar, nav, navLink, navLinkActive, main,
} from './QualityLayout.css'

// Pages — importadas diretamente (bundle splitting feito pelo Vite por code-splitting no AppRoutes)
import { QualityDashboard } from './pages/QualityDashboard'
import { QualityInspectionsPage } from './pages/QualityInspectionsPage'
import { QualityInspectionDetail } from './pages/QualityInspectionDetail'
import { QualityAnnotationWorkspace } from './pages/QualityAnnotationWorkspace'
import { TrainingPage } from '../../pages/TrainingPage'
import { QualityCamerasPage } from './pages/QualityCamerasPage'
import { QualityAndonDisplay } from './pages/QualityAndonDisplay'

// Quality Gate — carregados lazy para manter bundle da rota principal leve
const QualityPiecesPage = lazy(() => import('./pages/QualityPiecesPage').then(m => ({ default: m.QualityPiecesPage })))
const QualityReworkPage = lazy(() => import('./pages/QualityReworkPage').then(m => ({ default: m.QualityReworkPage })))
const QualityReportsPage = lazy(() => import('./pages/QualityReportsPage').then(m => ({ default: m.QualityReportsPage })))
const QualityConfigPage = lazy(() => import('./pages/QualityConfigPage').then(m => ({ default: m.QualityConfigPage })))

// Câmeras é a aba padrão — operador abre o módulo para ver o cockpit ao vivo
const NAV_ITEMS = [
  { to: '/quality/cameras',     label: 'Câmeras' },
  { to: '/quality/dashboard',   label: 'Dashboard' },
  { to: '/quality/inspections', label: 'Inspeções' },
  { to: '/quality/training',    label: 'Treinamento' },
  { to: '/quality/pieces',      label: 'Peças' },
  { to: '/quality/rework',      label: 'Retrabalho' },
  { to: '/quality/reports',     label: 'Relatórios' },
  { to: '/quality/config',      label: 'Config' },
]

export function QualityLayout() {
  const { hasModule } = useAuth()
  const navigate = useNavigate()
  const setSelectedModule = useAppStore((s) => s.setSelectedModule)

  useEffect(() => {
    setSelectedModule('quality')
    if (!hasModule('quality')) {
      navigate('/modules', { replace: true })
    }
  }, [hasModule, navigate, setSelectedModule])

  if (!hasModule('quality')) return null

  return (
    <div className={layoutRoot}>
      {/* Top bar com submenu de navegação */}
      <header className={topBar}>
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

      {/* Conteúdo principal */}
      <main className={main}>
        <Routes>
          {/* Rota padrão → câmeras (cockpit operacional) */}
          <Route index element={<Navigate to="cameras" replace />} />
          <Route path="cameras" element={<QualityCamerasPage />} />
          <Route path="dashboard" element={<QualityDashboard />} />
          <Route path="inspections" element={<QualityInspectionsPage />} />
          <Route path="inspections/:id" element={<QualityInspectionDetail />} />
          <Route path="inspections/:inspectionId/annotate" element={<QualityAnnotationWorkspace />} />
          <Route path="training" element={<TrainingPage />} />
          {/* Andon — sem JWT, acesso por IP interno validado no backend */}
          <Route path="andon/:cameraId" element={<QualityAndonDisplay />} />
          {/* Quality Gate — sub-rotas do gate RVB */}
          <Route path="pieces"  element={<Suspense fallback={null}><QualityPiecesPage /></Suspense>} />
          <Route path="rework"  element={<Suspense fallback={null}><QualityReworkPage /></Suspense>} />
          <Route path="reports" element={<Suspense fallback={null}><QualityReportsPage /></Suspense>} />
          <Route path="config"  element={<Suspense fallback={null}><QualityConfigPage /></Suspense>} />
          {/* Catch-all */}
          <Route path="*" element={<Navigate to="cameras" replace />} />
        </Routes>
      </main>
    </div>
  )
}
