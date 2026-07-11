/**
 * Auditoria visual — grupo 18-reports-sites (tier 1).
 *
 * /epi/reports — ReportsPage é PLACEHOLDER estático ("Em breve"): sem
 * endpoints, sem estados de dados. Cores hardcoded rgba(255,255,255,x)
 * inline (classe de defeito task-063 — ilegível sob superfície clara).
 * Só o estado default é capturável; fixtures de relatório/export não
 * existem ainda (registrado como deferred).
 *
 * /epi/sites-health — EpiSitesHealthPage (vai virar Admin no WS9).
 * Endpoints reais (edgeService adapta nomes do backend):
 *   GET /api/v1/edge/overview
 *       → data: { sites_total, sites_por_status, devices_total,
 *                 devices_online, devices_revoked, sites_offline }
 *   GET /api/v1/edge/sites/health
 *       → data: { sites: [{ site_id, name, derived_status,
 *                 last_heartbeat_at, inference_fps, cameras_online,
 *                 cameras_total, ... }] }
 *   GET /api/v1/edge/sites/:id/heartbeats
 *       → data: { heartbeats: [{ received_at, inference_fps, cpu_pct,
 *                 cameras_online, status }] }
 *   GET /api/v1/edge/sites/:id/heartbeat-summary
 *       → data: { site_id, heartbeat_count, avg_inference_fps,
 *                 uptime_pct, last_received_at }
 *
 * Role guard: isAdmin (admin|superadmin) — operator vê
 * "Acesso restrito a administradores" (estado real conhecido, capturado).
 */
import { test, type Page } from '@playwright/test'
import { setupApp, shootBothThemes, shoot, settle, gotoAudit } from './helpers'

/* ------------------------------------------------------------------ */
/* epi-reports (placeholder)                                           */
/* ------------------------------------------------------------------ */

const REPORTS_SCREEN = 'epi-reports'
const REPORTS_ROUTE = '/epi/reports'

test('epi-reports — default (placeholder "Em breve")', async ({ page }) => {
  await setupApp(page)
  await gotoAudit(page, REPORTS_ROUTE)
  await page.getByText('Relatorios').waitFor({ timeout: 30_000 })
  await page
    .getByText('Em breve — export Excel, graficos de tendencia, compliance reports.')
    .waitFor({ timeout: 10_000 })
  await settle(page)
  await shootBothThemes(page, REPORTS_SCREEN, 'default')
})

/* ------------------------------------------------------------------ */
/* sites-health — fixtures pt-BR (frota edge Tenant RVB Industrial)    */
/* ------------------------------------------------------------------ */

const SITES_SCREEN = 'sites-health'
const SITES_ROUTE = '/epi/sites-health'

const NOW = Date.now()
const minsAgo = (m: number) => new Date(NOW - m * 60_000).toISOString()

/** Shape cru do backend (adaptado por edgeService.adaptOverview). */
const OVERVIEW = {
  sites_total: 7,
  sites_por_status: { active: 5, inactive: 2 },
  devices_total: 12,
  devices_online: 9,
  devices_revoked: 1,
  sites_offline: 2,
}

