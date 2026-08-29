/**
 * App.tsx — routing e auth gate.
 * Max 100 linhas. Rotas em AppRoutes.tsx.
 */
import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate, matchPath, useLocation } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { Login } from './pages/Login'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { AppRoutes } from './AppRoutes'
import { AppShell } from './components/layout/AppShell/AppShell'
import { AppLayout } from './components/layout/AppLayout/AppLayout'
import { ChatFAB } from './components/chat/ChatFAB'
import { GlobalBanners } from './components/layout/GlobalBanners'
import { PREFIXO_LEGADO, ROTAS_NOVAS, ROTAS_NOVAS_SEM_SHELL, rotaNova } from './app/RotasNovas'
import { Shell } from './app/shell/Shell'
import { ThemeProvider } from './theme/ThemeProvider'
import type { User } from './hooks/useAuth'

// F5 SR2 — Acesso novo, ADITIVO ao ramo deslogado. Login/ForgotPasswordPage/
// ResetPasswordPage acima seguem intocados e atendem o catch-all `*`.
const Entrar = lazy(() => import('./app/acesso/Entrar').then((m) => ({ default: m.Entrar })))
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
/**
 * Endereços REAIS das telas do shell novo — de `ROTAS_NOVAS` mesmo, não uma
 * raiz aproximada. `/modules` (`ROTAS_NOVAS_SEM_SHELL`) fica de fora de
 * propósito: a regra do ciano abaixo é do SHELL novo, e o Modulos nunca usou
 * Shell nem foi medido — incluí-lo ali era regra sem base.
 */
const ROTAS_SHELL_NOVO = ROTAS_NOVAS
  .map((r) => r.props?.path)
  .filter((p): p is string => typeof p === 'string')
  .map((p) => `/${p}`)

const ROTAS_SEM_CHAT = [
  '/epi/training',
  // DECISÃO v2 (design/DECISOES-DESIGN-2026-08-29.md, item 4): o chat
  // flutuante SAI do shell novo — fura a lei do ciano ≤10%, e medido ele
  // sozinho punha 3.136px² de ciano em TODAS as telas novas. Se o suporte
  // ficar, vira item do menu de ajuda/⌘K, e aí é desenhado.
]

function ChatFABExcetoAnotacao() {
  const { pathname } = useLocation()
  if (ROTAS_SEM_CHAT.some(r => pathname.startsWith(r))) return null
  // Sombreada ou não, é a tela do SHELL NOVO que decide — não uma raiz
  // aproximada. Isso devolve o chat às telas antigas de /epi/* que o shell
  // novo não sombreia (ex.: /epi/counting, /epi/sites), que a raiz "/epi"
  // escondia sem necessidade.
  if (ROTAS_SHELL_NOVO.some((p) => matchPath({ path: p, end: true }, pathname))) return null
  return <ChatFAB />
}

/**
 * `/novo/*` era o prefixo do front novo antes do flip (29/08). Endereço
 * salvo (favorito, link compartilhado) continua funcionando: redireciona
 * para o mesmo caminho sem o prefixo, preservando query string e hash.
 */
function RedirecionaLegado() {
  const { pathname, search, hash } = useLocation()
  return <Navigate to={(pathname.slice(PREFIXO_LEGADO.length) || '/') + search + hash} replace />
}

function AppShellWrapper({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <AppShell>
      {/* Banners globais (impersonation + contexto de tenant assumido) —
          fora das rotas, visíveis em todas as telas; ocupam espaço real no
          layout via --global-banner-offset (ver GlobalBanners.tsx) */}
      <GlobalBanners />
      {/* FLIP (decisão do Vitor, 29/08): o front novo é o padrão. As rotas
          migradas montam o Shell novo, no próprio endereço final; o que
          ainda não migrou cai no `*` e segue no AppLayout antigo, com o
          mesmo comportamento de antes. O front antigo só sai quando a
          migração inteira estiver de pé — ver
          docs/migration/MANIFESTO-FRONT-ANTIGO.md. */}
      <Routes>
        {/* Antes do Shell: estas trazem o próprio cabeçalho. */}
        {ROTAS_NOVAS_SEM_SHELL}
        <Route element={<Shell />}>{ROTAS_NOVAS}</Route>
        <Route path="/novo/*" element={<RedirecionaLegado />} />
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

// TODO(pista acesso): trocar por app/acesso quando existir
const TelaLogin = Login

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
            <Route path="*" element={<TelaLogin />} />
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
