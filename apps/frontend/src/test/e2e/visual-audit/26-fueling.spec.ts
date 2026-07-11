/**
 * Auditoria visual — Grupo 26-fueling (tier 2): módulo Carga & Descarga.
 *
 * NOTA DE AUDITORIA: o briefing dizia "FuelingPage é placeholder Em breve",
 * mas na staging atual a FuelingPage é um dashboard COMPLETO com 3 abas
 * (Dashboard / Monitoramento de Baias / Eventos). O FuelingPlaceholder.tsx
 * existe mas NÃO é mais roteado. Capturamos a realidade.
 *
 * Rotas REAIS (AppRoutes.tsx):
 * - /fueling            → GET /api/fueling/dashboard?period=…  → data = DashboardData
 *                         GET /api/fueling/bays                → data = { bays: Bay[] }
 *                         GET /api/cameras                     → data = { cameras: Camera[] }
 *                         GET /api/admin/demo-videos?module=fueling → data = { videos: [] }
 *                         Abas deep-linkáveis via ?tab=baias|eventos (mesmo mecanismo da sidebar)
 * - /fueling/validation → GET /api/counting/sessions/validation-report?… → data = ValidationReport
 *
 * Tier 2: default + empty por página; abas capturadas por serem estados
 * distintos e baratos (deep-link). Validation ganha `error` (raw 500) porque
 * a página tem fallback dedicado ("Não foi possível carregar o relatório").
 */
import { test } from '@playwright/test'
import { setupApp, shootBothThemes, settle, gotoAudit } from './helpers'

/* ── Helpers de data ────────────────────────────────────────────── */

const minsAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()
const hoursAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString()
const daysAgoIso = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString().slice(0, 10)

/* ═══════════════════════════════════════════════════════════════════
 * 1) /fueling — Controle de Carregamento (dashboard + baias + eventos)
 * ═══════════════════════════════════════════════════════════════════ */

const FUELING_SLUG = 'fueling'

const DASHBOARD_RICO = {
  kpis: {
    total_carregado: 42,
    tempo_medio_minutos: 38,
    total_itens_movimentados: 12480,
    itens_nao_conformes: 187,
    taxa_nao_conformidade: 1.5,
    eventos_nao_conformidade: 23,
    taxa_ocupacao_percent: 78,
  },
  top_baias_produtivas: [
    { baia: 'Baia 03', itens: 3120 },
    { baia: 'Baia 01', itens: 2840 },
    { baia: 'Baia 05', itens: 2210 },
  ],
  top_baias_perda: [
    { baia: 'Baia 05', perda: 84 },
    { baia: 'Baia 02', perda: 57 },
    { baia: 'Baia 04', perda: 31 },
  ],
  series_operacoes_diarias: [
    { dia: '30/06', operacoes: 34 },
    { dia: '01/07', operacoes: 41 },
    { dia: '02/07', operacoes: 38 },
    { dia: '03/07', operacoes: 46 },
    { dia: '04/07', operacoes: 29 },
    { dia: '05/07', operacoes: 22 },
    { dia: '06/07', operacoes: 42 },
  ],
  series_tempo_por_baia: [
    { baia: 'Baia 01', tempo: 34 },
    { baia: 'Baia 02', tempo: 41 },
    { baia: 'Baia 03', tempo: 29 },
    { baia: 'Baia 04', tempo: 52 },
    { baia: 'Baia 05', tempo: 37 },
    { baia: 'Baia 06', tempo: 44 },
  ],
  pizza_causas_perda: [
    { name: 'Caixa avariada', value: 42 },
    { name: 'Item trocado', value: 28 },
    { name: 'Falta de item', value: 18 },
    { name: 'Outros', value: 12 },
  ],
}

const BAYS_RICO = {
  bays: [
    { id: 1, nome: 'Baia 01', status: 'active', operador: 'Carlos Menezes', placa: 'RVB2C34', total_itens: 1840, progresso: 72 },
    { id: 2, nome: 'Baia 02', status: 'active', operador: 'Marina Duarte', placa: 'FKT7A81', total_itens: 960, progresso: 38 },
    { id: 3, nome: 'Baia 03', status: 'idle', operador: null, placa: null, total_itens: 0, progresso: 0 },
    { id: 4, nome: 'Baia 04', status: 'maintenance', operador: null, placa: null, total_itens: 0, progresso: 0 },
    { id: 5, nome: 'Baia 05', status: 'active', operador: 'Antônio Ferreira Lima', placa: 'QXP4D18', total_itens: 2130, progresso: 91 },
    { id: 6, nome: 'Baia 06', status: 'idle', operador: null, placa: null, total_itens: 0, progresso: 0 },
  ],
}

