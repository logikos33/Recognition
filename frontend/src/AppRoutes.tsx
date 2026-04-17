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
import { FuelingPlaceholder } from './pages/fueling/FuelingPlaceholder'
import { ReportsPage } from './pages/ReportsPage'
import { VerificationQueuePage } from './pages/VerificationQueuePage'
import ModuleClassesPage from './pages/ModuleClassesPage'
import { AdminDashboard } from './pages/admin/AdminDashboard'
import { AdminTenantsPage } from './pages/admin/AdminTenantsPage'
import { AdminTenantDetailPage } from './pages/admin/AdminTenantDetailPage'
import { AdminTicketsPage } from './pages/admin/AdminTicketsPage'
// Módulo de Qualidade Industrial — importação lazy para não impactar bundle dos outros módulos
import { lazy, Suspense } from 'react'
const QualityLayout = lazy(() => import('./modules/quality/QualityLayout').then(m => ({ default: m.QualityLayout })))

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
        <Route path="/epi/reports" element={<ReportsPage />} />
        <Route path="/epi/verification" element={<VerificationQueuePage />} />

        {/* Admin module — superadmin only, guarded by AdminRoute */}
        <Route element={<AdminRoute />}>
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/admin/tenants" element={<AdminTenantsPage />} />
          <Route path="/admin/tenant/:id" element={<AdminTenantDetailPage />} />
          <Route path="/admin/tickets" element={<AdminTicketsPage />} />
        </Route>

        {/* Legacy routes → redirect to canonical */}
        <Route path="/home" element={<Navigate to="/epi/dashboard" replace />} />
        <Route path="/dashboard" element={<Navigate to="/epi/dashboard" replace />} />
        <Route path="/cameras" element={<Navigate to="/epi/cameras" replace />} />
        <Route path="/annotation" element={<Navigate to="/epi/training" replace />} />
        <Route path="/training" element={<Navigate to="/epi/training" replace />} />
        <Route path="/monitoring" element={<Navigate to="/epi/dashboard" replace />} />
        <Route path="/epi/monitoring" element={<Navigate to="/epi/dashboard" replace />} />
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
        <Route path="/fueling/*" element={<FuelingPlaceholder />} />

        {/* Catch-all */}
        <Route path="*" element={<RootRedirect />} />
      </Routes>
    </ErrorBoundary>
  )
}
