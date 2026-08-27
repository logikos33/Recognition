/**
 * App.tsx — routing e auth gate.
 * Max 100 linhas. Rotas em AppRoutes.tsx.
 */
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { Login } from './pages/Login'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { AppRoutes } from './AppRoutes'
import { AppShell } from './components/layout/AppShell/AppShell'
import { AppLayout } from './components/layout/AppLayout/AppLayout'
import { ChatFAB } from './components/chat/ChatFAB'
import { GlobalBanners } from './components/layout/GlobalBanners'
import { PREFIXO_NOVO, ROTAS_NOVAS } from './app/RotasNovas'
import { Shell } from './app/shell/Shell'
import { ThemeProvider } from './theme/ThemeProvider'
import type { User } from './hooks/useAuth'

/**
 * O FAB do chat é `position: fixed` no canto inferior direito (chat.css.ts:9,
 * zIndex 1000) e cobria os controles da tela de anotação — o anotador relatou
 * não conseguir ver o botão de descartar frame.
 *
 * Some na tela de anotação em vez de mexer em z-index ou reposicionar: é a
 * mudança menor, não move o chat para cobrir outra coisa, e a tela de anotação
 * é justamente onde ninguém está conversando com o assistente — está anotando
 * em fluxo, com o teclado.
 */
const ROTAS_SEM_CHAT = ['/epi/training']

function ChatFABExcetoAnotacao() {
  const { pathname } = useLocation()
  if (ROTAS_SEM_CHAT.some(r => pathname.startsWith(r))) return null
  return <ChatFAB />
}

function AppShellWrapper({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <AppShell>
      {/* Banners globais (impersonation + contexto de tenant assumido) —
          fora das rotas, visíveis em todas as telas; ocupam espaço real no
          layout via --global-banner-offset (ver GlobalBanners.tsx) */}
      <GlobalBanners />
      {/* Os dois fronts convivem (decisão do Vitor, 27/08). As rotas migradas
          montam o Shell novo; TODO o resto cai no `*` e segue no AppLayout
          antigo, com o mesmo comportamento de antes. O front antigo só sai
          quando a migração inteira estiver de pé — ver
          docs/migration/MANIFESTO-FRONT-ANTIGO.md. */}
      <Routes>
        <Route path={PREFIXO_NOVO} element={<Shell />}>{ROTAS_NOVAS}</Route>
        <Route
          path="*"
          element={
            <AppLayout user={user} onLogout={onLogout}>
              <AppRoutes />
            </AppLayout>
          }
        />
      </Routes>
      <ChatFABExcetoAnotacao />
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
