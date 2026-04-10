/**
 * AppRoutes — todas as rotas da aplicacao.
 * Pos-login redireciona para /modules (selecao de modulo).
 */
import { Routes, Route, Navigate } from 'react-router-dom'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { ModuleSelectionPage } from './pages/ModuleSelectionPage'
import { TrainingPage } from './pages/TrainingPage'
import { EpiDashboard } from './pages/epi/EpiDashboard'
import { EpiAlerts } from './pages/epi/EpiAlerts'
import { EpiCameras } from './pages/epi/EpiCameras'
import { FuelingPlaceholder } from './pages/fueling/FuelingPlaceholder'
import { ReportsPage } from './pages/ReportsPage'

export function AppRoutes() {
  return (
    <ErrorBoundary>
      <Routes>
        {/* Entry point — module selection */}
        <Route path="/" element={<Navigate to="/modules" replace />} />
        <Route path="/modules" element={<ModuleSelectionPage />} />

        {/* EPI module — canonical routes */}
        <Route path="/epi/dashboard" element={<EpiDashboard />} />
        <Route path="/epi/cameras" element={<EpiCameras />} />
        <Route path="/epi/alerts" element={<EpiAlerts />} />
        <Route path="/epi/training" element={<TrainingPage />} />
        <Route path="/epi/reports" element={<ReportsPage />} />

        {/* Legacy routes → redirect to canonical */}
        <Route path="/home" element={<Navigate to="/epi/dashboard" replace />} />
        <Route path="/dashboard" element={<Navigate to="/epi/dashboard" replace />} />
        <Route path="/cameras" element={<Navigate to="/epi/cameras" replace />} />
        <Route path="/annotation" element={<Navigate to="/epi/training" replace />} />
        <Route path="/training" element={<Navigate to="/epi/training" replace />} />
        <Route path="/monitoring" element={<Navigate to="/epi/dashboard" replace />} />
        <Route path="/epi/monitoring" element={<Navigate to="/epi/dashboard" replace />} />
        <Route path="/alerts" element={<Navigate to="/epi/alerts" replace />} />

        {/* Fueling module */}
        <Route path="/fueling/*" element={<FuelingPlaceholder />} />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/modules" replace />} />
      </Routes>
    </ErrorBoundary>
  )
}
