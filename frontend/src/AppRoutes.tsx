/**
 * AppRoutes — todas as rotas da aplicação.
 * Pós-login redireciona para /modules (seleção de módulo).
 */
import { Routes, Route, Navigate } from 'react-router-dom'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { ModuleSelectionPage } from './pages/ModuleSelectionPage'
import { DashboardPage } from './pages/DashboardPage'
import { CamerasPage } from './pages/CamerasPage'
import { AnnotationPage } from './pages/AnnotationPage'
import { TrainingPage } from './pages/TrainingPage'
import { MonitoringPage } from './pages/MonitoringPage'
import { AlertsHistoryPage } from './pages/AlertsHistoryPage'
import { HomePage } from './pages/HomePage'
import { EpiDashboard } from './pages/epi/EpiDashboard'
import { EpiCameras } from './pages/epi/EpiCameras'
import { EpiAlerts } from './pages/epi/EpiAlerts'
import { FuelingPlaceholder } from './pages/fueling/FuelingPlaceholder'

export function AppRoutes() {
  return (
    <ErrorBoundary>
      <Routes>
        {/* Entry point — module selection */}
        <Route path="/" element={<Navigate to="/modules" replace />} />
        <Route path="/modules" element={<ModuleSelectionPage />} />

        {/* Legacy routes */}
        <Route path="/home" element={<HomePage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/cameras" element={<CamerasPage />} />
        <Route path="/annotation" element={<AnnotationPage />} />
        <Route path="/training" element={<TrainingPage />} />
        <Route path="/monitoring" element={<MonitoringPage />} />
        <Route path="/alerts" element={<AlertsHistoryPage />} />

        {/* EPI module */}
        <Route path="/epi/dashboard" element={<EpiDashboard />} />
        <Route path="/epi/cameras" element={<EpiCameras />} />
        <Route path="/epi/alerts" element={<EpiAlerts />} />

        {/* Fueling module */}
        <Route path="/fueling/*" element={<FuelingPlaceholder />} />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/modules" replace />} />
      </Routes>
    </ErrorBoundary>
  )
}
