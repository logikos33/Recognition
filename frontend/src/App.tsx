/**
 * App.tsx — routing e auth gate.
 * Max 100 linhas. Rotas em AppRoutes.tsx.
 */
import { BrowserRouter } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { Login } from './pages/Login'
import { AppRoutes } from './AppRoutes'
import { AppShell } from './components/layout/AppShell/AppShell'
import { Header } from './components/layout/Header/Header'
import type { User } from './hooks/useAuth'

function AppShellWrapper({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <AppShell>
      <Header user={user} onLogout={onLogout} />
      <AppRoutes />
    </AppShell>
  )
}

export default function App() {
  const { user, isAuthenticated, logout } = useAuth()

  if (!isAuthenticated || !user) {
    return <Login />
  }

  return (
    <BrowserRouter>
      <AppShellWrapper user={user} onLogout={logout} />
    </BrowserRouter>
  )
}