const EVENTOS_RICO = {
  events: [
    { id: 'evt-001', camera_id: 'a1b2c3d4-e5f6-4a1b-9c2d-000000000001', class_name: 'truck', confidence: 0.94, created_at: minsAgo(3) },
    { id: 'evt-002', camera_id: 'a1b2c3d4-e5f6-4a1b-9c2d-000000000001', class_name: 'plate', confidence: 0.88, created_at: minsAgo(3) },
    { id: 'evt-003', camera_id: 'b2c3d4e5-f6a7-4b2c-8d3e-000000000002', class_name: 'product_box', confidence: 0.67, created_at: minsAgo(11) },
    { id: 'evt-004', camera_id: 'b2c3d4e5-f6a7-4b2c-8d3e-000000000002', class_name: 'pallet', confidence: 0.91, created_at: minsAgo(24) },
    { id: 'evt-005', camera_id: 'c3d4e5f6-a7b8-4c3d-9e4f-000000000003', class_name: 'forklift', confidence: 0.46, created_at: hoursAgo(1) },
    { id: 'evt-006', camera_id: 'a1b2c3d4-e5f6-4a1b-9c2d-000000000001', class_name: 'product_box', confidence: null, created_at: hoursAgo(2) },
    { id: 'evt-007', camera_id: 'c3d4e5f6-a7b8-4c3d-9e4f-000000000003', class_name: 'truck', confidence: 0.82, created_at: hoursAgo(3) },
  ],
}

/** Fixtures comuns da FuelingPage — sem câmeras ativas nem vídeo demo para
 *  que os cards de baia rendam o placeholder determinístico "Câmera não
 *  configurada" (CameraPlayer/HLS fora do escopo desta captura). */
const FUELING_FIXTURES = {
  '**/api/fueling/dashboard*': DASHBOARD_RICO,
  '**/api/fueling/bays': BAYS_RICO,
  '**/api/fueling/events*': EVENTOS_RICO,
  '**/api/cameras': { cameras: [] },
  '**/api/admin/demo-videos*': { videos: [] },
}

test('fueling — default (aba Dashboard rica)', async ({ page }) => {
  await setupApp(page, { fixtures: FUELING_FIXTURES })
  await gotoAudit(page, '/fueling')
  await page.getByText('Controle de Carregamento').waitFor()
  await page.getByText('Total Carregado').waitFor()
  await page.getByText('Causas de Não Conformidade').waitFor()
  await settle(page)
  await shootBothThemes(page, FUELING_SLUG, 'default', true)
})

test('fueling — empty (dashboard sem dados)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...FUELING_FIXTURES, '**/api/fueling/dashboard*': { no_data: true } },
  })
  await gotoAudit(page, '/fueling')
  await page.getByText('Nenhum dado de carregamento disponível').waitFor()
  await settle(page)
  await shootBothThemes(page, FUELING_SLUG, 'empty')
})

test('fueling — tab-baias (mosaico com 6 baias, câmeras não configuradas)', async ({ page }) => {
  await setupApp(page, { fixtures: FUELING_FIXTURES })
  await gotoAudit(page, '/fueling')
  await page.getByText('Controle de Carregamento').waitFor()
  await page.getByRole('button', { name: 'Monitoramento de Baias' }).click()
  await page.getByText('Baia 01').waitFor()
  await page.getByText('Carlos Menezes').waitFor()
  await settle(page)
  await shootBothThemes(page, FUELING_SLUG, 'tab-baias', true)
})

