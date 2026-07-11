/**
 * Auditoria visual — Grupo 17: Investigação (/epi/investigation, tier 1)
 *                              + Contagem (/epi/counting, tier 2).
 *
 * Endpoints reais consumidos:
 *
 * InvestigationPage (src/pages/epi/InvestigationPage.tsx):
 * - GET /api/v1/events/search?page&per_page&class_name[]&module_code&from&to&min_confidence
 *     → envelope { success, data: { events, total, page, per_page, pages } }
 * - GET /api/v1/events/timeline?bucket&...  → { success, data: { buckets, bucket_size } }
 *   ATENÇÃO (bug WS4): a página checa `res.success` — o envelope padrão da API
 *   é { status: 'success', data } (sem `success`), então o wrapper `fixtures`
 *   do harness cai no branch de ERRO ("Erro ao buscar eventos"). Por isso os
 *   estados ricos usam `raw` com { success: true, data }. O estado
 *   `empty-ws4-envelope` captura exatamente esse defeito com o envelope padrão.
 *   Nota: api.ts prefixa API_BASE='/api', então a URL final é /api/api/v1/... —
 *   os globs casam pelo sufixo `**\/api/v1/events/...**`.
 *
 * CountingPage (src/pages/CountingPage.tsx):
 * - GET /api/cameras                      → { status, data: { cameras } }
 * - GET /api/counting/sessions            → { status, data: { sessions } }
 * - GET /api/counting/sessions/{id}/stats → { status, data: { counts, total } }
 */
import { test } from '@playwright/test'
import { setupApp, shootBothThemes, shoot, settle, gotoAudit } from './helpers'

const SLUG_INV = 'investigation'
const ROUTE_INV = '/epi/investigation'
const SLUG_CNT = 'counting'
const ROUTE_CNT = '/epi/counting'

/* ── Fixtures pt-BR — Investigação ─────────────────────────────── */

const FRAME_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">
  <rect width="640" height="360" fill="#1e2330"/>
  <rect x="180" y="90" width="120" height="200" fill="none" stroke="#ef4444" stroke-width="3"/>
  <text x="185" y="82" fill="#ef4444" font-family="sans-serif" font-size="16">no_helmet 0.92</text>
  <text x="320" y="340" fill="#8ba3bc" font-family="sans-serif" font-size="18" text-anchor="middle">Câmera Pátio Norte — frame de evidência</text>
</svg>`

const FRAME_URL = (id: string) => `https://cdn.recognition.dev/frames/${id}.jpg`

const EVENTS = [
  {
    id: 'ev-001',
    camera_id: 'cam-01',
    module_code: 'epi',
    confidence: 0.92,
    violations: ['no_helmet', 'vest'],
    evidence_key: 'frames/ev-001.jpg',
    created_at: '2026-07-06T08:14:23Z',
    frame_url: FRAME_URL('ev-001'),
  },
  {
    id: 'ev-002',
    camera_id: 'cam-02',
    module_code: 'epi',
    confidence: 0.87,
    violations: ['no_vest'],
    evidence_key: 'frames/ev-002.jpg',
    created_at: '2026-07-06T07:52:10Z',
    frame_url: FRAME_URL('ev-002'),
  },
  {
    id: 'ev-003',
    camera_id: 'cam-03',
    module_code: 'epi',
    confidence: 0.78,
    violations: ['no_gloves', 'no_glasses'],
    evidence_key: 'frames/ev-003.jpg',
    created_at: '2026-07-06T07:31:44Z',
    frame_url: FRAME_URL('ev-003'),
  },
  {
    id: 'ev-004',
    camera_id: 'cam-01',
    module_code: 'epi',
    confidence: 0.95,
    violations: ['helmet', 'vest'],
    evidence_key: null,
    created_at: '2026-07-06T06:58:02Z',
    frame_url: null, // sem frame → placeholder "sem frame"
  },
  {
    id: 'ev-005',
    camera_id: 'cam-04',
    module_code: 'epi',
    confidence: 0.64,
    violations: ['no_helmet'],
    evidence_key: 'frames/ev-005.jpg',
    created_at: '2026-07-05T17:20:38Z',
    frame_url: FRAME_URL('ev-005'),
  },
  {
    id: 'ev-006',
    camera_id: 'cam-05',
    module_code: 'fueling',
    confidence: 0.71,
    violations: ['truck', 'plate'],
    evidence_key: 'frames/ev-006.jpg',
    created_at: '2026-07-05T16:05:11Z',
    frame_url: FRAME_URL('ev-006'),
  },
]

