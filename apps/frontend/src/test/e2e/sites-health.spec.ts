import { test, expect } from '@playwright/test'

// ---------------------------------------------------------------------------
// Backend-accurate mock payloads (field names match routes.py serialization)
// ---------------------------------------------------------------------------

const OVERVIEW_MOCK = {
  status: 'success',
  data: {
    sites_total: 3,
    sites_por_status: { active: 2, inactive: 0, maintenance: 1 },
    devices_total: 3,
    devices_online: 3,
    devices_revoked: 0,
    sites_offline: 1,
  },
}

const SITES_MOCK = {
  status: 'success',
  data: {
    sites: [
      {
        site_id: 'site-abc',
        name: 'Unidade Alpha',          // backend field: 'name' (not 'site_name')
        deployment_mode: 'standalone',
        derived_status: 'healthy',      // backend field: 'derived_status' (not 'status')
        last_heartbeat_at: new Date().toISOString(),  // backend field: 'last_heartbeat_at'
        inference_fps: 5.0,             // backend field: 'inference_fps' (not 'fps')
        cameras_online: 2,
        cameras_total: 2,
        cpu_pct: 30.0,
      },
      {
        site_id: 'site-xyz',
        name: 'Unidade Beta',
        deployment_mode: 'standalone',
        derived_status: 'degraded',
        last_heartbeat_at: new Date(Date.now() - 300_000).toISOString(),
        inference_fps: 2.3,
        cameras_online: 1,
        cameras_total: 3,
        cpu_pct: 60.0,
      },
    ],
  },
}

const HEARTBEATS_MOCK = {
  status: 'success',
  data: {
    heartbeats: [
      {
        id: 'hb-1',
        received_at: new Date(Date.now() - 120_000).toISOString(),  // backend: 'received_at'
        inference_fps: 5.0,   // backend: 'inference_fps'
        cpu_pct: 30.0,        // backend: 'cpu_pct'
        cameras_online: 2,
      },
      {
        id: 'hb-2',
        received_at: new Date(Date.now() - 60_000).toISOString(),
        inference_fps: 4.9,
        cpu_pct: 28.0,
        cameras_online: 2,
      },
    ],
  },
}

const SUMMARY_MOCK = {
  status: 'success',
  data: {
    site_id: 'site-abc',
    heartbeat_count: 288,             // backend: 'heartbeat_count' (not 'last_24h_heartbeats')
    avg_inference_fps: 4.9,           // backend: 'avg_inference_fps' (not 'avg_fps')
    uptime_pct: 99.1,                 // backend: 'uptime_pct' (not 'uptime_percent')
    last_received_at: new Date().toISOString(),  // backend: 'last_received_at'
    derived_status: 'healthy',
  },
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe('EpiSitesHealthPage e2e', () => {
  test.beforeEach(async ({ page }) => {
    // Inject admin auth into localStorage
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

    // Playwright uses LIFO: catch-all registered FIRST has lowest priority.
    // Specific routes registered below override it.
    await page.route('**/api/**', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"success","data":{}}' })
    )

    // Specific edge mocks — registered last → checked first (LIFO)
    await page.route('**/api/v1/edge/overview', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(OVERVIEW_MOCK),
      })
    )
    await page.route('**/api/v1/edge/sites/health', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(SITES_MOCK),
      })
    )
    await page.route('**/api/v1/edge/sites/*/heartbeats', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(HEARTBEATS_MOCK),
      })
    )
    await page.route('**/api/v1/edge/sites/*/heartbeat-summary', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(SUMMARY_MOCK),
      })
    )

  })

  test('loads the Sites & Saúde panel with overview cards', async ({ page }) => {
    await page.goto('/epi/sites-health')

    await expect(page.getByRole('heading', { name: /Sites.*Saúde/i })).toBeVisible({
      timeout: 8000,
    })

    await expect(page.getByText('Sites Saudáveis')).toBeVisible()
    await expect(page.getByText('Devices Online')).toBeVisible()
  })

  test('shows site rows in the table (backend field names transformed correctly)', async ({ page }) => {
    await page.goto('/epi/sites-health')

    // 'name' field from backend transformed to site_name by edgeService
    await expect(page.getByText('Unidade Alpha')).toBeVisible({ timeout: 8000 })
    await expect(page.getByText('Unidade Beta')).toBeVisible()
    // 'derived_status' transformed to status → badge labels
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

  test('non-admin user sees access-denied alert', async ({ page }) => {
    // Override the admin user set in beforeEach with an operator
    await page.addInitScript(() => {
      window.localStorage.setItem(
        'user',
        JSON.stringify({
          id: 'u2',
          email: 'op@test.com',
          name: 'Operator',
          role: 'operator',
          modules: ['epi'],
        })
      )
    })

    await page.goto('/epi/sites-health')

    await expect(page.getByRole('alert')).toBeVisible({ timeout: 5000 })
    await expect(page.getByText(/Acesso restrito/)).toBeVisible()
  })
})