test('fueling — tab-eventos (tabela de detecções)', async ({ page }) => {
  await setupApp(page, { fixtures: FUELING_FIXTURES })
  await gotoAudit(page, '/fueling')
  await page.getByText('Controle de Carregamento').waitFor()
  await page.getByRole('button', { name: 'Eventos' }).click()
  await page.getByText('Eventos Recentes').waitFor()
  await page.getByText('Empilhadeira').waitFor()
  await settle(page)
  await shootBothThemes(page, FUELING_SLUG, 'tab-eventos', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 2) /fueling/validation — Validação de Contagem (CD-07)
 * ═══════════════════════════════════════════════════════════════════ */

const VALIDATION_SLUG = 'fueling-validation'

const BAY_A = '7f3e2a10-1111-4aaa-8bbb-cccc00000001'
const BAY_B = '8a4f3b21-2222-4bbb-9ccc-dddd00000002'
const CAM_A = 'a1b2c3d4-e5f6-4a1b-9c2d-000000000001'
const CAM_B = 'b2c3d4e5-f6a7-4b2c-8d3e-000000000002'

const REPORT_RICO = {
  threshold_pct: 5,
  period: { start: daysAgoIso(7), end: daysAgoIso(0) },
  bay_id: null,
  sessions: [
    {
      id: 'c1000000-0000-4000-8000-000000000001', bay_id: BAY_A, camera_id: CAM_A,
      truck_plate: 'RVB2C34', direction: 'load', started_at: hoursAgo(2), ended_at: hoursAgo(1),
      acceptance_status: 'accepted', video_clip_url: null,
      manual_count: 248, system_count: 250, abs_error: 2, error_pct: 0.81, passed: true,
    },
    {
      id: 'c1000000-0000-4000-8000-000000000002', bay_id: BAY_A, camera_id: CAM_A,
      truck_plate: 'FKT7A81', direction: 'unload', started_at: hoursAgo(6), ended_at: hoursAgo(5),
      acceptance_status: 'pending', video_clip_url: null,
      manual_count: 312, system_count: 309, abs_error: 3, error_pct: 0.96, passed: true,
    },
    {
      id: 'c1000000-0000-4000-8000-000000000003', bay_id: BAY_B, camera_id: CAM_B,
      truck_plate: 'QXP4D18', direction: 'load', started_at: hoursAgo(26), ended_at: hoursAgo(25),
      acceptance_status: 'rejected', video_clip_url: null,
      manual_count: 180, system_count: 196, abs_error: 16, error_pct: 8.89, passed: false,
    },
    {
      id: 'c1000000-0000-4000-8000-000000000004', bay_id: BAY_B, camera_id: CAM_B,
      truck_plate: 'JHM9E55', direction: 'load', started_at: hoursAgo(30), ended_at: hoursAgo(29),
      acceptance_status: 'pending', video_clip_url: null,
      manual_count: 421, system_count: 419, abs_error: 2, error_pct: 0.48, passed: true,
    },
    {
      id: 'c1000000-0000-4000-8000-000000000005', bay_id: null, camera_id: CAM_A,
      truck_plate: null, direction: null, started_at: hoursAgo(50), ended_at: hoursAgo(49),
      acceptance_status: null, video_clip_url: null,
      manual_count: 96, system_count: 102, abs_error: 6, error_pct: 6.25, passed: false,
    },
    {
      id: 'c1000000-0000-4000-8000-000000000006', bay_id: BAY_A, camera_id: CAM_A,
      truck_plate: 'PZX3F77', direction: 'unload', started_at: hoursAgo(74), ended_at: hoursAgo(73),
      acceptance_status: 'accepted', video_clip_url: null,
      manual_count: 213, system_count: 207, abs_error: 6, error_pct: 2.82, passed: true,
    },
  ],
  daily: [
    { day: daysAgoIso(0), sessions: 2, system_total: 559, manual_total: 560, abs_error: 1, error_pct: 0.18, passed: true },
    { day: daysAgoIso(1), sessions: 2, system_total: 615, manual_total: 601, abs_error: 14, error_pct: 2.28, passed: true },
    { day: daysAgoIso(2), sessions: 1, system_total: 102, manual_total: 96, abs_error: 6, error_pct: 5.88, passed: false },
    { day: daysAgoIso(3), sessions: 1, system_total: 207, manual_total: 213, abs_error: 6, error_pct: 2.9, passed: true },
  ],
  summary: {
    sessions_validated: 6, system_count: 1483, manual_count: 1470,
    abs_error: 13, error_pct: 0.88, passed: true,
  },
}

const REPORT_VAZIO = {
  threshold_pct: 5,
  period: { start: daysAgoIso(7), end: daysAgoIso(0) },
  bay_id: null,
  sessions: [],
  daily: [],
  summary: { sessions_validated: 0, system_count: 0, manual_count: 0, abs_error: 0, error_pct: null, passed: true },
}

test('fueling-validation — default (6 sessões, agregado diário)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/counting/sessions/validation-report*': REPORT_RICO },
  })
  await gotoAudit(page, '/fueling/validation')
  await page.getByText('Validação de Contagem').waitFor()
  await page.getByText('RVB2C34').waitFor()
  await page.getByText('Agregado diário').waitFor()
  await settle(page)
  await shootBothThemes(page, VALIDATION_SLUG, 'default', true)
})

test('fueling-validation — empty (sem sessões no período)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/counting/sessions/validation-report*': REPORT_VAZIO },
  })
  await gotoAudit(page, '/fueling/validation')
  await page.getByText('Validação de Contagem').waitFor()
  await page.getByText('Nenhuma sessão validada no período').waitFor()
  await settle(page)
  await shootBothThemes(page, VALIDATION_SLUG, 'empty')
})

test('fueling-validation — error (500 no relatório)', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/counting/sessions/validation-report*': {
        status: 500,
        body: { status: 'error', message: 'Erro interno no servidor' },
      },
    },
  })
  await gotoAudit(page, '/fueling/validation')
  await page.getByText('Não foi possível carregar o relatório').waitFor()
  await settle(page)
  await shootBothThemes(page, VALIDATION_SLUG, 'error')
})