const SEARCH_RICH = { events: EVENTS, total: 47, page: 1, per_page: 20, pages: 3 }

const TIMELINE_RICH = {
  bucket_size: 'hour',
  buckets: [
    { bucket: '2026-07-06T00:00:00Z', count: 2 },
    { bucket: '2026-07-06T01:00:00Z', count: 1 },
    { bucket: '2026-07-06T02:00:00Z', count: 0 },
    { bucket: '2026-07-06T03:00:00Z', count: 3 },
    { bucket: '2026-07-06T04:00:00Z', count: 5 },
    { bucket: '2026-07-06T05:00:00Z', count: 4 },
    { bucket: '2026-07-06T06:00:00Z', count: 9 },
    { bucket: '2026-07-06T07:00:00Z', count: 12 },
    { bucket: '2026-07-06T08:00:00Z', count: 7 },
    { bucket: '2026-07-06T09:00:00Z', count: 3 },
    { bucket: '2026-07-06T10:00:00Z', count: 1 },
    { bucket: '2026-07-06T11:00:00Z', count: 0 },
  ],
}

/** Envelope { success, data } exigido pela página (ver bug WS4 no cabeçalho). */
const invRaw = (search: unknown, timeline: unknown) => ({
  '**/api/v1/events/search**': { status: 200, body: { success: true, data: search } },
  '**/api/v1/events/timeline**': { status: 200, body: { success: true, data: timeline } },
  '**/cdn.recognition.dev/**': { status: 200, body: FRAME_SVG, contentType: 'image/svg+xml' },
})

async function gotoInvRich(page: import('@playwright/test').Page) {
  // O shell tem overflow:hidden — fullPage não alcança abaixo da dobra.
  // Viewport alto revela a lista de eventos (thumbnails) + paginação.
  await page.setViewportSize({ width: 1440, height: 1900 })
  await setupApp(page, { raw: invRaw(SEARCH_RICH, TIMELINE_RICH) })
  await gotoAudit(page, ROUTE_INV)
  await page.getByText('Investigação de Eventos').waitFor()
  await page.getByText('92% confiança').waitFor()
  await settle(page)
}

/* ── Investigação — estados base ────────────────────────────────── */

test('investigation — default (rico, filtros + timeline + thumbnails + paginação)', async ({ page }) => {
  await gotoInvRich(page)
  await shootBothThemes(page, SLUG_INV, 'default', true)
})

test('investigation — filters-active (chips selecionados + confiança mín.)', async ({ page }) => {
  await gotoInvRich(page)
  await page.getByRole('button', { name: 'no_helmet', exact: true }).click()
  await page.getByRole('button', { name: 'no_vest', exact: true }).click()
  await page.getByPlaceholder('0.0 – 1.0').fill('0.7')
  await page.getByText('Limpar filtros de classe').waitFor()
  await settle(page)
  await shootBothThemes(page, SLUG_INV, 'filters-active', true)
})

test('investigation — empty', async ({ page }) => {
  await setupApp(page, {
    raw: invRaw(
      { events: [], total: 0, page: 1, per_page: 20, pages: 1 },
      { buckets: [], bucket_size: 'hour' }
    ),
  })
  await gotoAudit(page, ROUTE_INV)
  await page.getByText('Nenhum evento encontrado para os filtros aplicados').waitFor()
  await settle(page)
  await shootBothThemes(page, SLUG_INV, 'empty', true)
})

test('investigation — empty com envelope padrão da API (bug WS4)', async ({ page }) => {
  // Catch-all do harness devolve o envelope PADRÃO {status:'success', data:{}}.
  // A página checa `res.success` → cai no branch de erro mesmo com API 200.
  await setupApp(page)
  await gotoAudit(page, ROUTE_INV)
  await page.getByText('Erro ao buscar eventos').waitFor()
  await settle(page)
  await shootBothThemes(page, SLUG_INV, 'empty-ws4-envelope', true)
})

test('investigation — loading (stall)', async ({ page }) => {
  await setupApp(page, {
    stall: ['**/api/v1/events/search**', '**/api/v1/events/timeline**'],
  })
  await gotoAudit(page, ROUTE_INV)
  await page.getByText('Investigação de Eventos').waitFor()
  await page.getByText('Buscando…').waitFor()
  // settle() esperaria networkidle que nunca chega (requests penduradas)
  await page.waitForTimeout(1500)
  await shootBothThemes(page, SLUG_INV, 'loading', true)
})

