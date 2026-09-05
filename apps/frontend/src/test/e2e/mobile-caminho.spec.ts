/**
 * ONDA 2 (celular) — o CAMINHO dos 3 usuários da RVB em 375px.
 *
 * Por que navegador e não vitest: jsdom não calcula layout — `@media` nunca
 * dispara e `getBoundingClientRect()` devolve zero. O mesmo motivo já escrito
 * em `front-novo-mobile.spec.ts`; este spec é o irmão dele com a régua que
 * faltava.
 *
 * O QUE ELE MEDE, e por que essa régua e não "sem scroll horizontal".
 *
 * `front-novo-mobile.spec.ts` já garante que a página não rola de lado — e
 * PASSAVA com a tela inutilizável: a barra lateral do shell tem
 * `width: 236px; flex-shrink: 0`, então em 375px ela comia 63% da largura e
 * sobravam 91px de conteúdo (375 − 236 − 48 de padding). Nada estourava a
 * viewport porque o `<main>` é `flex: 1; min-width: 0` e simplesmente encolhia.
 * Zero scroll horizontal, zero legibilidade.
 *
 * A régua aqui é a LARGURA ÚTIL do conteúdo: `<main>` tem de sobrar com pelo
 * menos 320px de área interna em 375px de viewport. É o número que separa
 * "cabe" de "coube porque espremeu".
 */
import fs from 'node:fs'
import path from 'node:path'

import { expect, test, type Page } from '@playwright/test'

/** iPhone SE / base do handoff "nada quebra até 320px" com folga de 55px. */
const LARGURA = 375
const ALTURA = 812

/**
 * Piso da largura útil. 375 − 2×16px de padding lateral = 343; 320 deixa
 * margem para o padding não virar régua e ainda reprova qualquer volta da
 * barra lateral fixa (que deixava 91px).
 */
const LARGURA_UTIL_MINIMA = 320

const DESTINO = process.env.CAPTURA_DIR

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

  const envelope = (data: unknown) => JSON.stringify({ success: true, message: 'OK', data })
  const agora = new Date().toISOString()
  const alerta = {
    id: 'a1',
    camera_id: 'c1',
    camera_name: 'CAM-01 · Expedição',
    violations: [{ class: 'sem_capacete', confidence: 0.91, bbox: [40, 30, 120, 200] }],
    acknowledged: false,
    created_at: agora,
    captured_at: agora,
    evidence_url: null,
  }

  await page.route('**/api/**', (rota) => {
    const url = rota.request().url()
    const corpo = (data: unknown) =>
      rota.fulfill({ status: 200, contentType: 'application/json', body: envelope(data) })

    if (url.includes('/modules/epi/stats')) {
      return corpo({
        stats: { cameras_active: 4, cameras_total: 5, alerts_today: 3, alerts_week: 12 },
      })
    }
    if (/\/alerts\/[^/?]+(\?|$)/.test(url)) return corpo({ alert: alerta, ...alerta })
    if (url.includes('/alerts')) return corpo({ alerts: [alerta], total: 1 })
    if (url.includes('/cameras')) {
      return corpo({
        cameras: [
          { id: 'c1', name: 'CAM-01 · Expedição', is_active: true, status: 'online' },
          { id: 'c2', name: 'CAM-02 · Pátio', is_active: true, status: 'online' },
          { id: 'c3', name: 'CAM-03 · Doca', is_active: true, status: 'online' },
          { id: 'c4', name: 'CAM-04 · Corte', is_active: true, status: 'online' },
        ],
        total: 4,
      })
    }
    return corpo({})
  })
}

const TELAS = [
  { arquivo: '1-dashboard', rota: '/novo/epi/dashboard' },
  { arquivo: '2-eventos', rota: '/novo/epi/eventos' },
  { arquivo: '3-evento-detalhe', rota: '/novo/epi/eventos/a1' },
  { arquivo: '4-acoes', rota: '/novo/epi/acoes' },
  { arquivo: '5-ao-vivo', rota: '/novo/epi/live' },
]

