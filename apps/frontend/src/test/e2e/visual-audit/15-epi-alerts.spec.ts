/**
 * Auditoria visual — grupo 15-epi-alerts (tier 1).
 *
 * /epi/alerts — EpiAlerts é wrapper de AlertsHistoryPage: tabela de alertas com
 * filtros (datas, tipo de violação, status), paginação, export CSV, hover-ack
 * (1s de hover numa linha pendente dispara acknowledge!) e modal de evidência
 * com snapshot + bounding boxes (task-066: modal com background hardcoded
 * '#1a1d23' inline — candidato a defeito white-label).
 *
 * Endpoints reais consumidos pela página:
 *   GET  /api/alerts?start_date&end_date&violation_type&acknowledged&page&per_page
 *        → { alerts[], total, page, per_page, pages }
 *   GET  /api/alerts/:id/snapshot      → { snapshot_url }
 *   POST /api/alerts/:id/acknowledge   → (envelope success)
 *   GET  /api/alerts/export?...        → CSV blob (api.downloadBlob)
 *
 * CUIDADO hover-ack: onMouseEnter numa linha NÃO reconhecida arma timer de 1s
 * que dispara POST acknowledge + reload da tabela. Depois de qualquer click em
 * linha, mover o mouse pra fora (page.mouse.move) pra cancelar o timer; hover
 * screenshots usam linha JÁ reconhecida.
 */
import { test, type Page } from '@playwright/test'
import { setupApp, shootBothThemes, shoot, settle, gotoAudit } from './helpers'

const SCREEN = 'epi-alerts'
const ROUTE = '/epi/alerts'

/* ------------------------------------------------------------------ */
/* Fixtures pt-BR — Tenant RVB Industrial                              */
/* ------------------------------------------------------------------ */

/** Snapshot fake de evidência (SVG ASCII-only → data URL base64). */
const SNAPSHOT_SVG = [
  '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720">',
  '<rect width="1280" height="720" fill="#2b313b"/>',
  '<rect x="0" y="520" width="1280" height="200" fill="#3a414d"/>',
  '<rect x="700" y="220" width="420" height="300" fill="#4a5262" rx="6"/>',
  '<rect x="740" y="260" width="140" height="220" fill="#39404c"/>',
  // silhueta na região do bounding box (20%/15% → x=256 y=108 w=320 h=360)
  '<circle cx="416" cy="170" r="42" fill="#8a93a3"/>',
  '<rect x="356" y="215" width="120" height="180" rx="18" fill="#77808f"/>',
  '<rect x="368" y="395" width="38" height="120" fill="#666f7d"/>',
  '<rect x="426" y="395" width="38" height="120" fill="#666f7d"/>',
  '<text x="24" y="44" fill="#d7dde6" font-family="monospace" font-size="26">',
  'CAM 02 - DOCA DE CARGA 2 - 04/07/2026 14:32:18</text>',
  '<text x="1120" y="700" fill="#9aa3b0" font-family="monospace" font-size="22">REC</text>',
  '</svg>',
].join('')

const SNAPSHOT_URL = `data:image/svg+xml;base64,${Buffer.from(SNAPSHOT_SVG).toString('base64')}`

const ALERTS = [
  {
    id: 'al-1',
    camera_id: 'cam-0001-patio-norte',
    camera_name: 'Câmera Pátio Norte',
    violations: [{ class: 'no_helmet', confidence: 0.94 }],
    acknowledged: false,
    created_at: '2026-07-04T17:32:00Z',
    evidence_key: 'evidence/rvb/al-1.jpg',
  },
  {
    id: 'al-2',
    camera_id: 'cam-0002-doca-2',
    camera_name: 'Câmera Doca de Carga 2',
    violations: [
      { class: 'no_vest', confidence: 0.88 },
      { class: 'no_helmet', confidence: 0.76 },
    ],
    acknowledged: false,
    created_at: '2026-07-04T14:32:18Z',
    evidence_key: 'evidence/rvb/al-2.jpg',
  },
  {
    id: 'al-3',
    camera_id: 'cam-0003-linha-1',
    camera_name: 'Câmera Linha de Produção',
    violations: [{ class: 'no_gloves', confidence: 0.71 }],
    acknowledged: true,
    created_at: '2026-07-04T11:05:44Z',
    evidence_key: 'evidence/rvb/al-3.jpg',
  },
  {
    id: 'al-4',
    camera_id: 'cam-0004-portaria',
    camera_name: 'Câmera Portaria Principal',
    violations: [{ class: 'no_safety_glasses', confidence: 0.83 }],
    acknowledged: true,
    created_at: '2026-07-03T19:48:10Z',
    evidence_key: 'evidence/rvb/al-4.jpg',
  },
  {
    id: 'al-5',
    camera_id: 'cam-0005-almoxarifado',
    camera_name: 'Câmera Almoxarifado',
    violations: [{ class: 'no_helmet', confidence: 0.97 }],
    acknowledged: false,
    created_at: '2026-07-03T16:21:37Z',
    // SEM evidence_key → modal sem snapshot
  },
  {
    id: 'al-6',
    camera_id: 'cam-0006-estac-sul',
    camera_name: 'Câmera Estacionamento Sul',
    violations: [{ class: 'no_vest', confidence: 0.62 }],
    acknowledged: false,
    created_at: '2026-07-03T09:14:02Z',
    evidence_key: 'evidence/rvb/al-6.jpg',
  },
  {
    id: 'al-7',
    camera_id: 'cam-0001-patio-norte',
    camera_name: 'Câmera Pátio Norte',
    violations: [
      { class: 'no_helmet', confidence: 0.91 },
      { class: 'no_gloves', confidence: 0.68 },
    ],
    acknowledged: true,
    created_at: '2026-07-02T22:40:55Z',
    evidence_key: 'evidence/rvb/al-7.jpg',
  },
]

