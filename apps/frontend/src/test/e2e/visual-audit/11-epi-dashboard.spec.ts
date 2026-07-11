/**
 * Auditoria visual — Grupo 11: EPI Dashboard (/epi/dashboard) — tier 1.
 *
 * Endpoints reais consumidos pela página (EpiDashboard + KPIRow + CameraGrid):
 * - GET /api/alerts?per_page=50&page=1  → { alerts, total, page, pages }
 * - GET /api/alerts?page=1&per_page=10  → drawer "Alertas Hoje" (KPIRow)
 * - GET /api/cameras                    → { cameras: Camera[] }
 * - GET /api/modules/epi/stats          → DashboardStats (KPIs)
 * - GET /api/cameras/{id}/stream/info   → { type, url } (CameraCell)
 *
 * O grid DVR lê atribuições de células do localStorage (zustand persist,
 * chave 'epi-camera-grid') — seedado via addInitScript no estado rico.
 */
import { test, type Page } from '@playwright/test'
import { setupApp, shootBothThemes, shoot, settle, gotoAudit } from './helpers'

const SLUG = 'epi-dashboard'
const ROUTE = '/epi/dashboard'

/* ── Fixtures pt-BR ─────────────────────────────────────────────── */

const minsAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()

const CAMERAS = [
  {
    id: 'cam-1',
    name: 'Câmera Pátio Norte',
    location: 'Pátio Norte — Portão 2',
    manufacturer: 'intelbras',
    host: '10.0.42.11',
    port: 554,
    channel: 1,
    module_code: 'epi',
    is_active: true,
    stream_status: 'active',
    last_seen: minsAgo(1),
    created_at: '2026-05-02T09:12:00Z',
  },
  {
    id: 'cam-2',
    name: 'Câmera Doca 3',
    location: 'Doca de Carregamento',
    manufacturer: 'hikvision',
    host: '10.0.42.12',
    port: 554,
    channel: 1,
    module_code: 'epi',
    is_active: true,
    stream_status: 'active',
    last_seen: minsAgo(2),
    created_at: '2026-05-02T09:20:00Z',
  },
  {
    id: 'cam-3',
    name: 'Câmera Linha de Produção A',
    location: 'Galpão 1 — Linha A',
    manufacturer: 'intelbras',
    host: '10.0.42.13',
    port: 554,
    channel: 2,
    module_code: 'epi',
    is_active: true,
    stream_status: 'error',
    last_error: 'RTSP timeout após 15s',
    created_at: '2026-05-10T14:05:00Z',
  },
  {
    id: 'cam-4',
    name: 'Câmera Almoxarifado',
    location: 'Bloco B — Térreo',
    manufacturer: 'generic',
    host: '10.0.42.14',
    port: 554,
    channel: 1,
    module_code: 'epi',
    is_active: false,
    stream_status: 'stopped',
    created_at: '2026-06-01T08:00:00Z',
  },
]

const ALERTS = [
  {
    id: 'al-01',
    camera_id: 'cam-1',
    camera_name: 'Câmera Pátio Norte',
    violation_type: 'Sem capacete',
    violations: [{ class: 'no_helmet', confidence: 0.94 }],
    acknowledged: false,
    created_at: minsAgo(4),
  },
  {
    id: 'al-02',
    camera_id: 'cam-2',
    camera_name: 'Câmera Doca 3',
    violation_type: 'Sem colete',
    violations: [{ class: 'no_vest', confidence: 0.88 }],
    acknowledged: false,
    created_at: minsAgo(13),
  },
  {
    id: 'al-03',
    camera_id: 'cam-3',
    camera_name: 'Câmera Linha de Produção A',
    violation_type: 'Sem luvas',
    violations: [
      { class: 'no_gloves', confidence: 0.81 },
      { class: 'no_helmet', confidence: 0.77 },
    ],
    acknowledged: true,
    created_at: minsAgo(28),
  },
  {
    id: 'al-04',
    camera_id: 'cam-1',
    camera_name: 'Câmera Pátio Norte',
    violation_type: 'Sem óculos',
    violations: [{ class: 'no_safety_glasses', confidence: 0.73 }],
    acknowledged: false,
    created_at: minsAgo(47),
  },
  {
    id: 'al-05',
    camera_id: 'cam-4',
    camera_name: 'Câmera Almoxarifado',
    violation_type: 'Sem colete',
    violations: [{ class: 'no_vest', confidence: 0.9 }],
    acknowledged: false,
    created_at: minsAgo(68),
  },
  {
    id: 'al-06',
    camera_id: 'cam-2',
    camera_name: 'Câmera Doca 3',
    violation_type: 'Sem capacete',
    violations: [{ class: 'no_helmet', confidence: 0.86 }],
    acknowledged: true,
    created_at: minsAgo(95),
  },
  {
    id: 'al-07',
    camera_id: 'cam-3',
    camera_name: 'Câmera Linha de Produção A',
    violation_type: 'Sem luvas',
    violations: [{ class: 'no_gloves', confidence: 0.79 }],
    acknowledged: false,
    created_at: minsAgo(152),
  },
  {
    id: 'al-08',
    camera_id: 'cam-1',
    camera_name: 'Câmera Pátio Norte',
    violation_type: 'Sem colete',
    violations: [{ class: 'no_vest', confidence: 0.92 }],
    acknowledged: true,
    created_at: minsAgo(240),
  },
]