/** Shape cru do backend: name/derived_status/last_heartbeat_at/inference_fps. */
const SITES = [
  {
    site_id: 'site-rvb-matriz',
    name: 'RVB Industrial — Matriz Betim',
    deployment_mode: 'edge',
    derived_status: 'healthy',
    last_heartbeat_at: minsAgo(0),
    inference_fps: 24.6,
    cameras_online: 6,
    cameras_total: 6,
    cpu_pct: 41.2,
    gpu_pct: 63.0,
    queue_depth: 0,
    edge_version: '1.4.2',
  },
  {
    site_id: 'site-rvb-contagem',
    name: 'RVB Industrial — Filial Contagem',
    deployment_mode: 'edge',
    derived_status: 'healthy',
    last_heartbeat_at: minsAgo(2),
    inference_fps: 22.1,
    cameras_online: 4,
    cameras_total: 4,
    cpu_pct: 38.7,
    gpu_pct: 55.4,
    queue_depth: 0,
    edge_version: '1.4.2',
  },
  {
    site_id: 'site-cd-cajamar',
    name: 'Centro de Distribuição Cajamar',
    deployment_mode: 'edge',
    derived_status: 'healthy',
    last_heartbeat_at: minsAgo(1),
    inference_fps: 25.3,
    cameras_online: 8,
    cameras_total: 8,
    cpu_pct: 52.9,
    gpu_pct: 71.8,
    queue_depth: 1,
    edge_version: '1.4.1',
  },
  {
    site_id: 'site-porto-santos',
    name: 'Unidade Portuária Santos',
    deployment_mode: 'edge',
    derived_status: 'degraded',
    last_heartbeat_at: minsAgo(9),
    inference_fps: 11.4,
    cameras_online: 3,
    cameras_total: 5,
    cpu_pct: 88.6,
    gpu_pct: 94.1,
    queue_depth: 14,
    edge_version: '1.3.9',
  },
  {
    site_id: 'site-quimica-paulinia',
    name: 'Planta Química Paulínia',
    deployment_mode: 'edge',
    derived_status: 'critical',
    last_heartbeat_at: minsAgo(28),
    inference_fps: 3.2,
    cameras_online: 1,
    cameras_total: 6,
    cpu_pct: 97.4,
    gpu_pct: 99.0,
    queue_depth: 42,
    edge_version: '1.3.9',
  },
  {
    site_id: 'site-mineracao-serra',
    name: 'Mineração Serra Azul',
    deployment_mode: 'edge',
    derived_status: 'offline',
    last_heartbeat_at: minsAgo(60 * 26),
    inference_fps: null,
    cameras_online: 0,
    cameras_total: 4,
    cpu_pct: null,
    gpu_pct: null,
    queue_depth: null,
    edge_version: '1.3.7',
  },
  {
    site_id: 'site-terminal-sul',
    name: 'Terminal Logístico Sul',
    deployment_mode: 'edge',
    derived_status: 'offline',
    last_heartbeat_at: null,
    inference_fps: null,
    cameras_online: 0,
    cameras_total: 2,
    cpu_pct: null,
    gpu_pct: null,
    queue_depth: null,
    edge_version: null,
  },
]

/** 24 heartbeats (5 em 5 min) com FPS oscilando ~20-25 (shape cru do backend). */
const HEARTBEATS = {
  heartbeats: Array.from({ length: 24 }, (_, i) => ({
    id: `hb-${i + 1}`,
    received_at: minsAgo((24 - i) * 5),
    status: 'healthy',
    inference_fps: Number((22.5 + Math.sin(i / 2.5) * 2.8).toFixed(1)),
    cameras_online: 6,
    cameras_total: 6,
    cpu_pct: Number((44 + Math.cos(i / 3) * 9).toFixed(1)),
  })),
}

const SUMMARY = {
  site_id: 'site-rvb-matriz',
  heartbeat_count: 288,
  avg_inference_fps: 23.4,
  uptime_pct: 99.2,
  last_received_at: minsAgo(0),
  max_inference_fps: 26.1,
  avg_inference_latency_ms: 42,
  last_status: 'healthy',
  derived_status: 'healthy',
  window_seconds: 86_400,
}

/**
 * Globs específicos registrados DEPOIS dos genéricos → precedência
 * (Playwright avalia rotas na ordem inversa de registro).
 * site-terminal-sul nunca enviou heartbeat → painel "Sem dados de heartbeat".
 */
const RICH_FIXTURES: Record<string, unknown> = {
  '**/api/v1/edge/overview': OVERVIEW,
  '**/api/v1/edge/sites/health': { sites: SITES },
  '**/api/v1/edge/sites/*/heartbeats': HEARTBEATS,
  '**/api/v1/edge/sites/*/heartbeat-summary': SUMMARY,
  '**/api/v1/edge/sites/site-terminal-sul/heartbeats': { heartbeats: [] },
  '**/api/v1/edge/sites/site-terminal-sul/heartbeat-summary': {
    site_id: 'site-terminal-sul',
    heartbeat_count: 0,
    avg_inference_fps: null,
    uptime_pct: 0,
    last_received_at: null,
  },
}

async function openSitesPage(page: Page) {
  await gotoAudit(page, SITES_ROUTE)
  await page.getByRole('heading', { name: 'Sites & Saúde' }).waitFor({ timeout: 30_000 })
  await page.getByText('RVB Industrial — Matriz Betim').waitFor({ timeout: 15_000 })
  await settle(page)
}

/* --------------------------- Estados ------------------------------ */