test('investigation — error (500)', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/v1/events/search**': {
        status: 500,
        body: { status: 'error', error: 'Erro interno do servidor' },
      },
      '**/api/v1/events/timeline**': {
        status: 200,
        body: { success: true, data: { buckets: [], bucket_size: 'hour' } },
      },
    },
  })
  await gotoAudit(page, ROUTE_INV)
  await page.getByText('Não foi possível conectar à API').waitFor()
  await page.waitForTimeout(1200) // deixa o toast de erro aparecer
  await shootBothThemes(page, SLUG_INV, 'error', true)
})

/* ── Investigação — modal de frame ampliado ─────────────────────── */

test('investigation — modal frame ampliado', async ({ page }) => {
  await gotoInvRich(page)
  // Clique na linha do ev-001 (92%) abre o modal de frame ampliado
  await page.getByText('92% confiança').click()
  await page.getByRole('button', { name: '✕' }).waitFor()
  await settle(page, 500)
  await shootBothThemes(page, SLUG_INV, 'modal-frame')
})

/* ── Investigação — hovers (só tema dark) ───────────────────────── */

test('investigation — hovers (dark)', async ({ page }) => {
  await gotoInvRich(page)

  await page.getByRole('button', { name: 'no_helmet', exact: true }).hover()
  await page.waitForTimeout(300)
  await shoot(page, SLUG_INV, 'hover-class-chip')

  await page.getByText('92% confiança').hover()
  await page.waitForTimeout(300)
  await shoot(page, SLUG_INV, 'hover-event-row')
})

/* ── Fixtures pt-BR — Contagem ──────────────────────────────────── */

const CAMERAS_CNT = [
  { id: 'cam-01', name: 'Câmera Pátio Norte', is_streaming: true },
  { id: 'cam-02', name: 'Câmera Doca 02', is_streaming: true },
  { id: 'cam-03', name: 'Câmera Portaria Principal', is_streaming: false },
  { id: 'cam-04', name: 'Câmera Almoxarifado', is_streaming: false },
  { id: 'cam-05', name: 'Câmera Linha de Produção A', is_streaming: true },
]

const SESSIONS_CNT = [
  {
    id: 'sess-8f2c41aa-0001',
    camera_id: 'cam-02',
    module_code: 'epi',
    status: 'active',
    started_at: '2026-07-06T09:12:00Z',
    truck_plate: 'RVB4D23',
    direction: 'load',
    acceptance_status: 'pending',
  },
  {
    id: 'sess-3b9d02fe-0002',
    camera_id: 'cam-01',
    module_code: 'epi',
    status: 'active',
    started_at: '2026-07-06T08:47:00Z',
    truck_plate: 'BRA2E19',
    direction: 'unload',
    acceptance_status: 'accepted',
  },
  {
    id: 'sess-77aa10cd-0003',
    camera_id: 'cam-05',
    module_code: 'epi',
    status: 'active',
    started_at: '2026-07-06T08:05:00Z',
    truck_plate: null,
    direction: 'load',
    acceptance_status: 'rejected',
  },
]

const STATS_CNT = {
  counts: { helmet: 34, no_helmet: 5, vest: 28, no_vest: 9, gloves: 17, no_gloves: 3 },
  total: 96,
}

/* ── Contagem — estados (tier 2: default + empty) ───────────────── */

test('counting — default (rico, sessão ativa + stats + outras sessões)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/cameras': { cameras: CAMERAS_CNT },
      '**/api/counting/sessions': { sessions: SESSIONS_CNT },
      '**/api/counting/sessions/*/stats': STATS_CNT,
    },
  })
  await gotoAudit(page, ROUTE_CNT)
  await page.getByText('Contagem DeepSORT').waitFor()
  await page.getByText('Outras sessões ativas').waitFor()
  await page.getByText('Capacete', { exact: true }).waitFor() // grid de stats renderizado
  await settle(page)
  await shootBothThemes(page, SLUG_CNT, 'default', true)
})

test('counting — empty', async ({ page }) => {
  await setupApp(page) // catch-all {} → sem câmeras, sem sessões
  await gotoAudit(page, ROUTE_CNT)
  await page.getByText('Nenhuma contagem ativa').waitFor()
  await settle(page)
  await shootBothThemes(page, SLUG_CNT, 'empty', true)
})
