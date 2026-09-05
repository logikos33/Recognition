/**
 * App.tsx — routing e auth gate.
 * Max 100 linhas. Rotas em AppRoutes.tsx.
 */
import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { Entrar } from './app/acesso/Entrar'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { AppRoutes } from './AppRoutes'
import { AppShell } from './components/layout/AppShell/AppShell'
import { AppLayout } from './components/layout/AppLayout/AppLayout'
import { ChatFAB } from './components/chat/ChatFAB'
import { GlobalBanners } from './components/layout/GlobalBanners'
import { PREFIXO_NOVO, ROTAS_NOVAS, ROTAS_NOVAS_SEM_SHELL, rotaNova } from './app/RotasNovas'
import { Shell } from './app/shell/Shell'
import { ThemeProvider } from './theme/ThemeProvider'
import type { User } from './hooks/useAuth'

// A PORTA: o catch-all deslogado serve `Entrar` (o antigo `pages/Login.tsx`
// chamava `login()` sem 3º arg → default '/' do useAuth → front ANTIGO). Importe
// ESTÁTICO — é a 1ª pintura de todo visitante; lazy a deixava em branco.
const EsqueciSenha = lazy(() => import('./app/acesso/EsqueciSenha').then((m) => ({ default: m.EsqueciSenha })))
const RedefinirSenha = lazy(() => import('./app/acesso/RedefinirSenha').then((m) => ({ default: m.RedefinirSenha })))

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
const ROTAS_SEM_CHAT = [
  '/epi/training',
  // DECISÃO v2 (design/DECISOES-DESIGN-2026-08-29.md, item 4): o chat
  // flutuante SAI do shell novo — fura a lei do ciano ≤10%, e medido ele
  // sozinho punha 3.136px² de ciano em TODAS as telas novas. Se o suporte
  // ficar, vira item do menu de ajuda/⌘K, e aí é desenhado.
  //
  // Sai só do front NOVO: no antigo ele continua exatamente como estava.
  PREFIXO_NOVO,
]

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
        {/* Antes do Shell: estas trazem o próprio cabeçalho. */}
        {ROTAS_NOVAS_SEM_SHELL}
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
        <Suspense fallback={null}>
          <Routes>
            <Route path={rotaNova('/entrar')} element={<Entrar />} />
            <Route path={rotaNova('/esqueci-senha')} element={<EsqueciSenha />} />
            <Route path={rotaNova('/redefinir-senha')} element={<RedefinirSenha />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="*" element={<Entrar />} />
          </Routes>
        </Suspense>
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