test('sites-health — default (frota rica: 7 sites, status variados)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openSitesPage(page)
  await page.getByText('Devices Online').waitFor({ timeout: 10_000 })
  await shootBothThemes(page, SITES_SCREEN, 'default', true)
})

test('sites-health — empty (nenhum site na frota)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/edge/overview': {
        sites_total: 0,
        sites_por_status: {},
        devices_total: 0,
        devices_online: 0,
        devices_revoked: 0,
        sites_offline: 0,
      },
      '**/api/v1/edge/sites/health': { sites: [] },
    },
  })
  await gotoAudit(page, SITES_ROUTE)
  await page.getByText('Nenhum site encontrado').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, SITES_SCREEN, 'empty')
})

test('sites-health — loading (overview/health nunca respondem)', async ({ page }) => {
  await setupApp(page, {
    stall: ['**/api/v1/edge/overview', '**/api/v1/edge/sites/health'],
  })
  await gotoAudit(page, SITES_ROUTE)
  await page.getByText('Carregando dados da frota...').waitFor({ timeout: 30_000 })
  // Sem settle: networkidle nunca acontece com request pendurada.
  await page.waitForTimeout(1500)
  await shootBothThemes(page, SITES_SCREEN, 'loading')
})

test('sites-health — error (edge endpoints 500) + hover retry', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/v1/edge/overview': {
        status: 500,
        body: { status: 'error', error: 'Falha ao consultar frota edge' },
      },
      '**/api/v1/edge/sites/health': {
        status: 500,
        body: { status: 'error', error: 'Falha ao consultar frota edge' },
      },
    },
  })
  await gotoAudit(page, SITES_ROUTE)
  await page.getByRole('button', { name: 'Tentar novamente' }).waitFor({ timeout: 30_000 })
  await settle(page)

  // Hover (só dark) no CTA de retry — antes da transformação clara.
  await page.getByRole('button', { name: 'Tentar novamente' }).hover()
  await page.waitForTimeout(300)
  await shoot(page, SITES_SCREEN, 'dark-hover-retry')
  await page.mouse.move(4, 4)
  await page.waitForTimeout(300)

  await shootBothThemes(page, SITES_SCREEN, 'error')
})

test('sites-health — operator-denied (role operator → acesso restrito)', async ({ page }) => {
  await setupApp(page, { role: 'operator', fixtures: RICH_FIXTURES })
  await gotoAudit(page, SITES_ROUTE)
  await page.getByText('Acesso restrito a administradores').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, SITES_SCREEN, 'operator-denied')
})

/* ------------------- Painel de detalhe (drawer) -------------------- */

test('sites-health — modal-site-detail (summary + gráfico FPS)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openSitesPage(page)
  await page.getByTestId('site-row-site-rvb-matriz').click()
  await page.getByText('FPS — últimas 24 entradas').waitFor({ timeout: 10_000 })
  await page.getByText('Uptime').waitFor({ timeout: 10_000 })
  await settle(page, 600)
  await shootBothThemes(page, SITES_SCREEN, 'modal-site-detail')
})

test('sites-health — modal-site-detail-sem-dados (site offline sem heartbeats)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openSitesPage(page)
  await page.getByTestId('site-row-site-terminal-sul').click()
  await page.getByText('Sem dados de heartbeat').waitFor({ timeout: 10_000 })
  await settle(page, 400)
  await shootBothThemes(page, SITES_SCREEN, 'modal-site-detail-sem-dados')
})

test('sites-health — modal-site-detail-loading (detalhe pendurado)', async ({ page }) => {
  await setupApp(page, {
    fixtures: RICH_FIXTURES,
    stall: [
      '**/api/v1/edge/sites/*/heartbeats',
      '**/api/v1/edge/sites/*/heartbeat-summary',
    ],
  })
  await openSitesPage(page)
  await page.getByTestId('site-row-site-rvb-matriz').click()
  await page.getByText('Carregando detalhes...').waitFor({ timeout: 10_000 })
  await page.waitForTimeout(800)
  await shootBothThemes(page, SITES_SCREEN, 'modal-site-detail-loading')
})

/* --------------------------- Hover (só dark) ----------------------- */

test('sites-health — hover linha da tabela de sites', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openSitesPage(page)
  await page.getByTestId('site-row-site-porto-santos').hover()
  await page.waitForTimeout(300)
  await shoot(page, SITES_SCREEN, 'dark-hover-row')
})
