/**
 * Warmup — roda PRIMEIRO (ordem alfabética, workers=1).
 * Pré-compila o import graph do Vite dev (entry + chunks lazy: Admin, Quality,
 * DesignSystem, Tablet) pra nenhum teste seguinte pagar o cold-compile.
 */
import { test } from '@playwright/test'
import { setupApp } from './helpers'

test('warmup vite dev server', async ({ page }) => {
  test.setTimeout(300_000)
  await setupApp(page, { auth: false })
  await page.goto('/', { waitUntil: 'load', timeout: 240_000 })

  await setupApp(page, { role: 'superadmin' })
  for (const route of ['/epi/dashboard', '/admin', '/quality/dashboard', '/design-system']) {
    await page.goto(route, { waitUntil: 'load', timeout: 120_000 })
    await page.waitForTimeout(500)
  }
})
