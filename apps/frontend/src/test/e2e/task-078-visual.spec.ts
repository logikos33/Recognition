/**
 * Task-078 — evidência visual do modal de detalhe do alerta (AlertsHistoryPage).
 * Tinha fundo `#1a1d23`/`#ef4444` cru; corrigido para tokens do tema
 * (`vars.color.bgElevated`/`danger`/etc). Mantido como card local (fora de
 * Dialog.Portal) de propósito — ver nota no próprio AlertsHistoryPage.tsx
 * sobre o bug de Portal + theme-scope descoberto nesta task.
 *
 * Não faz asserções funcionais: captura screenshots antes/depois da correção
 * visual (tokens WS1). Controle do prefixo via env SHOT_PREFIX=before|after.
 *
 * Uso:
 *   SHOT_PREFIX=before npx playwright test task-078-visual
 *   SHOT_PREFIX=after  npx playwright test task-078-visual
 */
import { test, type Page } from '@playwright/test'
import * as path from 'node:path'
import * as fs from 'node:fs'

const PREFIX = process.env.SHOT_PREFIX ?? 'after'
const OUT_DIR =
  process.env.EVIDENCE_DIR ??
  path.resolve(process.cwd(), '../../docs/quality/evidence/task-078')

const ALERT = {
  id: 'a1',
  camera_id: 'cam-1',
  camera_name: 'Câmera Pátio',
  violations: [{ class: 'no_helmet', confidence: 0.92 }],
  acknowledged: false,
  created_at: new Date().toISOString(),
}

async function setupRoutes(page: Page) {
  await page.route('**/api/**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: {} }),
    })
  )

  await page.route('**/alerts?**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        data: { alerts: [ALERT], total: 1, page: 1, per_page: 20, pages: 1 },
      }),
    })
  )

  await page.route('**/alerts/a1/snapshot', route =>
    route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({}) })
  )

  await page.addInitScript(() => {
    localStorage.setItem('token', 'fake-jwt-token')
    localStorage.setItem(
      'user',
      JSON.stringify({ email: 'test@test.com', role: 'admin', full_name: 'Test Admin' })
    )
  })
}

async function shoot(page: Page, name: string) {
  fs.mkdirSync(OUT_DIR, { recursive: true })
  await page.screenshot({ path: path.join(OUT_DIR, `${PREFIX}-${name}.png`), fullPage: false })
}

test.describe('task-078 evidência visual — modal de detalhe do alerta', () => {
  test('AlertsHistoryPage — abre o modal de detalhe do alerta', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/alerts')
    await page.getByText('Câmera Pátio').first().waitFor({ state: 'visible' })
    await page.getByText('Câmera Pátio').first().click()
    await page.getByText('Detalhe do Alerta').waitFor({ state: 'visible' })
    await page.waitForTimeout(400)
    await shoot(page, 'alert-detail-modal')
  })
})
