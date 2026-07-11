/**
 * Auditoria visual — grupo 14-monitoring (tier 1).
 *
 * /epi/monitoring — MonitoringPage (VMS ao vivo): grid de câmeras filtrável
 *   por módulo, toggle de overlay, drawer de detalhe (Feed / Logs ao vivo /
 *   Info). NOTA: a rota NÃO redireciona mais pro dashboard — /monitoring é
 *   que redireciona para /epi/monitoring (AppRoutes.tsx:88-89).
 *   Endpoints reais:
 *     GET /api/cameras[?module=X]                → data: Camera[] | { cameras: Camera[] }
 *     GET /api/cameras/:id/stream/stream.m3u8    → player HLS (helpers 404 → card offline, legítimo)
 *     WS  socket.io namespace /monitor           → não conecta no harness → badge "Desconectado"
 *
 * /epi/health — StreamHealthPage: status do sistema (chips), workers Celery
 *   (tabela) e câmeras (cards com streaming/gateway/TTL).
 *   Endpoints reais (ATENÇÃO — /health e /streams/status são lidos na RAIZ do
 *   envelope, então precisam de `raw`, não `fixtures`):
 *     GET /api/health                        → { status, checks: { database, redis } }  (raiz)
 *     GET /api/streams/status                → { status, workers: [...] }               (raiz)
 *     GET /api/cameras                       → data: { cameras: [...] }
 *     GET /api/cameras/:id/stream/status     → data: { streaming, gateway_online, ttl_seconds }
 */
import { test, type Page } from '@playwright/test'
import { setupApp, shootBothThemes, shoot, settle, gotoAudit } from './helpers'

/* ================================================================== */
/* Fixtures pt-BR — Tenant RVB Industrial                              */
/* ================================================================== */

const CAMERAS = [
  {
    id: 'cam-1',
    name: 'Câmera Pátio Norte',
    location: 'Pátio Norte — Galpão A',
    manufacturer: 'intelbras',
    host: '10.20.30.101',
    port: 554,
    channel: 1,
    module_code: 'epi',
    is_active: true,
    is_streaming: true,
    stream_status: 'active',
    created_at: '2026-05-02T08:12:00Z',
  },
  {
    id: 'cam-2',
    name: 'Câmera Doca de Carga 2',
    location: 'Doca 2 — Expedição',
    manufacturer: 'hikvision',
    host: '10.20.30.102',
    port: 554,
    channel: 1,
    module_code: 'epi',
    is_active: true,
    is_streaming: true,
    stream_status: 'active',
    created_at: '2026-05-10T10:40:00Z',
  },
  {
    id: 'cam-3',
    name: 'Câmera Linha de Produção',
    location: 'Linha 1 — Envase',
    manufacturer: 'dahua',
    host: '10.20.30.103',
    port: 554,
    channel: 1,
    module_code: 'quality',
    is_active: true,
    is_streaming: false,
    stream_status: 'error',
    last_error: 'timeout',
    created_at: '2026-05-18T14:05:00Z',
  },
  {
    id: 'cam-4',
    name: 'Câmera Portaria Principal',
    location: 'Portaria — Entrada de Veículos',
    manufacturer: 'intelbras',
    host: '10.20.30.104',
    port: 554,
    channel: 1,
    module_code: 'fueling',
    is_active: true,
    is_streaming: true,
    stream_status: 'active',
    created_at: '2026-06-01T09:00:00Z',
  },
  {
    id: 'cam-5',
    name: 'Câmera Almoxarifado',
    location: 'Almoxarifado Central',
    manufacturer: 'generic',
    host: '10.20.30.105',
    port: 8554,
    channel: 1,
    module_code: 'epi',
    is_active: false,
    is_streaming: false,
    stream_status: 'inactive',
    created_at: '2026-06-12T16:22:00Z',
  },
  {
    id: 'cam-6',
    name: 'Câmera Estacionamento Sul',
    location: 'Estacionamento — Bloco S',
    manufacturer: 'hikvision',
    host: '10.20.30.106',
    port: 554,
    channel: 2,
    module_code: 'quality',
    is_active: true,
    is_streaming: true,
    stream_status: 'active',
    created_at: '2026-06-20T11:45:00Z',
  },
]

