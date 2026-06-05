import { test, expect } from '@playwright/test'

const OVERVIEW_MOCK = {
  status: 'success',
  data: {
    sites_total: 3,
    sites_healthy: 2,
    sites_degraded: 1,
    sites_critical: 0,
    sites_offline: 0,
    devices_total: 3,
    devices_online: 3,
    devices_offline: 0,
  },
}

const SITES_MOCK = {
  status: 'success',
  data: [
    {
      site_id: 'site-abc',
      site_name: 'Unidade Alpha',
      status: 'healthy',
      last_heartbeat: new Date().toISOString(),
      fps: 5.0,
      cameras_online: 2,
      cameras_total: 2,
    },
    {
      site_id: 'site-xyz',
      site_name: 'Unidade Beta',
      status: 'degraded',
      last_heartbeat: new Date(Date.now() - 300_000).toISOString(),
      fps: 2.3,
      cameras_online: 1,
      cameras_total: 3,
    },
  ],
}

const HEARTBEATS_MOCK = {
  status: 'success',
  data: [
    { timestamp: new Date(Date.now() - 120_000).toISOString(), fps: 5.0 },
    { timestamp: new Date(Date.now() - 60_000).toISOString(), fps: 4.9 },
  ],
}

const SUMMARY_MOCK = {
  status: 'success',
  data: {
    site_id: 'site-abc',
    avg_fps: 4.9,
    uptime_percent: 99.1,
    last_24h_heartbeats: 288,
    last_heartbeat: new Date().toISOString(),
  },
}

test.describe('EpiSitesHealthPage e2e', () => {
  test.beforeEach(async ({ page }) => {
    // Inject fake auth into localStorage so app treats user as logged in
    await page.addInitScript(() => {
      window.localStorage.setItem('token', 'fake-e2e-token')
      window.localStorage.setItem(
        'user',
        JSON.stringify({
          id: 'u1',
          email: 'e2e@test.com',
          name: 'E2E User',
          role: 'admin',
          modules: ['epi'],
        })
      )
    })

    // Mock edge endpoints
    await page.route('**/api/edge/overview', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(OVERVIEW_MOCK),
      })
    )
    await page.route('**/api/edge/sites/health', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(SITES_MOCK),
      })
    )
    await page.route('**/api/sites/*/heartbeats', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(HEARTBEATS_MOCK),
      })
    )
    await page.route('**/api/heartbeat-summary*', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(SUMMARY_MOCK),
      })
    )

    // Stub remaining API calls so nothing unexpectedly 401s
    await page.route('**/api/**', route => {
      if (!route.request().url().match(/edge\/overview|edge\/sites\/health|sites\/.*\/heartbeats|heartbeat-summary/)) {
        route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"success","data":{}}' })
      } else {
        route.continue()
      }
    })
  })

  test('loads the Sites & Saúde panel with overview cards', async ({ page }) => {
    await page.goto('/epi/sites-health')

    await expect(page.getByRole('heading', { name: /Sites.*Saúde/i })).toBeVisible({
      timeout: 8000,
    })

    await expect(page.getByText('Sites Saudáveis')).toBeVisible()
    await expect(page.getByText('Devices Online')).toBeVisible()
  })

  test('shows site rows in the table', async ({ page }) => {
    await page.goto('/epi/sites-health')

    await expect(page.getByText('Unidade Alpha')).toBeVisible({ timeout: 8000 })
    await expect(page.getByText('Unidade Beta')).toBeVisible()
    await expect(page.getByText('Saudável')).toBeVisible()
    await expect(page.getByText('Degradado')).toBeVisible()
  })

  test('clicking a row opens the detail panel with summary', async ({ page }) => {
    await page.goto('/epi/sites-health')

    await page.getByTestId('site-row-site-abc').click()

    await expect(page.getByTestId('site-detail-panel')).toBeVisible({ timeout: 6000 })
    await expect(page.getByText('Uptime')).toBeVisible()
    await expect(page.getByText('FPS Médio')).toBeVisible()
  })

  test('closing the detail panel hides it', async ({ page }) => {
    await page.goto('/epi/sites-health')

    await page.getByTestId('site-row-site-abc').click()
    await expect(page.getByTestId('site-detail-panel')).toBeVisible({ timeout: 6000 })

    await page.getByRole('button', { name: 'Fechar detalhes do site' }).click()
    await expect(page.getByTestId('site-detail-panel')).not.toBeVisible()
  })

  test('panel is accessible via keyboard (Enter key)', async ({ page }) => {
    await page.goto('/epi/sites-health')

    const row = page.getByTestId('site-row-site-abc')
    await row.waitFor({ timeout: 8000 })
    await row.focus()
    await page.keyboard.press('Enter')

    await expect(page.getByTestId('site-detail-panel')).toBeVisible({ timeout: 6000 })
  })
})
