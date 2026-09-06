/**
 * A RAIZ `/` COM O USUÁRIO LOGADO (#762).
 *
 * `/` é o endereço que a pessoa digita quando reabre o produto no dia
 * seguinte — e é também para onde `assumeTenantContext`/`startImpersonation`
 * recarregavam a página (#760). Deslogado ele já estava certo desde a V1
 * (pinta `Entrar`, a tela nova, com teste em `App.porta.test.tsx`); LOGADO
 * não havia teste nenhum, e o `RootRedirect` mandava para `/admin`
 * (superadmin) ou `/modules` — os dois no front ANTIGO, medido por clique no
 * DEV em 05/09.
 *
 * O teste CRUZA O ROTEADOR, que é a fronteira que vale aqui: monta a mesma
 * árvore que `App.tsx` monta (prefixo novo primeiro, front antigo no `*`) e
 * afirma em que endereço a pessoa PARA. Afirmar o retorno de
 * `rotaHomeDoUsuario()` não provaria nada — o `RootRedirect` poderia
 * continuar ignorando a função.
 *
 * Este arquivo também é o que sustenta a exceção `'/'` de
 * `coexistencia.test.tsx`: enquanto ele estiver verde, `'/'` não é um
 * endereço do front antigo.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

/**
 * O jsdom desta configuração expõe um `localStorage` OCO (o objeto existe, os
 * métodos não — ver `App.test.tsx`). `AppRoutes.tsx` chama
 * `localStorage.getItem` NO TOPO DO MÓDULO (via `ModuleSelectionPage` →
 * `stores/appStore.ts`); sem isto o import abaixo derruba o arquivo inteiro.
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

const papel = vi.hoisted(() => ({ superadmin: true }))
vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 'u1', tenant_id: 't1' },
    isAuthenticated: true,
    isSuperAdmin: papel.superadmin,
    isAdmin: false,
    can: () => true,
    logout: vi.fn(),
  }),
}))

const { AppRoutes } = await import('../AppRoutes')
const { PREFIXO_NOVO } = await import('./RotasNovas')

/** Só existe para dizer em que endereço do front NOVO a navegação parou. */
function SondaDoFrontNovo() {
  return <div>NOVO:{useLocation().pathname}</div>
}

/**
 * A MESMA fiação de `App.tsx` (ramo logado): o prefixo novo ganha, o front
 * antigo atende o `*`. O front novo entra como sonda em vez do `Shell` real —
 * o que se mede aqui é o DESTINO, não a tela.
 */
function monta(url: string) {
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path={`${PREFIXO_NOVO}/*`} element={<SondaDoFrontNovo />} />
        <Route path="*" element={<AppRoutes />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('a raiz logada não entrega o front antigo', () => {
  it('superadmin em `/` para no painel admin NOVO', () => {
    papel.superadmin = true
    monta('/')
    expect(screen.getByText('NOVO:/novo/admin')).toBeTruthy()
  })

  it('quem não é superadmin em `/` para na escolha de módulo NOVA', () => {
    papel.superadmin = false
    monta('/')
    expect(screen.getByText('NOVO:/novo/modules')).toBeTruthy()
  })

  it('endereço antigo inexistente também para no front novo, não no antigo', () => {
    // O `RootRedirect` atende `/` E o catch-all deste roteador. Digitar um
    // endereço morto do produto velho não pode ser a porta dos fundos que
    // devolve a pessoa ao produto velho.
    papel.superadmin = true
    monta('/rota-que-nao-existe')
    expect(screen.getByText('NOVO:/novo/admin')).toBeTruthy()
  })
})
