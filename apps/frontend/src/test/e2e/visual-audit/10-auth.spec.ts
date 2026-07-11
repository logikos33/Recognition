/**
 * Visual-audit — Grupo 10-auth (tier 1)
 *
 * Páginas:
 *   login            → /        (setupApp {auth:false} — qualquer rota cai na Login)
 *   module-selection → /modules (picker de módulos pós-login; sem chamadas de API)
 *
 * Estados capturados em dark + light (superfícies white-label), hover só dark.
 */
import { test, expect } from '@playwright/test'
import { setupApp, gotoAudit, settle, shoot, shootBothThemes } from './helpers'

/* ------------------------------------------------------------------ */
/* Helpers locais                                                      */
/* ------------------------------------------------------------------ */

/** Sobrescreve o user injetado pelo setupApp (roda DEPOIS na ordem de init). */
async function overrideUser(
  page: import('@playwright/test').Page,
  role: 'superadmin' | 'admin' | 'operator' | 'viewer',
  modules: string[]
) {
  await page.addInitScript(
    ([r, mods]) => {
      localStorage.setItem(
        'user',
        JSON.stringify({
          id: 'u-audit-1',
          email: 'auditor@recognition.dev',
          name: 'Auditor Visual',
          role: r,
          tenant_id: '00000000-0000-0000-0000-000000000001',
          modules: mods,
        })
      )
    },
    [role, modules] as const
  )
}

async function gotoLogin(page: import('@playwright/test').Page) {
  await gotoAudit(page, '/')
  await expect(page.getByRole('heading', { name: 'Recognition' })).toBeVisible()
  await expect(page.getByText('Visão computacional industrial')).toBeVisible()
}

async function fillLogin(page: import('@playwright/test').Page) {
  await page.getByPlaceholder('seu@email.com').fill('mariana.souza@rvbindustrial.com.br')
  await page.getByPlaceholder('••••••••').fill('Recognition@2026!')
}

/* ------------------------------------------------------------------ */
/* LOGIN — /                                                           */
/* ------------------------------------------------------------------ */

test('login — default (tab Entrar)', async ({ page }) => {
  await setupApp(page, { auth: false })
  await gotoLogin(page)
  await expect(page.getByText('Acesso padrão')).toBeVisible()
  await settle(page)
  await shootBothThemes(page, 'login', 'default')
})

test('login — tab Criar Conta', async ({ page }) => {
  await setupApp(page, { auth: false })
  await gotoLogin(page)
  // No estado inicial só existe UM botão "Criar Conta" (a aba)
  await page.getByRole('button', { name: 'Criar Conta' }).click()
  await expect(page.getByPlaceholder('Confirmar senha')).toBeVisible()
  await settle(page)
  await shootBothThemes(page, 'login', 'tab-register')
})

test('login — erro de validação (senhas não coincidem)', async ({ page }) => {
  await setupApp(page, { auth: false })
  await gotoLogin(page)
  await page.getByRole('button', { name: 'Criar Conta' }).click()
  await page.getByPlaceholder('Nome completo').fill('Mariana Souza')
  await page.getByPlaceholder('seu@email.com').fill('mariana.souza@rvbindustrial.com.br')
  await page.getByPlaceholder('••••••••').fill('Recognition@2026!')
  await page.getByPlaceholder('Confirmar senha').fill('Recognition2026')
  await page.locator('button[type="submit"]').click()
  await expect(page.getByText('As senhas não coincidem')).toBeVisible()
  await settle(page)
  await shootBothThemes(page, 'login', 'error')
})

test('login — erro da API (credenciais inválidas, 401)', async ({ page }) => {
  await setupApp(page, {
    auth: false,
    raw: {
      '**/api/auth/login**': {
        status: 401,
        body: { status: 'error', error: 'Credenciais inválidas' },
      },
    },
  })
  await gotoLogin(page)
  await fillLogin(page)
  await page.locator('button[type="submit"]').click()
  await expect(page.getByText('Credenciais inválidas')).toBeVisible()
  await settle(page)
  await shootBothThemes(page, 'login', 'error-api')
})

test('login — loading (autenticando, request pendente)', async ({ page }) => {
  await setupApp(page, {
    auth: false,
    stall: ['**/api/auth/login**'],
  })
  await gotoLogin(page)
  await fillLogin(page)
  await page.locator('button[type="submit"]').click()
  await expect(page.getByRole('button', { name: 'Aguarde...' })).toBeVisible()
  // settle esperaria networkidle com request pendurada — usar delay curto direto
  await page.waitForTimeout(600)
  await shootBothThemes(page, 'login', 'loading')
})

test('login — hovers (dark)', async ({ page }) => {
  await setupApp(page, { auth: false })
  await gotoLogin(page)
  await settle(page)
  // Hover no CTA principal
  await page.locator('button[type="submit"]').hover()
  await page.waitForTimeout(300)
  await shoot(page, 'login', 'hover-submit')
  // Hover na aba inativa "Criar Conta"
  await page.getByRole('button', { name: 'Criar Conta' }).hover()
  await page.waitForTimeout(300)
  await shoot(page, 'login', 'hover-tab-register')
})

/* ------------------------------------------------------------------ */
/* MODULE SELECTION — /modules                                         */
/* ------------------------------------------------------------------ */

async function gotoModules(page: import('@playwright/test').Page) {
  await gotoAudit(page, '/modules')
  await expect(page.getByRole('heading', { name: 'Selecione o Módulo' })).toBeVisible()
}

test('module-selection — default (operator, todos os módulos ativos)', async ({ page }) => {
  await setupApp(page, { role: 'operator' })
  await gotoModules(page)
  await expect(page.getByRole('button', { name: 'Acessar módulo EPI' })).toBeVisible()
  await settle(page)
  await shootBothThemes(page, 'module-selection', 'default')
})

test('module-selection — operator com só EPI (cards "Em breve")', async ({ page }) => {
  await setupApp(page, { role: 'operator' })
  await overrideUser(page, 'operator', ['epi'])
  await gotoModules(page)
  await expect(page.getByText('Em breve').first()).toBeVisible()
  await settle(page)
  await shootBothThemes(page, 'module-selection', 'modules-limited')
})

test('module-selection — superadmin (fueling ativo por override de role)', async ({ page }) => {
  await setupApp(page, { role: 'superadmin' })
  // Só módulo epi no tenant: Carregamento fica ativo mesmo assim (override superadmin),
  // Qualidade cai para "Em breve" — evidencia a diferença por role.
  await overrideUser(page, 'superadmin', ['epi'])
  await gotoModules(page)
  await expect(
    page.getByRole('button', { name: 'Acessar módulo Controle de Carregamento' })
  ).toBeVisible()
  await expect(page.getByText('Em breve').first()).toBeVisible()
  await settle(page)
  await shootBothThemes(page, 'module-selection', 'role-superadmin')
})

test('module-selection — hovers (dark)', async ({ page }) => {
  await setupApp(page, { role: 'operator' })
  await gotoModules(page)
  await settle(page)
  await page.getByRole('button', { name: 'Acessar módulo EPI' }).hover()
  await page.waitForTimeout(300)
  await shoot(page, 'module-selection', 'hover-card-epi')
  await page
    .getByRole('button', { name: 'Acessar módulo Qualidade Industrial' })
    .hover()
  await page.waitForTimeout(300)
  await shoot(page, 'module-selection', 'hover-card-quality')
})