test.describe('caminho do TST em 375px', () => {
  test.use({ viewport: { width: LARGURA, height: ALTURA } })

  for (const { arquivo, rota } of TELAS) {
    test(`${rota}: conteúdo com largura útil e sem scroll horizontal`, async ({ page }) => {
      await entrarComoSuperadmin(page)
      await page.goto(rota)
      await page.locator('main').waitFor()
      // O conteúdo é preguiçoso (`lazy()`); sem isto a medida sai do loader.
      await page.waitForTimeout(1200)

      if (DESTINO) {
        fs.mkdirSync(DESTINO, { recursive: true })
        await page.screenshot({
          path: path.join(DESTINO, `${arquivo}.png`),
          fullPage: true,
        })
      }

      const medida = await page.evaluate(() => {
        const main = document.querySelector('main') as HTMLElement | null
        const raiz = document.scrollingElement
        const estilo = main ? getComputedStyle(main) : null
        return {
          util: main
            ? main.getBoundingClientRect().width -
              parseFloat(estilo!.paddingLeft) -
              parseFloat(estilo!.paddingRight)
            : 0,
          scroll: raiz ? raiz.scrollWidth : 0,
          janela: window.innerWidth,
        }
      })

      expect(medida.util, 'largura útil do <main>').toBeGreaterThanOrEqual(LARGURA_UTIL_MINIMA)
      expect(medida.scroll, 'scrollWidth da página').toBeLessThanOrEqual(medida.janela + 1)
    })
  }

  /**
   * A adaptação não pode ser "some com o menu": sem navegação, o operador que
   * abre um evento no chão de fábrica não tem como voltar para a lista. E não
   * basta a barra existir — a faixa horizontal só é navegação se ROLAR: os
   * itens do fim (Ações, Relatórios) ficam fora dos 375px iniciais, e uma
   * faixa com `overflow: hidden` os deixaria inalcançáveis, que é o mesmo
   * beco com outra roupa.
   */
  test('a navegação principal continua alcançável — e rolável — em 375px', async ({ page }) => {
    await entrarComoSuperadmin(page)
    await page.goto('/novo/epi/dashboard')
    const nav = page.getByRole('navigation', { name: 'Navegação principal' })
    await expect(nav).toBeVisible()
    await expect(nav.getByRole('link', { name: 'Eventos' })).toBeVisible()

    // A faixa cabe na tela e o excedente rola DENTRO dela.
    const faixa = await nav.evaluate((el) => ({
      largura: el.clientWidth,
      conteudo: el.scrollWidth,
      rolavel: getComputedStyle(el).overflowX,
    }))
    expect(faixa.largura).toBeLessThanOrEqual(LARGURA)
    expect(faixa.conteudo).toBeGreaterThan(faixa.largura)
    expect(faixa.rolavel).toBe('auto')

    // E o item do fim do caminho do TST chega de verdade ao alcance do dedo.
    const acoes = nav.getByRole('link', { name: 'Ações' })
    await acoes.scrollIntoViewIfNeeded()
    await expect(acoes).toBeInViewport()
  })
  /**
   * O SINO — o overlay que a régua acima estruturalmente não enxerga.
   *
   * As medidas de `<main>` não alcançam o painel de notificações: ele é
   * `position: fixed`, portanto sai do fluxo e não entra na largura útil. E o
   * `scrollWidth` também não o pega, porque ele vaza para a ESQUERDA (`right`
   * ancorado, largura fixa) e overflow negativo não gera rolagem. É o MESMO
   * modo de falha que este arquivo denuncia no `front-novo-mobile.spec.ts`:
   * verde com a tela quebrada.
   *
   * Medido antes de consertar, com o painel aberto de verdade:
   *
   *     375px → left = −1px      360px → left = −16px     320px → left = −56px
   *
   * O sino está no caminho: é `can('alerts:read')` — a mesma permissão do item
   * "Eventos" — e o clique nele é o atalho do TST para o evento. Cortado à
   * esquerda, o que some é o começo de cada linha (ícone e nome da câmera).
   */
  for (const largura of [375, 360, 320]) {
    test(`o painel do sino cabe inteiro em ${largura}px`, async ({ page }) => {
      await page.setViewportSize({ width: largura, height: ALTURA })
      await entrarComoSuperadmin(page)
      await page.goto('/novo/epi/dashboard')
      await page.getByRole('button', { name: 'Notificações' }).click()

      const titulo = page.getByText('Notificações', { exact: true })
      await expect(titulo).toBeVisible()
      const caixa = await titulo.evaluate((el) => {
        // O painel é o ancestral posicionado do título.
        let no = el.parentElement
        while (no && getComputedStyle(no).position !== 'fixed') no = no.parentElement
        const r = no!.getBoundingClientRect()
        return { esquerda: r.left, direita: r.right, janela: window.innerWidth }
      })

      expect(caixa.esquerda, 'borda esquerda do painel do sino').toBeGreaterThanOrEqual(0)
      expect(caixa.direita, 'borda direita do painel do sino').toBeLessThanOrEqual(caixa.janela)
    })
  }
})
