/**
 * App.tsx — routing e auth gate.
 * Max 100 linhas. Toda logica em hooks e componentes dedicados.
 */
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { Login } from './pages/Login'
import { DashboardPage } from './pages/DashboardPage'
import { CamerasPage } from './pages/CamerasPage'
import { AnnotationPage } from './pages/AnnotationPage'
import { TrainingPage } from './pages/TrainingPage'
import { MonitoringPage } from './pages/MonitoringPage'
import { AlertsHistoryPage } from './pages/AlertsHistoryPage'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import type { User } from './hooks/useAuth'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/cameras', label: 'Cameras' },
  { to: '/monitoring', label: 'Monitoramento' },
  { to: '/alerts', label: 'Alertas' },
  { to: '/annotation', label: 'Anotacao' },
  { to: '/training', label: 'Treinamento' },
]

const navStyle = (isActive: boolean): React.CSSProperties => ({
  padding: '6px 14px', borderRadius: 6, fontSize: 13, fontWeight: 600,
  textDecoration: 'none', cursor: 'pointer',
  background: isActive ? '#1e40af' : 'transparent',
  color: isActive ? '#fff' : '#94a3b8',
})

function AppShell({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <div style={{ minHeight: '100vh', background: '#0f172a', color: 'white', fontFamily: 'Inter, sans-serif' }}>
      <header style={{
        background: '#1e293b', borderBottom: '1px solid #334155',
        padding: '10px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <NavLink to="/dashboard" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 20 }}>EPI</span>
            <span style={{ fontWeight: 700, fontSize: 16, color: '#e2e8f0' }}>Monitor V2</span>
          </NavLink>
          <nav style={{ display: 'flex', gap: 4, marginLeft: 16 }}>
            {NAV_ITEMS.map(item => (
              <NavLink key={item.to} to={item.to} style={({ isActive }) => navStyle(isActive)}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: '#94a3b8', fontSize: 13 }}>{user.name}</span>
          <span style={{
            padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700,
            background: user.role === 'admin' ? '#1d4ed8' : '#059669', color: 'white',
          }}>{user.role.toUpperCase()}</span>
          <button onClick={onLogout} style={{
            padding: '5px 12px', borderRadius: 6, background: 'transparent',
            border: '1px solid #475569', color: '#94a3b8', cursor: 'pointer', fontSize: 12,
          }}>Sair</button>
        </div>
      </header>
      <ErrorBoundary>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/cameras" element={<CamerasPage />} />
          <Route path="/annotation" element={<AnnotationPage />} />
          <Route path="/training" element={<TrainingPage />} />
          <Route path="/monitoring" element={<MonitoringPage />} />
          <Route path="/alerts" element={<AlertsHistoryPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </ErrorBoundary>
    </div>
  )
}

export default function App() {
  const { user, isAuthenticated, logout } = useAuth()

  if (!isAuthenticated || !user) {
    return <Login />
  }

  return (
    <BrowserRouter>
      <AppShell user={user} onLogout={logout} />
    </BrowserRouter>
  )
}