/* ================================================================== */
/* PÁGINA 1 — /epi/monitoring (MonitoringPage, VMS)                    */
/* ================================================================== */

const MON = 'epi-monitoring'
const MON_ROUTE = '/epi/monitoring'

// '**/api/cameras**' cobre /cameras E /cameras?module=X (o filtro por módulo
// também é aplicado client-side pela página, então devolver a lista completa
// funciona pros dois casos). O 404 dos .m3u8 registrado pelo setupApp tem
// precedência sobre este glob.
const MON_FIXTURES: Record<string, unknown> = {
  '**/api/cameras**': { cameras: CAMERAS },
}

async function openMonitoring(page: Page) {
  await gotoAudit(page, MON_ROUTE)
  await page.getByText('Câmera Pátio Norte').waitFor({ timeout: 30_000 })
  await settle(page)
}

/** Abre o drawer de detalhe da cam-2 e espera a tab bar aparecer. */
async function openDrawer(page: Page) {
  await page.getByText('Câmera Doca de Carga 2').first().click()
  await page.getByRole('button', { name: 'Logs ao vivo' }).waitFor({ timeout: 10_000 })
  await page.waitForTimeout(600) // animação de abertura do AppDrawer
}

test('epi-monitoring — default (grid rico, players conectando)', async ({ page }) => {
  await setupApp(page, { fixtures: MON_FIXTURES })
  await openMonitoring(page)
  await shootBothThemes(page, MON, 'default')
})

test('epi-monitoring — offline-players (m3u8 404 → cards offline)', async ({ page }) => {
  await setupApp(page, { fixtures: MON_FIXTURES })
  await gotoAudit(page, MON_ROUTE)
  await page.getByText('Câmera Pátio Norte').waitFor({ timeout: 30_000 })
  // hls.js esgota os retries do manifest (404) e o card mostra "Camera offline"
  await page
    .getByText('Camera offline')
    .first()
    .waitFor({ timeout: 60_000 })
    .catch(() => {})
  await page.waitForTimeout(1500)
  await shootBothThemes(page, MON, 'offline-players')
})

test('epi-monitoring — empty (nenhuma câmera)', async ({ page }) => {
  await setupApp(page, { fixtures: { '**/api/cameras**': { cameras: [] } } })
  await gotoAudit(page, MON_ROUTE)
  await page.getByText('Nenhuma câmera encontrada').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, MON, 'empty')
})

test('epi-monitoring — loading (GET /cameras nunca responde)', async ({ page }) => {
  await setupApp(page, { stall: ['**/api/cameras**'] })
  await gotoAudit(page, MON_ROUTE)
  await page.getByText('Carregando câmeras...').waitFor({ timeout: 30_000 })
  // Sem settle: request pendurada nunca dá networkidle.
  await page.waitForTimeout(1500)
  await shootBothThemes(page, MON, 'loading')
})

test('epi-monitoring — error (GET /cameras 500 → cai no vazio + toast)', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/cameras**': {
        status: 500,
        body: { status: 'error', error: 'Falha ao conectar ao banco de dados' },
      },
    },
  })
  await gotoAudit(page, MON_ROUTE)
  // A página engole o erro (catch → setCameras([])) e renderiza o MESMO
  // estado vazio — sem UI de erro dedicada. Registrado como issue.
  await page.getByText('Nenhuma câmera encontrada').waitFor({ timeout: 30_000 })
  await page.waitForTimeout(1200) // dá tempo do toast de erro (lazy-import) aparecer
  await shootBothThemes(page, MON, 'error')
})

