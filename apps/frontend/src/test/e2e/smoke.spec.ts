import { test, expect } from '@playwright/test'

test('login page renders', async ({ page }) => {
  // Mock API calls — no real backend needed
  await page.route('**/api/**', route =>
    route.fulfill({ status: 401, contentType: 'application/json', body: '{"error":"unauthorized"}' })
  )

  await page.goto('/')

  // A porta passou a servir a tela NOVA de login (`app/acesso/Entrar`) — PR #659.
  await expect(page.locator('h1')).toContainText('Entrar')
  await expect(page.locator('input[type="email"]')).toBeVisible()
})
