/**
 * Smoke do harness de auditoria visual: valida boot do app mockado,
 * captura Login + Seleção de Módulos + Dashboard nos dois temas.
 */
import { test } from '@playwright/test'
import { setupApp, shootBothThemes, settle, gotoAudit } from './helpers'

test('login — default (dark + light)', async ({ page }) => {
  await setupApp(page, { auth: false })
  await gotoAudit(page, '/')
  await settle(page)
  await shootBothThemes(page, 'login', 'default')
})

test('module-selection — default (dark + light)', async ({ page }) => {
  await setupApp(page, { role: 'operator' })
  await gotoAudit(page, '/modules')
  await settle(page)
  await shootBothThemes(page, 'module-selection', 'default')
})

test('epi-dashboard — default (dark + light)', async ({ page }) => {
  await setupApp(page)
  await gotoAudit(page, '/epi/dashboard')
  await settle(page)
  await shootBothThemes(page, 'epi-dashboard', 'default')
})