test('epi-monitoring — tab-epi (filtro por módulo EPI)', async ({ page }) => {
  await setupApp(page, { fixtures: MON_FIXTURES })
  await openMonitoring(page)
  await page.getByRole('button', { name: 'EPI', exact: true }).first().click()
  await page.getByText('Câmera Almoxarifado').waitFor({ timeout: 15_000 })
  await settle(page, 500)
  await shootBothThemes(page, MON, 'tab-epi')
})

test('epi-monitoring — drawer-feed (detalhe da câmera, tab Feed)', async ({ page }) => {
  await setupApp(page, { fixtures: MON_FIXTURES })
  await openMonitoring(page)
  await openDrawer(page)
  await shootBothThemes(page, MON, 'drawer-feed')
})

test('epi-monitoring — drawer-tab-logs (Logs ao vivo, aguardando detecções)', async ({ page }) => {
  await setupApp(page, { fixtures: MON_FIXTURES })
  await openMonitoring(page)
  await openDrawer(page)
  await page.getByRole('button', { name: 'Logs ao vivo' }).click()
  await page.getByText('Aguardando detecções...').waitFor({ timeout: 10_000 })
  await page.waitForTimeout(400)
  await shootBothThemes(page, MON, 'drawer-tab-logs')
})

test('epi-monitoring — drawer-tab-info (metadados da câmera)', async ({ page }) => {
  await setupApp(page, { fixtures: MON_FIXTURES })
  await openMonitoring(page)
  await openDrawer(page)
  await page.getByRole('button', { name: 'Info', exact: true }).click()
  await page.getByText('Fabricante').waitFor({ timeout: 10_000 })
  await page.waitForTimeout(400)
  await shootBothThemes(page, MON, 'drawer-tab-info')
})

test('epi-monitoring — hover (card de câmera + toggle Overlay) [só dark]', async ({ page }) => {
  await setupApp(page, { fixtures: MON_FIXTURES })
  await openMonitoring(page)

  await page.getByText('Câmera Pátio Norte').hover()
  await page.waitForTimeout(300)
  await shoot(page, MON, 'dark-hover-camera-card')

  await page.getByRole('button', { name: 'Overlay' }).hover()
  await page.waitForTimeout(300)
  await shoot(page, MON, 'dark-hover-overlay-toggle')
})

/* ================================================================== */
/* PÁGINA 2 — /epi/health (StreamHealthPage)                           */
/* ================================================================== */

const SH = 'stream-health'
const SH_ROUTE = '/epi/health'

const WORKERS = [
  { worker_id: 'celery@worker-inference-01', status: 'online', active_tasks: 3 },
  { worker_id: 'celery@worker-training-01', status: 'online', active_tasks: 1 },
  { worker_id: 'celery@worker-extraction-01', status: 'online', active_tasks: 0 },
  { worker_id: 'celery@worker-quality-02', status: 'offline', active_tasks: 0 },
]

// /health e /streams/status são lidos na RAIZ do envelope → mock via `raw`.
const SH_RAW_OK: Record<string, { status?: number; body?: unknown }> = {
  '**/api/health': {
    body: { status: 'healthy', checks: { database: true, redis: true } },
  },
  '**/api/streams/status': {
    body: { status: 'ok', workers: WORKERS },
  },
}

// Status de stream variado por câmera (lido em res.data → `fixtures`).
const SH_FIXTURES_OK: Record<string, unknown> = {
  '**/api/cameras': { cameras: CAMERAS },
  '**/api/cameras/cam-1/stream/status': {
    streaming: true, gateway_online: true, ttl_seconds: 112,
  },
  '**/api/cameras/cam-2/stream/status': {
    streaming: true, gateway_online: true, ttl_seconds: 87,
  },
  '**/api/cameras/cam-3/stream/status': {
    streaming: false, gateway_online: true,
  },
  '**/api/cameras/cam-4/stream/status': {
    streaming: true, gateway_online: false,
  },
  '**/api/cameras/cam-5/stream/status': {
    streaming: false, gateway_online: false,
  },
  '**/api/cameras/cam-6/stream/status': {
    streaming: true, gateway_online: true, ttl_seconds: 45,
  },
}

