/**
 * Regressão da PORTA (ramo DESLOGADO).
 *
 * V1: o catch-all deslogado passou a servir a tela NOVA de login (`Entrar`).
 * Quem chega em `https://<app>/` — que é como TODO usuário chega — via a tela
 * ANTIGA, cujo `login()` sem 3º argumento cai no default `'/'` de
 * `useAuth.ts` e entrega o front ANTIGO. `Entrar` chama
 * `login(email, senha, rotaNova('/'))` e entrega o front NOVO.
 *
 * As 3 rotas nomeadas de acesso (`/novo/entrar`, `/novo/esqueci-senha`,
 * `/novo/redefinir-senha`) seguem montando suas telas, e `/forgot-password` e
 * `/reset-password` (endereços antigos, que circulam em e-mail de redefinição)
 * seguem de pé.
 *
 * As telas em si (Entrar/EsqueciSenha/RedefinirSenha) já têm teste próprio;
 * aqui o alvo é só a FIAÇÃO de rota em App.tsx.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

/**
 * O jsdom desta configuração expõe um `localStorage` OCO (objeto existe,
 * métodos não — ver `app/modulos/Modulos.test.tsx`). `AppRoutes.tsx` (via
 * `ModuleSelectionPage` → `stores/appStore.ts`) chama `localStorage.getItem`
 * NO TOPO DO MÓDULO, e `App.tsx` importa `AppRoutes` incondicionalmente — sem
 * isto, o import de `./App` abaixo derruba o arquivo de teste inteiro.
 */
const mapaStorage = new Map<string, string>()
Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: {
    getItem: (k: string) => mapaStorage.get(k) ?? null,
    setItem: (k: string, v: string) => void mapaStorage.set(k, v),
    removeItem: (k: string) => void mapaStorage.delete(k),
    clear: () => mapaStorage.clear(),
  },
})

vi.mock('./hooks/useAuth', () => ({
  useAuth: () => ({ user: null, isAuthenticated: false, logout: vi.fn() }),
}))
vi.mock('./pages/Login', () => ({ Login: () => <div>LOGIN-ANTIGO</div> }))
vi.mock('./pages/ForgotPasswordPage', () => ({ ForgotPasswordPage: () => <div>ESQUECI-ANTIGO</div> }))
vi.mock('./pages/ResetPasswordPage', () => ({ ResetPasswordPage: () => <div>REDEFINIR-ANTIGO</div> }))
vi.mock('./app/acesso/Entrar', () => ({ Entrar: () => <div>ENTRAR-NOVO</div> }))
vi.mock('./app/acesso/EsqueciSenha', () => ({ EsqueciSenha: () => <div>ESQUECI-NOVO</div> }))
vi.mock('./app/acesso/RedefinirSenha', () => ({ RedefinirSenha: () => <div>REDEFINIR-NOVO</div> }))

const App = (await import('./App')).default

/** `BrowserRouter` de dentro do App lê a URL do `window.history` no mount. */
const irPara = (caminho: string) => window.history.pushState({}, '', caminho)

describe('App — ramo deslogado (a porta)', () => {
  it('/novo/entrar monta a tela NOVA de login', async () => {
    irPara('/novo/entrar')
    render(<App />)
    expect(await screen.findByText('ENTRAR-NOVO')).toBeTruthy()
  })

  it('/novo/esqueci-senha monta a tela NOVA de recuperação', async () => {
    irPara('/novo/esqueci-senha')
    render(<App />)
    expect(await screen.findByText('ESQUECI-NOVO')).toBeTruthy()
  })

  it('/novo/redefinir-senha monta a tela NOVA de redefinição', async () => {
    irPara('/novo/redefinir-senha?token=abc')
    render(<App />)
    expect(await screen.findByText('REDEFINIR-NOVO')).toBeTruthy()
  })

  it('a raiz `/` deslogada monta a tela NOVA — é por onde o usuário entra', async () => {
    irPara('/')
    render(<App />)
    expect(await screen.findByText('ENTRAR-NOVO')).toBeTruthy()
    expect(screen.queryByText('LOGIN-ANTIGO')).toBeNull()
  })

  it('rota deslogada desconhecida cai na tela NOVA — o catch-all é a porta', async () => {
    irPara('/qualquer-coisa-que-nao-existe')
    render(<App />)
    expect(await screen.findByText('ENTRAR-NOVO')).toBeTruthy()
    expect(screen.queryByText('LOGIN-ANTIGO')).toBeNull()
  })

  it('/forgot-password e /reset-password antigos continuam de pé', () => {
    irPara('/forgot-password')
    render(<App />)
    expect(screen.getByText('ESQUECI-ANTIGO')).toBeTruthy()
  })
})
