/**
 * AppRoutes — todas as rotas da aplicacao.
 * Pos-login: operator → /modules, superadmin → /admin.
 * Rotas /admin/* protegidas por AdminRoute (role superadmin).
 */
import { Routes, Route, Navigate } from 'react-router-dom'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { AdminRoute } from './components/guards/AdminRoute'
import { useAuth } from './hooks/useAuth'
import { ModuleSelectionPage } from './pages/ModuleSelectionPage'
import { TrainingPage } from './pages/TrainingPage'
import { EpiDashboard } from './pages/epi/EpiDashboard'
import { EpiAlerts } from './pages/epi/EpiAlerts'
import { EpiCameras } from './pages/epi/EpiCameras'
import { FuelingPage } from './pages/fueling/FuelingPage'
import { FuelingValidationPage } from './pages/fueling/FuelingValidationPage'
import { ReportsPage } from './pages/ReportsPage'
import { VerificationQueuePage } from './pages/VerificationQueuePage'
import { CountingPage } from './pages/CountingPage'
import { StreamHealthPage } from './pages/StreamHealthPage'
import ModuleClassesPage from './pages/ModuleClassesPage'
import { EpiOperationsPage } from './pages/epi/EpiOperationsPage'
import { MonitoringPage } from './pages/MonitoringPage'
import { EpiScenarioEditorPage } from './pages/epi/EpiScenarioEditorPage'
import { EpiSitesHealthPage } from './pages/epi/EpiSitesHealthPage'
import { InvestigationPage } from './pages/epi/InvestigationPage'
import { lazy, Suspense } from 'react'
const QualityLayout = lazy(() => import('./modules/quality/QualityLayout').then(m => ({ default: m.QualityLayout })))
const AdminLayout = lazy(() => import('./modules/admin/AdminLayout').then(m => ({ default: m.AdminLayout })))
const DesignSystemPage = lazy(() => import('./pages/DesignSystemPage').then(m => ({ default: m.DesignSystemPage })))
// Tablet Kiosk — rota pública sem JWT, acesso por IP interno (Quality Gate RVB)
const TabletKiosk = lazy(() => import('./modules/quality/tablet/TabletKiosk').then(m => ({ default: m.TabletKiosk })))

function RootRedirect() {
  const { isSuperAdmin } = useAuth()
  return <Navigate to={isSuperAdmin ? '/admin' : '/modules'} replace />
}

export function AppRoutes() {
  return (
    <ErrorBoundary>
      <Routes>
        {/* Entry point — role-based redirect */}
        <Route path="/" element={<RootRedirect />} />
        <Route path="/modules" element={<ModuleSelectionPage />} />

        {/* EPI module — canonical routes */}
        <Route path="/epi/dashboard" element={<EpiDashboard />} />
        <Route path="/epi/cameras" element={<EpiCameras />} />
        <Route path="/epi/alerts" element={<EpiAlerts />} />
        <Route path="/epi/training" element={<TrainingPage />} />
        <Route path="/epi/training/classes" element={<ModuleClassesPage />} />
        <Route path="/epi/cameras/:cameraId/operations" element={<EpiOperationsPage />} />
        <Route path="/epi/cameras/:cameraId/scenario" element={<EpiScenarioEditorPage />} />
        <Route path="/epi/reports" element={<ReportsPage />} />
        <Route path="/epi/verification" element={<VerificationQueuePage />} />
        <Route path="/epi/counting" element={<CountingPage />} />
        <Route path="/epi/health" element={<StreamHealthPage />} />
        <Route path="/epi/sites-health" element={<EpiSitesHealthPage />} />
        <Route path="/epi/investigation" element={<InvestigationPage />} />

        {/* Admin module — superadmin only, lazy-loaded */}
        <Route element={<AdminRoute />}>
          <Route
            path="/admin/*"
            element={
              <Suspense fallback={<div style={{ padding: 32 }}>Carregando...</div>}>
                <AdminLayout />
              </Suspense>
            }
          />
          <Route
            path="/design-system"
            element={
              <Suspense fallback={<div style={{ padding: 32 }}>Carregando...</div>}>
                <DesignSystemPage />
              </Suspense>
            }
          />
        </Route>

        {/* Legacy routes → redirect to canonical */}
        <Route path="/home" element={<Navigate to="/epi/dashboard" replace />} />
        <Route path="/dashboard" element={<Navigate to="/epi/dashboard" replace />} />
        <Route path="/cameras" element={<Navigate to="/epi/cameras" replace />} />
        <Route path="/annotation" element={<Navigate to="/epi/training" replace />} />
        <Route path="/training" element={<Navigate to="/epi/training" replace />} />
        <Route path="/monitoring" element={<Navigate to="/epi/monitoring" replace />} />
        <Route path="/epi/monitoring" element={<MonitoringPage />} />
        <Route path="/alerts" element={<Navigate to="/epi/alerts" replace />} />

        {/* Quality module — carregado via lazy para isolamento de bundle */}
        <Route
          path="/quality/*"
          element={
            <Suspense fallback={null}>
              <QualityLayout />
            </Suspense>
          }
        />

        {/* Fueling module */}
        <Route path="/fueling/validation" element={<FuelingValidationPage />} />
        <Route path="/fueling/*" element={<FuelingPage />} />

        {/* Tablet Kiosk — rota pública sem JWT, acesso por IP interno */}
        <Route
          path="/tablet/:station"
          element={
            <Suspense fallback={<div style={{ background: '#0a0c10' /* allow: bgBase tablet fallback */, minHeight: '100vh' }} />}>
              <TabletKiosk />
            </Suspense>
          }
        />

        {/* Catch-all */}
        <Route path="*" element={<RootRedirect />} />
      </Routes>
    </ErrorBoundary>
  )
}