async function openStreamHealth(page: Page) {
  await gotoAudit(page, SH_ROUTE)
  await page.getByText('Stream Health').waitFor({ timeout: 30_000 })
  await settle(page)
}

test('stream-health — default (sistema saudável, workers e câmeras)', async ({ page }) => {
  await setupApp(page, { fixtures: SH_FIXTURES_OK, raw: SH_RAW_OK })
  await openStreamHealth(page)
  await page.getByText('celery@worker-inference-01').waitFor({ timeout: 15_000 })
  await shootBothThemes(page, SH, 'default', true)
})

test('stream-health — empty (sem workers, sem câmeras)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/cameras': { cameras: [] } },
    raw: {
      '**/api/health': {
        body: { status: 'healthy', checks: { database: true, redis: true } },
      },
      '**/api/streams/status': { body: { status: 'ok', workers: [] } },
    },
  })
  await openStreamHealth(page)
  await page.getByText('Nenhum worker detectado.').waitFor({ timeout: 15_000 })
  await page.getByText('Nenhuma câmera cadastrada.').waitFor({ timeout: 15_000 })
  await shootBothThemes(page, SH, 'empty', true)
})

test('stream-health — loading (endpoints nunca respondem → spinner)', async ({ page }) => {
  await setupApp(page, {
    stall: ['**/api/health', '**/api/streams/status', '**/api/cameras'],
  })
  await gotoAudit(page, SH_ROUTE)
  // O api.ts aborta em 15s → screenshot antes disso, com o spinner na tela.
  await page.waitForTimeout(2500)
  await shootBothThemes(page, SH, 'loading')
})

test('stream-health — error (500 em tudo → chips vermelhos + listas vazias)', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/health': { status: 500, body: { status: 'error', error: 'Serviço indisponível' } },
      '**/api/streams/status': { status: 500, body: { status: 'error', error: 'Serviço indisponível' } },
      '**/api/cameras': { status: 500, body: { status: 'error', error: 'Serviço indisponível' } },
      '**/api/cameras/*/stream/status': { status: 500, body: { status: 'error' } },
    },
  })
  await gotoAudit(page, SH_ROUTE)
  await page.getByText('Stream Health').waitFor({ timeout: 30_000 })
  await page.waitForTimeout(1500) // toasts de erro (lazy-import)
  await shootBothThemes(page, SH, 'error', true)
})

test('stream-health — degraded (Redis fora, gateway degradado, worker offline)', async ({ page }) => {
  await setupApp(page, {
    fixtures: SH_FIXTURES_OK,
    raw: {
      '**/api/health': {
        body: { status: 'degraded', checks: { database: true, redis: false } },
      },
      '**/api/streams/status': {
        body: {
          status: 'degraded',
          workers: [
            { worker_id: 'celery@worker-inference-01', status: 'online', active_tasks: 2 },
            { worker_id: 'celery@worker-quality-02', status: 'offline', active_tasks: 0 },
          ],
        },
      },
    },
  })
  await openStreamHealth(page)
  await page.getByText('celery@worker-quality-02').waitFor({ timeout: 15_000 })
  await shootBothThemes(page, SH, 'degraded', true)
})

test('stream-health — hover (botão Atualizar + card de câmera) [só dark]', async ({ page }) => {
  await setupApp(page, { fixtures: SH_FIXTURES_OK, raw: SH_RAW_OK })
  await openStreamHealth(page)

  await page.getByRole('button', { name: /Atualizar/ }).hover()
  await page.waitForTimeout(300)
  await shoot(page, SH, 'dark-hover-atualizar')

  await page.getByText('Câmera Pátio Norte').hover()
  await page.waitForTimeout(300)
  await shoot(page, SH, 'dark-hover-camera-card')
})
