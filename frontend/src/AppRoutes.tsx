/**
 * AppRoutes — todas as rotas da aplicação.
 * Separado para manter App.tsx dentro do limite de 100 linhas.
 */
import { Routes, Route, Navigate } from 'react-router-dom'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
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
        <Route path="/" element={<HomePage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/cameras" element={<CamerasPage />} />
        <Route path="/annotation" element={<AnnotationPage />} />
        <Route path="/training" element={<TrainingPage />} />
        <Route path="/monitoring" element={<MonitoringPage />} />
        <Route path="/alerts" element={<AlertsHistoryPage />} />
        <Route path="/epi/dashboard" element={<EpiDashboard />} />
        <Route path="/epi/cameras" element={<EpiCameras />} />
        <Route path="/epi/alerts" element={<EpiAlerts />} />
        <Route path="/fueling/*" element={<FuelingPlaceholder />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  )
}
