import { test, expect } from '@playwright/test'

test('login page renders', async ({ page }) => {
  // Mock API calls — no real backend needed
  await page.route('**/api/**', route =>
    route.fulfill({ status: 401, contentType: 'application/json', body: '{"error":"unauthorized"}' })
  )

  await page.goto('/')

  await expect(page.locator('h1')).toContainText('Recognition')
  await expect(page.locator('input[type="email"]')).toBeVisible()
})
