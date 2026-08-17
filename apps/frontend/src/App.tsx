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
import { GlobalBanners } from './components/layout/GlobalBanners'
import { ThemeProvider } from './theme/ThemeProvider'
import type { User } from './hooks/useAuth'

function AppShellWrapper({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <AppShell>
      {/* Banners globais (impersonation + contexto de tenant assumido) —
          fora das rotas, visíveis em todas as telas; ocupam espaço real no
          layout via --global-banner-offset (ver GlobalBanners.tsx) */}
      <GlobalBanners />
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
