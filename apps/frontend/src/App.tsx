/**
 * App.tsx — routing e auth gate.
 * Max 100 linhas. Rotas em AppRoutes.tsx.
 */
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { Login } from './pages/Login'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { AppRoutes } from './AppRoutes'
import { AppShell } from './components/layout/AppShell/AppShell'
import { AppLayout } from './components/layout/AppLayout/AppLayout'
import { ChatFAB } from './components/chat/ChatFAB'
import { ImpersonationBanner } from './components/ImpersonationBanner'
import { ThemeProvider } from './theme/ThemeProvider'
import type { User } from './hooks/useAuth'

function AppShellWrapper({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <AppShell>
      {/* WS6: banner "vendo como" — fora das rotas, visível em todas as telas */}
      <ImpersonationBanner />
      <AppLayout user={user} onLogout={onLogout}>
        <AppRoutes />
      </AppLayout>
      <ChatFAB />
    </AppShell>
  )
}

export default function App() {
  const { user, isAuthenticated, logout } = useAuth()

  if (!isAuthenticated || !user) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="*" element={<Login />} />
        </Routes>
      </BrowserRouter>
    )
  }

  return (
    <ThemeProvider tenantId={user.tenant_id}>
      <BrowserRouter>
        <AppShellWrapper user={user} onLogout={logout} />
      </BrowserRouter>
    </ThemeProvider>
  )
}