const STATS = {
  cameras_active: 3,
  cameras_total: 4,
  compliance_rate: 87,
  alerts_today: 12,
  detections_per_hour: 342,
  detections_prev_hour: 310,
  active_model_name: 'yolo26s-epi-rvb-v3',
  active_model_map50: 0.912,
  compliance_by_class: {
    helmet: 94.2,
    vest: 88.7,
    gloves: 71.3,
    glasses: 65.8,
  },
}

const RICH_FIXTURES = {
  '**/api/alerts*': { alerts: ALERTS, total: 12, page: 1, pages: 1 },
  '**/api/cameras': { cameras: CAMERAS },
  '**/api/modules/epi/stats': STATS,
  '**/api/cameras/*/stream/info': {
    type: 'hls',
    url: 'http://localhost:3001/streams/demo/stream.m3u8',
  },
}

const ERROR_500 = {
  status: 500,
  body: { status: 'error', error: 'Erro interno do servidor' },
}

/* ── Helpers locais ─────────────────────────────────────────────── */

/** Seeda o grid DVR (zustand persist) com 3 câmeras + 1 célula vazia. */
async function seedGrid(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem(
      'epi-camera-grid',
      JSON.stringify({
        state: {
          activeLayoutId: '2x2',
          cellAssignments: { 0: 'cam-1', 1: 'cam-2', 2: 'cam-3', 3: null },
          customPresets: [],
          showLabels: true,
        },
        version: 0,
      })
    )
  })
}

async function gotoRich(page: Page) {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await seedGrid(page)
  await gotoAudit(page, ROUTE)
  await page.getByText('Últimos Alertas').waitFor()
  await settle(page)
}

async function openWizard(page: Page) {
  await page.getByLabel('Abrir painel de controle').click()
  await page.getByText('Painel de Controle').waitFor()
  await page.getByRole('button', { name: /Nova Camera/i }).click()
  await page.getByText('Passo 1 de 4').waitFor()
}

async function wizardToStep2(page: Page) {
  await page.getByRole('button', { name: 'Intelbras' }).click()
  await page.getByRole('button', { name: 'Próximo →' }).click()
  await page.getByText('Passo 2 de 4').waitFor()
}

async function wizardToStep3(page: Page) {
  await page.getByPlaceholder('192.168.1.100').fill('10.0.42.15')
  await page.getByPlaceholder('admin').fill('admin')
  await page.getByPlaceholder('Senha de acesso').fill('recognition123')
  await page.getByRole('button', { name: 'Próximo →' }).click()
  await page.getByText('Passo 3 de 4').waitFor()
}

async function wizardToStep4(page: Page) {
  await page.getByPlaceholder('Ex: Entrada Principal, Baia 1...').fill('Câmera Portaria Sul')
  await page.getByPlaceholder('Ex: Bloco A, Térreo...').fill('Portaria Sul')
  await page.getByRole('button', { name: 'Próximo →' }).click()
  await page.getByText('Passo 4 de 4').waitFor()
}

/* ── Estados base ───────────────────────────────────────────────── */

test('epi-dashboard — default (rico)', async ({ page }) => {
  await gotoRich(page)
  await shootBothThemes(page, SLUG, 'default', true)
})

test('epi-dashboard — default quadrantes Q3/Q4 (viewport alto)', async ({ page }) => {
  // O shell tem overflow:hidden — em 900px de altura a 2ª linha do quadrantGrid
  // (Registro de Eventos + Distribuição de Violações) fica clipada. Viewport
  // alto revela os quadrantes inferiores para a auditoria.
  await page.setViewportSize({ width: 1440, height: 1700 })
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await seedGrid(page)
  await gotoAudit(page, ROUTE)
  await page.getByText('Registro de Eventos').waitFor()
  await settle(page)
  await shootBothThemes(page, SLUG, 'default-quadrantes')
})

test('epi-dashboard — empty', async ({ page }) => {
  await setupApp(page) // catch-all {} → sem alertas, sem câmeras, sem stats
  await gotoAudit(page, ROUTE)
  await page.getByText('Nenhum alerta recente').waitFor()
  await settle(page)
  await shootBothThemes(page, SLUG, 'empty', true)
})

