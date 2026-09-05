/**
 * A PORTA PINTA NO PRIMEIRO FRAME.
 *
 * Arquivo SEPARADO de propósito, e o motivo é a armadilha que ele existe para
 * evitar: dentro de `App.test.tsx` esta asserção passa mesmo com a porta
 * `lazy()`, porque o primeiro caso daquele arquivo (`/novo/entrar`) já resolve
 * o módulo e deixa o cache do `React.lazy` quente — os casos seguintes então
 * pintam síncrono por carona. Guarda que passa dos dois jeitos não guarda nada.
 *
 * Aqui o registro de módulos chega frio, como chega no navegador de quem abre
 * `https://<app>/` pela primeira vez.
 *
 * O que se perde sem isto: com `Entrar` sob `lazy()` + `Suspense
 * fallback={null}`, a raiz pintava `<body><div /></body>` e só mostrava a tela
 * depois de um segundo round-trip. E ficava branca PARA SEMPRE se o hash do
 * chunk não existisse mais (redeploy do Railway com aba velha aberta): o ramo
 * deslogado do `App.tsx` não tem ErrorBoundary. `pages/Login.tsx`, que atendia
 * o catch-all antes, era import estático e não tinha nenhum desses dois modos
 * de falha.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

/** jsdom desta config expõe `localStorage` OCO — ver App.test.tsx. */
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

describe('App — a porta pinta no 1º frame', () => {
  // `getByText` SÍNCRONO: nada de `findByText`. É a asserção inteira.
  it('a raiz `/` deslogada já mostra a tela NOVA sem esperar chunk', () => {
    window.history.pushState({}, '', '/')
    render(<App />)
    expect(screen.getByText('ENTRAR-NOVO')).toBeTruthy()
    expect(screen.queryByText('LOGIN-ANTIGO')).toBeNull()
  })
})
