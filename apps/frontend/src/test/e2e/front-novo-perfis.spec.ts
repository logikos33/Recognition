/**
 * O front novo visto por CADA PAPEL — no navegador, não em jsdom.
 *
 * POR QUE ESTE ARQUIVO EXISTE
 *
 * A navegação do shell novo é derivada de PERMISSÃO, não de nome de perfil: o
 * desenho supõe 4 perfis e o backend tem 6. Os testes de unidade conferem que
 * cada chave existe no registry e que `navVisivel` filtra. O que eles NÃO
 * provam é o produto montado: com o Shell, o roteador, o CSS e o `can()` real
 * lendo o `user` do localStorage.
 *
 * Na rodada da migração, o produto só foi aberto de olho por um SUPERADMIN — que
 * é justamente o papel que passa por cima de toda permissão e, por isso, nunca
 * vê o que os outros veem. Este arquivo fecha esse buraco.
 *
 * A MATRIZ É A DO BACKEND, não uma suposição: `matriz-papeis.json` é gerada de
 * `services/api/app/core/permissions.py` (via `permissions_for_role`). Se alguém
 * mudar quem pode o quê lá e não aqui, o teste fica vermelho — que é o ponto.
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test, type Page } from '@playwright/test'

/**
 * Lido do disco em vez de `import ... from './matriz-papeis.json'`: o ESM do
 * Node exige atributo de importação para JSON, e a forma exigida varia com a
 * versão. Ler o arquivo funciona em todas, e deixa explícito que a matriz é um
 * ARTEFATO GERADO do backend — não uma constante que alguém edita aqui.
 */
const AQUI = dirname(fileURLToPath(import.meta.url))
const MATRIZ: Record<string, string[]> = JSON.parse(
  readFileSync(join(AQUI, 'matriz-papeis.json'), 'utf-8'),
)

/** O menu do módulo EPI e a permissão que cada item exige (navPorPerfil.ts). */
const MENU: Array<{ rotulo: string; permissao: string | null }> = [
  { rotulo: 'Dashboard', permissao: null },
  { rotulo: 'Ao Vivo', permissao: 'cameras:read' },
  { rotulo: 'Eventos', permissao: 'alerts:read' },
  { rotulo: 'Verificação', permissao: 'verification:read' },
  { rotulo: 'Ações', permissao: 'alerts:read' },
  { rotulo: 'Câmeras', permissao: 'cameras:read' },
  { rotulo: 'Relatórios', permissao: 'reports:read' },
  // F5 PR-A: grupo Estúdio concatenado DEPOIS do EPI no Shell — último no DOM.
  { rotulo: 'Estúdio', permissao: 'frames:annotate' },
  // F5 SR2 PR-1: grupo Admin concatenado por último — só o superadmin vê.
  { rotulo: 'Administração', permissao: 'admin:panel' },
]

/** O que o menu DEVE mostrar para um papel, derivado da matriz do backend. */
function menuEsperado(papel: string): string[] {
  const permissoes = new Set(MATRIZ[papel] ?? [])
  // superadmin passa por cima de tudo (useAuth.can), inclusive do que a matriz diz
  const pode = (p: string) => papel === 'superadmin' || permissoes.has(p)
  return MENU.filter((i) => i.permissao === null || pode(i.permissao)).map((i) => i.rotulo)
}

/**
 * Sessão sem rede: o `can()` do produto lê `user.permissions` do localStorage,
 * então é ali que o papel entra. O token é um JWT de forma válida com `exp` no
 * futuro — o Shell lê o claim para decidir se avisa que a sessão vai expirar, e
 * um token ilegível faria o aviso sumir por motivo errado.
 */
async function entrarComo(page: Page, papel: string) {
  const permissoes = MATRIZ[papel] ?? []
  const exp = Math.floor(Date.now() / 1000) + 3600
  const b64 = (o: unknown) =>
    Buffer.from(JSON.stringify(o)).toString('base64').replace(/=+$/, '')
  const token = `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64({ exp })}.assinatura-de-teste`

  await page.addInitScript(
    ([papel, permissoes, token]) => {
      localStorage.setItem('token', token as string)
      localStorage.setItem(
        'user',
        JSON.stringify({
          id: 'u-teste',
          email: `${papel}@teste.local`,
          name: `Teste ${papel}`,
          role: papel,
          tenant_id: '00000000-0000-0000-0000-000000000001',
          tenant_schema: 'teste',
          modules: ['ppe'],
          permissions: permissoes,
        }),
      )
    },
    [papel, permissoes, token] as const,
  )

  // Sem backend: toda chamada devolve envelope válido e vazio. As telas caem no
  // vazio honesto, que é o suficiente para o menu montar — é o menu que está
  // sob teste aqui, não o conteúdo.
  await page.route('**/api/**', (rota) =>
    rota.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, message: 'OK', data: {} }),
    }),
  )
}

const PAPEIS = Object.keys(MATRIZ)

test.describe('front novo, por papel', () => {
  for (const papel of PAPEIS) {
    test(`${papel}: o menu mostra exatamente o que a permissão permite`, async ({ page }) => {
      await entrarComo(page, papel)
      await page.goto('/novo/epi/dashboard')

      const nav = page.getByRole('navigation', { name: 'Navegação principal' })
      await expect(nav).toBeVisible()

      const visiveis = (await nav.getByRole('link').allTextContents()).map((t) => t.trim())
      expect(visiveis).toEqual(menuEsperado(papel))
    })

    test(`${papel}: nenhum link do menu escapa do front novo`, async ({ page }) => {
      // Regressão de 27/08: 10 links absolutos levavam, calados, para a tela
      // ANTIGA de mesmo endereço. Aqui é o produto montado que responde.
      await entrarComo(page, papel)
      await page.goto('/novo/epi/dashboard')

      const hrefs = await page
        .getByRole('navigation', { name: 'Navegação principal' })
        .getByRole('link')
        .evaluateAll((as) => as.map((a) => a.getAttribute('href') ?? ''))

      for (const href of hrefs) expect(href).toMatch(/^\/novo\//)
    })
  }

  test('quem não tem verification:read não alcança a fila pelo menu', async ({ page }) => {
    // `viewer` é o caso real: tem alerts:read e reports:read, NÃO tem
    // verification:read. Se um dia a Verificação aparecer para ele, é porque
    // alguém trocou a chave — e é exatamente o erro que já quase aconteceu
    // (`alerts:review`, que não existe).
    expect(MATRIZ.viewer).not.toContain('verification:read')

    await entrarComo(page, 'viewer')
    await page.goto('/novo/epi/dashboard')

    const nav = page.getByRole('navigation', { name: 'Navegação principal' })
    await expect(nav.getByRole('link', { name: 'Verificação' })).toHaveCount(0)
    await expect(nav.getByRole('link', { name: 'Eventos' })).toHaveCount(1)
  })
})
