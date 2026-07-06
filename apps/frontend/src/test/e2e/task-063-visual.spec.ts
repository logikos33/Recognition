/**
 * Task-063 — evidência visual do painel "Desempenho por câmera" (CamerasPage)
 * e da tela de Operação (TrainingModeLayout).
 *
 * Não faz asserções funcionais: captura screenshots antes/depois da correção
 * visual (tokens WS1). Controle do prefixo via env SHOT_PREFIX=before|after.
 *
 * Uso:
 *   SHOT_PREFIX=before npx playwright test task-063-visual
 *   SHOT_PREFIX=after  npx playwright test task-063-visual
 */
import { test, type Page } from '@playwright/test'
import * as path from 'node:path'
import * as fs from 'node:fs'

const PREFIX = process.env.SHOT_PREFIX ?? 'after'
// apps/frontend → raiz do repo → docs/quality/evidence/task-063
const OUT_DIR = path.resolve(process.cwd(), '../../docs/quality/evidence/task-063')

const CAMERA = {
  id: '1',
  name: 'Câmera Pátio',
  location: 'Pátio Norte',
  manufacturer: 'hikvision',
  ip_address: '10.0.0.5',
  port: 554,
  stream_status: 'inactive',
  is_active: true,
  fps_target: 5,
  quality_preset: 'medium',
}

const OPERATIONS = [
  {
    id: 101,
    camera_id: '1',
    module_id: 'ppe',
    type_id: 'position',
    name: 'Zona Portão Leste',
    config: { roi_points: [[0.1, 0.2], [0.5, 0.2], [0.5, 0.7], [0.1, 0.7]] },
    status: 'active',
    version: 1,
    created_at: new Date().toISOString(),
  },
  {
    id: 102,
    camera_id: '1',
    module_id: 'ppe',
    type_id: 'count_static',
    name: 'Contagem Doca 2',
    config: { roi_points: [[0.6, 0.3], [0.9, 0.3], [0.9, 0.8], [0.6, 0.8]] },
    status: 'error',
    version: 1,
    created_at: new Date().toISOString(),
  },
]

const OP_TYPES = [
  {
    type_id: 'position',
    type_label: 'Posição / Presença',
    description: 'Detecta presença em zona ROI',
    available_modules: ['ppe'],
    config_schema: { roi_points: {} },
    metric_options: ['state'],
    output_formats: ['conditional'],
  },
  {
    type_id: 'count_static',
    type_label: 'Contagem Estática',
    description: 'Conta objetos dentro da zona',
    available_modules: ['ppe'],
    config_schema: { roi_points: {}, count_threshold: {} },
    metric_options: ['count'],
    output_formats: ['physical'],
  },
]

async function setupRoutes(page: Page, theme: 'recognition-dark' | 'professional') {
  // Catch-all PRIMEIRO — Playwright avalia rotas na ordem inversa de registro,
  // então as rotas específicas abaixo têm precedência sobre esta.
  await page.route('**/api/**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: {} }),
    })
  )

  await page.route('**/api/cameras/1/health-context**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        data: {
          has_telemetry: false,
          derived_status: null,
          metrics: null,
          fps_demand_total: 0,
          cameras_active_count: 0,
        },
      }),
    })
  )

  await page.route('**/api/cameras/1/operations**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: { operations: OPERATIONS } }),
    })
  )

  await page.route('**/api/modules/**/operation-types**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: { module: 'ppe', types: OP_TYPES } }),
    })
  )

  await page.route('**/api/cameras', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        data: { cameras: [CAMERA], gateway_status: { status: 'online' } },
      }),
    })
  )

  await page.route('**/stream.m3u8**', route => route.fulfill({ status: 404, body: '' }))

  await page.addInitScript(
    ([mode]) => {
      localStorage.setItem('token', 'fake-jwt-token')
      localStorage.setItem(
        'user',
        JSON.stringify({ email: 'test@test.com', role: 'admin', full_name: 'Test Admin' })
      )
      localStorage.setItem(
        'recognition-theme',
        JSON.stringify({ state: { mode }, version: 0 })
      )
    },
    [theme]
  )
}

async function shoot(page: Page, name: string) {
  fs.mkdirSync(OUT_DIR, { recursive: true })
  await page.screenshot({ path: path.join(OUT_DIR, `${PREFIX}-${name}.png`), fullPage: false })
}

const THEMES = ['recognition-dark', 'professional'] as const

for (const theme of THEMES) {
  test.describe(`task-063 evidência visual — tema ${theme}`, () => {
    test(`CamerasPage com painel Desempenho por câmera (${theme})`, async ({ page }) => {
      await setupRoutes(page, theme)
      await page.goto('/epi/cameras')
      // Seleciona a câmera na lista lateral
      await page.getByText('Câmera Pátio').first().click()
      await page.getByText('Desempenho por câmera').waitFor({ state: 'visible' })
      await page.waitForTimeout(800)
      // Garante o painel de FPS no viewport
      await page.getByText('Desempenho por câmera').scrollIntoViewIfNeeded()
      await shoot(page, `cameras-fps-${theme}`)
    })

    test(`Tela de Operação — TrainingModeLayout (${theme})`, async ({ page }) => {
      await setupRoutes(page, theme)
      await page.goto('/epi/cameras/1/operations')
      await page.getByText('Ferramentas cadastradas').first().waitFor({ state: 'visible' })
      await page.waitForTimeout(800)
      await shoot(page, `operations-${theme}`)
    })
  })
}
