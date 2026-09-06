/**
 * OS ENDEREÇOS QUE SOBRARAM (#762).
 *
 * A raiz `/` foi consertada no #808. Das 22 rotas que, com o usuário LOGADO,
 * ainda entregavam o front ANTIGO, este arquivo cobre as que JÁ TÊM
 * substituta montada em `ROTAS_NOVAS` — e, tão importante quanto, as que NÃO
 * têm e por isso continuam servindo a tela velha de propósito.
 *
 * O CRITÉRIO PARA REDIRECIONAR, e por que ele não é "existe tela parecida":
 *
 *   Cada tela antiga superada carrega, no próprio topo do arquivo, um
 *   `@migrado-para` e — quando a substituta AINDA NÃO FAZ TUDO — um
 *   `@paridade-pendente` nomeando o que se perderia. Redirecionar é tirar o
 *   endereço da tela antiga; com `@paridade-pendente` isso apaga função que
 *   só existe lá (criar estação do gate, iniciar uma contagem, editar a
 *   câmera do módulo). Por isso o de-para abaixo só inclui substituta SEM
 *   pendência declarada. As pendentes ficam listadas no bloco negativo, que
 *   é parte da prova: silêncio não distingue "não redirecionei porque
 *   quebraria" de "esqueci".
 *
 * O teste CRUZA O ROTEADOR (mesma fiação de `App.tsx`: prefixo novo primeiro,
 * front antigo no `*`) e afirma EM QUE ENDEREÇO a pessoa para — com query e
 * hash, que é o que um link de e-mail e um filtro salvo carregam.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

/**
 * `localStorage` OCO do jsdom desta configuração (ver `App.test.tsx`):
 * `AppRoutes.tsx` alcança `stores/appStore.ts`, que lê no TOPO do módulo.
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
    hasModule: () => true,
    logout: vi.fn(),
  }),
}))

const { AppRoutes } = await import('../AppRoutes')
const { PREFIXO_NOVO } = await import('./RotasNovas')

/** Diz o endereço INTEIRO onde a navegação parou dentro do front novo. */
function SondaDoFrontNovo() {
  const { pathname, search, hash } = useLocation()
  return <div>{`NOVO:${pathname}${search}${hash}`}</div>
}

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

/**
 * O de-para. Escrito à mão aqui de propósito: é a ESPECIFICAÇÃO, não um eco
 * da tabela do código — teste que importa a tabela que ele deveria conferir
 * passa mesmo com a tabela errada.
 */
const REDIRECIONADAS: Array<[antiga: string, nova: string]> = [
  // `Modulos.tsx` é a escolha de módulo nova, e `rotaHomeDoUsuario(false)` já
  // manda `/` para lá desde o #808 — `/modules` ia para a tela velha.
  ['/modules', '/novo/modules'],
  // `ReportsPage.tsx`: `@migrado-para app/epi/Relatorios.tsx`, sem pendência
  // (a antiga é literalmente um placeholder de 31 linhas).
  ['/epi/reports', '/novo/epi/relatorios'],
  // `TrainingPage.tsx` e `ModuleClassesPage.tsx`: `MIGRADO`, paridade fechada
  // em 30/08 (PRs #572/#574/#577/#580/#583/#586).
  ['/epi/training', '/novo/estudio'],
  ['/epi/training/classes', '/novo/estudio/classes'],
  ['/training', '/novo/estudio'],
  ['/annotation', '/novo/estudio'],
  ['/module-classes', '/novo/estudio/classes'],
]

/** As de `/admin/*`, atrás do MESMO gate `AdminRoute` de hoje. */
const REDIRECIONADAS_ADMIN: Array<[antiga: string, nova: string]> = [
  ['/admin', '/novo/admin'],
  ['/admin/tenants', '/novo/admin/tenants'],
  ['/admin/users', '/novo/admin/usuarios'],
]

describe('endereços antigos com substituta pronta caem no front novo', () => {
  it.each([...REDIRECIONADAS, ...REDIRECIONADAS_ADMIN])(
    '%s → %s',
    (antiga, nova) => {
      papel.superadmin = true
      monta(antiga)
      expect(screen.getByText(`NOVO:${nova}`)).toBeTruthy()
    },
  )

  it.each([...REDIRECIONADAS, ...REDIRECIONADAS_ADMIN])(
    '%s preserva query e hash',
    (antiga, nova) => {
      papel.superadmin = true
      monta(`${antiga}?de=2026-09-01&camera=7#linha-3`)
      expect(
        screen.getByText(`NOVO:${nova}?de=2026-09-01&camera=7#linha-3`),
      ).toBeTruthy()
    },
  )

  it.each(REDIRECIONADAS_ADMIN.map(([antiga]) => antiga))(
    '%s: quem NÃO é superadmin continua sendo barrado pelo AdminRoute, como antes',
    (antiga) => {
      // Os redirects do Admin ficam DENTRO do `<Route element={<AdminRoute />}>`
      // justamente para isto: o papel decide primeiro, o redirect depois. Fora
      // do gate, um operador digitando `/admin/tenants` bateria no
      // `SemPermissao` do painel novo — que confirma que a rota existe.
      // `AdminRoute` manda para `/`, que o `RootRedirect` resolve por papel.
      papel.superadmin = false
      monta(antiga)
      expect(screen.getByText('NOVO:/novo/modules')).toBeTruthy()
    },
  )
})

/**
 * O outro lado da prova. Cada um destes tem substituta no front novo — e
 * continua servindo a tela ANTIGA porque a substituta perde função nomeada no
 * `@paridade-pendente` do próprio arquivo. Redirecionar aqui não seria
 * migração, seria remoção silenciosa.
 */
const NAO_REDIRECIONAM: Array<[rota: string, porque: string]> = [
  ['/quality/config', 'criar/editar estação e salvar config do gate só existem na antiga'],
  ['/quality/cameras', 'editar config da câmera e atribuir/remover câmera do módulo'],
  ['/quality/inspections', 'filtros (resultado, feedback, período, ordem) e paginação'],
  ['/epi/counting', 'iniciar contagem (POST /counting/sessions)'],
  ['/admin/tenants/abc-123', 'é onde vive o UserPermissionsDrawer, sem equivalente no novo'],
  ['/epi/investigation', 'SEM-DESENHO: não existe tela nova'],
  ['/epi/sites', 'SEM-DESENHO: não existe tela nova'],
]

describe('endereço sem substituta completa continua no front antigo', () => {
  it.each(NAO_REDIRECIONAM)('%s fica onde está (%s)', (rota) => {
    papel.superadmin = true
    monta(rota)
    expect(screen.queryByText(/^NOVO:/)).toBeNull()
  })
})
