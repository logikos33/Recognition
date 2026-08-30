/**
 * SR3 — leitura mobile <768px nas telas de LEITURA da jornada EPI.
 *
 * POR QUE ISTO É UM SPEC DE NAVEGADOR, NÃO UM `.test.ts` DE VITEST
 *
 * Vitest roda em jsdom, e jsdom NÃO calcula layout: `@media (max-width:...)`
 * nunca dispara, `scrollWidth`/`innerWidth` não refletem CSS real. Um teste de
 * unidade não prova reflow — só o navegador prova. Por isso o SR3 (coluna
 * única, zero scroll horizontal, alvos ≥44px) é verificado aqui, com Chromium
 * de verdade em viewport 390×844 (iPhone 12/13 mini — a base do handoff
 * `Mobile EPI.dc.html`, que também documenta "nada quebra até 320px").
 *
 * Sessão e API stubada seguem o mesmo padrão de `front-novo-perfis.spec.ts`:
 * sem backend, `superadmin` (passa por cima de toda permissão) evita ter que
 * escolher um papel específico só para abrir as três telas.
 */
import { expect, test, type Page } from '@playwright/test'

async function entrarComoSuperadmin(page: Page) {
  const exp = Math.floor(Date.now() / 1000) + 3600
  const b64 = (o: unknown) =>
    Buffer.from(JSON.stringify(o)).toString('base64').replace(/=+$/, '')
  const token = `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64({ exp })}.assinatura-de-teste`

  await page.addInitScript(
    ([token]) => {
      localStorage.setItem('token', token as string)
      localStorage.setItem(
        'user',
        JSON.stringify({
          id: 'u-teste',
          email: 'superadmin@teste.local',
          name: 'Teste Superadmin',
          role: 'superadmin',
          tenant_id: '00000000-0000-0000-0000-000000000001',
          tenant_schema: 'teste',
          modules: ['ppe'],
          permissions: [],
        }),
      )
    },
    [token] as const,
  )

  const envelope = (data: unknown) =>
    JSON.stringify({ success: true, message: 'OK', data })

  // Sem backend. A maioria das chamadas cai no envelope vazio — telas de
  // "vazio honesto" bastam pra medir layout e cabeçalho. Duas exceções: Ações
  // e Dashboard têm ESTADO VAZIO PRÓPRIO ("Nenhuma ação aberta", "Sem dados
  // para este módulo") sem h1 nenhum — pra chegar na tela de leitura de
  // verdade (a que o SR3 precisa provar), essas duas respostas precisam vir
  // com dado.
  await page.route('**/api/**', (rota) => {
    const url = rota.request().url()
    if (url.includes('/modules/epi/stats')) {
      return rota.fulfill({
        status: 200,
        contentType: 'application/json',
        body: envelope({ stats: { cameras_active: 4, cameras_total: 5, alerts_today: 3, alerts_week: 12 } }),
      })
    }
    if (url.includes('/alerts') && url.includes('acknowledged=false')) {
      return rota.fulfill({
        status: 200,
        contentType: 'application/json',
        body: envelope({
          alerts: [{
            id: 'a1', camera_id: 'c1', camera_name: 'CAM-01',
            violations: [{ class: 'sem_capacete' }],
            acknowledged: false, created_at: new Date().toISOString(),
          }],
          total: 1,
        }),
      })
    }
    return rota.fulfill({
      status: 200,
      contentType: 'application/json',
      body: envelope({}),
    })
  })
}

const TELAS = [
  { rota: '/novo/epi/eventos', titulo: 'Eventos' },
  { rota: '/novo/epi/acoes', titulo: 'Ações corretivas' },
  { rota: '/novo/epi/dashboard', titulo: 'Dashboard' },
]

test.describe('front novo, mobile <768 (SR3)', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  for (const { rota, titulo } of TELAS) {
    test(`${rota}: sem scroll horizontal e título legível`, async ({ page }) => {
      await entrarComoSuperadmin(page)
      await page.goto(rota)

      await expect(page.getByRole('heading', { level: 1, name: titulo })).toBeVisible()

      const semScrollHorizontal = await page.evaluate(() => {
        const raiz = document.scrollingElement
        return raiz ? raiz.scrollWidth <= window.innerWidth + 1 : true
      })
      expect(semScrollHorizontal).toBe(true)
    })
  }
})