const ALERTS_RESPONSE = {
  alerts: ALERTS,
  total: 42,
  page: 1,
  per_page: 20,
  pages: 3,
}

/**
 * '**\/api/alerts*' cobre a lista (query string não tem '/', e '*' não
 * atravessa '/'), sem engolir /alerts/:id/snapshot nem /alerts/:id/acknowledge
 * (esses caem no snapshot fixture ou no catch-all do setupApp).
 * O snapshot é registrado DEPOIS → precedência garantida.
 */
const RICH_FIXTURES: Record<string, unknown> = {
  '**/api/alerts*': ALERTS_RESPONSE,
  '**/api/alerts/*/snapshot': { snapshot_url: SNAPSHOT_URL },
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

async function openPage(page: Page) {
  await gotoAudit(page, ROUTE)
  await page.getByText('Histórico de Alertas').waitFor({ timeout: 30_000 })
  await page.getByText('Câmera Doca de Carga 2').waitFor({ timeout: 15_000 })
  await settle(page)
}

/**
 * Abre o modal de detalhe clicando na linha e IMEDIATAMENTE tira o mouse de
 * cima (cancela o hover-ack de 1s das linhas pendentes).
 */
async function openAlertModal(page: Page, rowText: string) {
  await page.getByText(rowText).first().click()
  await page.mouse.move(4, 4)
  await page.getByText('Detalhe do Alerta').waitFor({ timeout: 10_000 })
}

/* ------------------------------------------------------------------ */
/* Estados                                                             */
/* ------------------------------------------------------------------ */

test('epi-alerts — default (tabela rica + filtros + paginação)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)
  await page.getByText('Total: 42 alertas').waitFor({ timeout: 10_000 })
  await shootBothThemes(page, SCREEN, 'default', true)
})

test('epi-alerts — empty (nenhum alerta)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/alerts*': { alerts: [], total: 0, page: 1, per_page: 20, pages: 1 },
    },
  })
  await gotoAudit(page, ROUTE)
  await page.getByText('Nenhum alerta encontrado').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, SCREEN, 'empty')
})

test('epi-alerts — loading (GET /alerts nunca responde)', async ({ page }) => {
  await setupApp(page, { stall: ['**/api/alerts*'] })
  await gotoAudit(page, ROUTE)
  await page.getByText('Histórico de Alertas').waitFor({ timeout: 30_000 })
  // Sem settle: networkidle nunca acontece com request pendurada.
  await page.waitForTimeout(2500)
  await shootBothThemes(page, SCREEN, 'loading')
})

test('epi-alerts — error (GET /alerts 500)', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/alerts*': {
        status: 500,
        body: { status: 'error', error: 'Falha ao consultar alertas' },
      },
    },
  })
  await gotoAudit(page, ROUTE)
  await page.getByText('Histórico de Alertas').waitFor({ timeout: 30_000 })
  // Página cai no catch (data null) → caixa vazia; toast pode aparecer junto.
  await page.getByText('Nenhum alerta encontrado').waitFor({ timeout: 15_000 }).catch(() => {})
  await page.waitForTimeout(800)
  await shootBothThemes(page, SCREEN, 'error')
})

test('epi-alerts — exporting (export CSV pendurado → botão "Exportando...")', async ({ page }) => {
  await setupApp(page, {
    fixtures: RICH_FIXTURES,
    stall: ['**/api/alerts/export*'],
  })
  await openPage(page)
  await page.getByRole('button', { name: 'Exportar CSV' }).click()
  await page.mouse.move(4, 4)
  await page.getByText('Exportando...').waitFor({ timeout: 10_000 })
  await page.waitForTimeout(400)
  await shootBothThemes(page, SCREEN, 'exporting')
})

/* --------------------------- Modais ------------------------------- */

test('epi-alerts — modal-evidencia (snapshot + bounding boxes)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)
  await openAlertModal(page, 'Câmera Doca de Carga 2')
  await page.locator('img[alt="Evidência"]').waitFor({ timeout: 10_000 })
  await settle(page, 600)
  await shootBothThemes(page, SCREEN, 'modal-evidencia')
})

test('epi-alerts — modal-sem-evidencia (alerta sem evidence_key)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)
  await openAlertModal(page, 'Câmera Almoxarifado')
  await settle(page, 400)
  await shootBothThemes(page, SCREEN, 'modal-sem-evidencia')
})

/* --------------------------- Hover (só dark) ---------------------- */

test('epi-alerts — hover (linha reconhecida + Exportar CSV)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)

  // Linha JÁ reconhecida (al-3) — sem risco de disparar o hover-ack de 1s.
  await page.getByText('Câmera Linha de Produção').hover()
  await page.waitForTimeout(300)
  await shoot(page, SCREEN, 'dark-hover-row')

  await page.mouse.move(4, 4)
  await page.getByRole('button', { name: 'Exportar CSV' }).hover()
  await page.waitForTimeout(300)
  await shoot(page, SCREEN, 'dark-hover-export')
})
