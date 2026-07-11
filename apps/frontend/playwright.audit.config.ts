/**
 * Config Playwright dedicada à auditoria visual (docs/quality/visual-audit).
 * Separada do playwright.config.ts versionado: timeout maior (cold-compile do
 * Vite dev bloqueia domcontentloaded na primeira navegação) e testDir restrito.
 */
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './src/test/e2e/visual-audit',
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:3001',
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npx vite --port 3001 --strictPort',
    url: 'http://localhost:3001',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