test('epi-dashboard — loading (stall)', async ({ page }) => {
  await setupApp(page, {
    stall: [
      '**/api/alerts*',
      '**/api/cameras',
      '**/api/cameras/**',
      '**/api/modules/epi/stats',
    ],
  })
  await gotoAudit(page, ROUTE)
  await page.getByText('Cameras Ativas').waitFor()
  // settle() esperaria networkidle que nunca chega (requests penduradas)
  await page.waitForTimeout(1500)
  await shootBothThemes(page, SLUG, 'loading', true)
})

test('epi-dashboard — error (500)', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/alerts*': ERROR_500,
      '**/api/cameras': ERROR_500,
      '**/api/modules/epi/stats': ERROR_500,
    },
  })
  await gotoAudit(page, ROUTE)
  await page.getByText('Cameras Ativas').waitFor()
  await page.waitForTimeout(1500) // deixa o toast de erro aparecer
  await shootBothThemes(page, SLUG, 'error', true)
})

/* ── Drawers dos KPIs ───────────────────────────────────────────── */

test('epi-dashboard — drawer KPI Alertas Hoje', async ({ page }) => {
  await gotoRich(page)
  await page.getByText('Alertas Hoje').click()
  await page.getByText('Ultimos Alertas').waitFor() // título do drawer (sem acento)
  await settle(page, 500)
  await shootBothThemes(page, SLUG, 'modal-kpi-alertas')
})

test('epi-dashboard — drawer KPI Conformidade', async ({ page }) => {
  await gotoRich(page)
  await page.getByText('Taxa de Conformidade').click()
  await page.getByText('Conformidade por EPI').waitFor()
  await settle(page, 500)
  await shootBothThemes(page, SLUG, 'modal-kpi-conformidade')
})

/* ── Painel/menus do grid de câmeras ────────────────────────────── */

test('epi-dashboard — painel de controle do grid', async ({ page }) => {
  await gotoRich(page)
  await page.getByLabel('Abrir painel de controle').click()
  await page.getByText('Painel de Controle').waitFor()
  await settle(page, 500)
  await shootBothThemes(page, SLUG, 'modal-painel-cameras')
})

test('epi-dashboard — seletor de câmera (célula vazia)', async ({ page }) => {
  await gotoRich(page)
  // getByLabel evita o wrapper sortable do dnd-kit (também expõe role=button)
  await page.getByLabel('Adicionar câmera na posição 4').click()
  await page.getByText('Selecionar câmera').waitFor()
  await settle(page, 500)
  await shootBothThemes(page, SLUG, 'modal-seletor-camera')
})

test('epi-dashboard — menu de contexto da célula', async ({ page }) => {
  await gotoRich(page)
  // primeira ocorrência no DOM = header da célula do grid (Q1 vem antes de Q2/Q3)
  await page.getByText('Câmera Pátio Norte').first().click({ button: 'right' })
  await page.getByText('Trocar câmera').waitFor()
  await shootBothThemes(page, SLUG, 'modal-menu-contexto')
})

/* ── Wizard Nova Câmera (aberto a partir do painel do grid) ─────── */

test('epi-dashboard — wizard nova câmera passo 1', async ({ page }) => {
  await gotoRich(page)
  await openWizard(page)
  await settle(page, 500)
  await shootBothThemes(page, SLUG, 'wizard-step1')
})

test('epi-dashboard — wizard nova câmera passo 2', async ({ page }) => {
  await gotoRich(page)
  await openWizard(page)
  await wizardToStep2(page)
  await settle(page, 500)
  await shootBothThemes(page, SLUG, 'wizard-step2')
})

test('epi-dashboard — wizard nova câmera passo 3', async ({ page }) => {
  await gotoRich(page)
  await openWizard(page)
  await wizardToStep2(page)
  await wizardToStep3(page)
  await settle(page, 500)
  await shootBothThemes(page, SLUG, 'wizard-step3')
})

test('epi-dashboard — wizard nova câmera passo 4', async ({ page }) => {
  await gotoRich(page)
  await openWizard(page)
  await wizardToStep2(page)
  await wizardToStep3(page)
  await wizardToStep4(page)
  await settle(page, 500)
  await shootBothThemes(page, SLUG, 'wizard-step4')
})

/* ── Hover (só tema dark) ───────────────────────────────────────── */

test('epi-dashboard — hovers (dark)', async ({ page }) => {
  await gotoRich(page)

  await page.getByText('Taxa de Conformidade').hover()
  await page.waitForTimeout(300)
  await shoot(page, SLUG, 'hover-kpi-conformidade')

  // primeira ocorrência de "Sem colete" = linha do quadrante Últimos Alertas
  await page.getByText('Sem colete').first().hover()
  await page.waitForTimeout(300)
  await shoot(page, SLUG, 'hover-alert-row')
})
