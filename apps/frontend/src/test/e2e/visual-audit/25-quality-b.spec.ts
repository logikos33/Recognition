/**
 * Visual-audit — Grupo 25-quality-b (tier 2: default + vazio; modal principal barato).
 *
 * Páginas e subpaths REAIS (confirmados no QualityLayout.tsx):
 *   - /quality/reports                              → QualityReportsPage (lazy)
 *   - /quality/rework                               → QualityReworkPage (lazy)
 *   - /quality/training                             → TrainingPage (compartilhada c/ EPI)
 *   - /quality/inspections/:inspectionId/annotate   → QualityAnnotationWorkspace
 *     (a rota "/quality/annotation" NÃO existe — catch-all redireciona p/ cameras)
 *   - /quality/andon/:cameraId                      → QualityAndonDisplay
 *     (a rota "/quality/andon" sem :cameraId NÃO existe)
 *   - /tablet/:station                              → TabletKiosk (rota pública, sem JWT)
 *
 * Endpoints reais descobertos no source:
 *   QualityReportsPage:
 *     - GET /api/v1/quality/gate/pieces?status=approved&per_page=200… → {pieces: QualityPiece[]}
 *     - POST /api/v1/quality/gate/pieces/<id>/export-wiser (só via clique)
 *     - POST /api/v1/quality/gate/export-wiser/batch (só via clique)
 *   QualityReworkPage:
 *     - GET /api/v1/quality/gate/reworks?page=&per_page=20…          → {reworks, total}
 *     - GET /api/v1/quality/gate/stats/rework                        → ReworkMetrics
 *     - GET  <API_BASE>/api/v1/quality/gate/photos/<path>            → imagem (SVG mockado)
 *   TrainingPage (/quality/training):
 *     - GET /api/training/images?page=&page_size=24                  → {frames,total,page,page_size,total_pages}
 *     - GET /api/training/models                                     → TrainedModel[]
 *     - GET /api/classes                                             → YoloClass[]
 *     - GET /api/training/jobs                                       → TrainingJob[]
 *     - GET /api/training/jobs/current/status (poll 3s)              → {job,gpu_enabled,live}
 *     - GET /api/training/frames/<id>/image                          → thumbnail (SVG mockado)
 *   QualityAnnotationWorkspace:
 *     - GET /api/v1/quality/inspections/<id>/annotation-frames       → {frames: AnnotationFrame[]}
 *     - GET /api/v1/quality/classes                                  → {classes: QualityClass[]}
 *     - GET /api/v1/quality/annotation-frames/<id>/url               → {url, expires_in}
 *     - GET /api/v1/quality/inspections/<id>/annotation-progress     → AnnotationProgress
 *   QualityAndonDisplay:
 *     - GET /api/v1/quality/andon/<cameraId> (poll 15s)              → AndonData
 *   TabletKiosk:
 *     - WS socket.io namespace /quality (sem backend → view idle permanente)
 */
import { test } from '@playwright/test'
import { setupApp, shootBothThemes, settle, gotoAudit } from './helpers'

const minAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()

// ---------------------------------------------------------------------------
// Fixtures — Quality Gate (pt-BR, Tenant RVB Industrial)
// ---------------------------------------------------------------------------

/** Base de peça aprovada do gate — campos completos do schema. */
function piece(over: Record<string, unknown>) {
  return {
    id: 'pc-0000',
    piece_number: 'RVB-0000',
    work_order: 'OP-2026-0107',
    product_type: 'Chicote elétrico 12 vias',
    status: 'approved',
    current_station: null,
    operator_id: 'op-carlos-silva',
    started_at: minAgo(300),
    completed_at: minAgo(240),
    total_rework_count: 0,
    total_rework_time_seconds: 0,
    photo_quality_path: 'gate/pc-0000/final.jpg',
    photo_quality_r2_key: 'tenant-rvb/gate/pc-0000/final.jpg',
    wiser_exported: false,
    wiser_exported_at: null,
    created_at: minAgo(310),
    updated_at: minAgo(240),
    ...over,
  }
}

const GATE_PIECES = [
  piece({ id: 'pc-8841', piece_number: 'RVB-8841', completed_at: minAgo(35), wiser_exported: true, wiser_exported_at: minAgo(20) }),
  piece({ id: 'pc-8842', piece_number: 'RVB-8842', completed_at: minAgo(58), wiser_exported: true, wiser_exported_at: minAgo(40), total_rework_count: 1, total_rework_time_seconds: 84 }),
  piece({ id: 'pc-8843', piece_number: 'RVB-8843', completed_at: minAgo(92), wiser_exported: false }),
  piece({ id: 'pc-8844', piece_number: 'RVB-8844', completed_at: minAgo(120), wiser_exported: true, wiser_exported_at: minAgo(90), total_rework_count: 2, total_rework_time_seconds: 389 }),
  piece({ id: 'pc-8850', piece_number: 'RVB-8850', work_order: 'OP-2026-0112', completed_at: minAgo(160), wiser_exported: false }),
  piece({ id: 'pc-8851', piece_number: 'RVB-8851', work_order: 'OP-2026-0112', completed_at: minAgo(185), wiser_exported: false, total_rework_count: 1, total_rework_time_seconds: 156 }),
  piece({ id: 'pc-8860', piece_number: 'RVB-8860', work_order: null, completed_at: minAgo(410), wiser_exported: true, wiser_exported_at: minAgo(380) }),
]

/** Retrabalho do gate — campos completos do schema. */
function rework(over: Record<string, unknown>) {
  return {
    id: 'rw-000',
    piece_id: 'pc-8842-a1b2c3d4',
    inspection_id: 'insp-0000',
    validation_type: 'v1',
    defect_type: null,
    defect_description: null,
    photo_before_path: null,
    photo_after_path: null,
    operator_id: 'op-carlos-silva',
    started_at: minAgo(60),
    completed_at: minAgo(58),
    duration_seconds: 84,
    attempt_number: 1,
    notes: null,
    created_at: minAgo(60),
    ...over,
  }
}

const GATE_REWORKS = [
  rework({
    id: 'rw-101', piece_id: 'pc-8842-9f3e21aa', validation_type: 'v1',
    defect_type: 'Fio desalinhado no anel',
    photo_before_path: 'gate/rw-101/antes.jpg', photo_after_path: 'gate/rw-101/depois.jpg',
    duration_seconds: 84, started_at: minAgo(42),
    notes: 'Fio 3 reposicionado no anel guia; verificado torque do terminal.',
  }),
  rework({
    id: 'rw-102', piece_id: 'pc-8844-7b2c10ef', validation_type: 'v2',
    defect_type: 'Saída sem isolamento',
    photo_before_path: 'gate/rw-102/antes.jpg', photo_after_path: null,
    duration_seconds: 156, attempt_number: 1, started_at: minAgo(95),
  }),
  rework({
    id: 'rw-103', piece_id: 'pc-8844-7b2c10ef', validation_type: 'v3',
    defect_type: 'Anel sem capa isolante',
    photo_before_path: 'gate/rw-103/antes.jpg', photo_after_path: 'gate/rw-103/depois.jpg',
    duration_seconds: 233, attempt_number: 2, started_at: minAgo(130),
    notes: 'Capa termo-retrátil aplicada e aquecida — segunda tentativa aprovada.',
  }),
  rework({
    id: 'rw-104', piece_id: 'pc-8851-c4d5e6f7', validation_type: 'v1',
    defect_description: 'Fio fora do canal do anel na posição 5',
    duration_seconds: 61, started_at: minAgo(180),
  }),
  rework({
    id: 'rw-105', piece_id: 'pc-8823-11aa22bb', validation_type: 'v2',
    defect_type: 'Isolamento parcial na saída 2',
    duration_seconds: 142, started_at: minAgo(300),
  }),
  rework({
    id: 'rw-106', piece_id: 'pc-8810-33cc44dd', validation_type: 'v1',
    defect_type: 'Fio desalinhado no anel',
    photo_before_path: 'gate/rw-106/antes.jpg', photo_after_path: 'gate/rw-106/depois.jpg',
    duration_seconds: 97, started_at: minAgo(430),
  }),
]

const REWORK_METRICS = {
  by_validation: [
    { validation_type: 'v1', count: 14, avg_duration_seconds: 95 },
    { validation_type: 'v2', count: 8, avg_duration_seconds: 142 },
    { validation_type: 'v3', count: 5, avg_duration_seconds: 210 },
  ],
  total_reworks: 27,
  avg_duration_seconds: 128,
}

const REWORK_METRICS_EMPTY = { by_validation: [], total_reworks: 0, avg_duration_seconds: 0 }

/** Foto de retrabalho mockada (SVG aceito pelo <img>). */
const PHOTO_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">
  <rect width="640" height="360" fill="#1c2530"/>
  <circle cx="320" cy="180" r="110" fill="none" stroke="#8ba3bc" stroke-width="14"/>
  <path d="M 90 300 C 200 220, 260 210, 320 180" stroke="#f59e0b" stroke-width="8" fill="none"/>
  <path d="M 320 180 C 400 150, 480 160, 560 120" stroke="#06b6d4" stroke-width="8" fill="none"/>
  <text x="20" y="34" font-size="18" fill="#668096" font-family="monospace">gate/close-up · anel 12 vias</text>
</svg>`

// ---------------------------------------------------------------------------
// Fixtures — Treinamento (mesma TrainingPage do módulo EPI, contexto quality)
// ---------------------------------------------------------------------------

const FRAME_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="160" height="90">
  <rect width="160" height="90" fill="#243040"/>
  <circle cx="80" cy="45" r="26" fill="none" stroke="#8ba3bc" stroke-width="5"/>
  <path d="M 20 78 C 50 60, 66 56, 80 45" stroke="#f59e0b" stroke-width="3" fill="none"/>
  <text x="8" y="16" font-size="9" fill="#668096" font-family="monospace">bancada-a-closeup</text>
</svg>`

const TRAIN_GALLERY = Array.from({ length: 18 }).map((_, i) => ({
  id: `qfrm-${String(i + 1).padStart(3, '0')}`,
  video_id: 'vid-bancada-a-01',
  frame_number: 210 + i * 25,
  filename: `frame_${String(210 + i * 25).padStart(6, '0')}.jpg`,
  is_annotated: i % 4 !== 0,
  created_at: minAgo(60 * 20 - i * 12),
  video_name: 'Câmera Bancada A — close-up qualidade',
}))

const TRAIN_FIXTURES = {
  '**/api/training/images**': { frames: TRAIN_GALLERY, total: 96, page: 1, page_size: 24, total_pages: 4 },
  '**/api/training/models': [
    {
      id: 'qmdl-002', name: 'yolo26s-quality-rvb-v2', model_path: 'models/tenant-rvb/yolo26s-quality-v2.pt',
      map50: 0.902, precision: 0.884, recall: 0.861, is_active: true, created_at: '2026-07-01T10:20:00Z',
    },
    {
      id: 'qmdl-001', name: 'yolo26n-quality-rvb-v1', model_path: 'models/tenant-rvb/yolo26n-quality-v1.pt',
      map50: 0.845, precision: 0.82, recall: 0.79, is_active: false, created_at: '2026-06-18T15:05:00Z',
    },
  ],
  '**/api/classes': [
    { id: 0, name: 'Produto OK', color: '#10b981' },
    { id: 1, name: 'Produto NOK', color: '#ef4444' },
    { id: 5, name: 'Bolha', color: '#8b5cf6' },
    { id: 6, name: 'Mancha', color: '#22d3ee' },
  ],
  '**/api/training/jobs': [
    {
      id: 'qjb-031', preset: 'balanced', model_size: 'yolo26s', status: 'completed',
      progress: 100, current_epoch: 60, total_epochs: 60,
      metrics: { map50: 0.902, precision: 0.884, recall: 0.861 }, created_at: '2026-07-01T08:40:00Z',
    },
    {
      id: 'qjb-027', preset: 'fast', model_size: 'yolo26n', status: 'failed',
      progress: 35, current_epoch: 17, total_epochs: 50, metrics: {},
      error_message: 'Dataset com menos de 10 frames anotados', created_at: '2026-06-25T11:10:00Z',
    },
    {
      id: 'qjb-020', preset: 'balanced', model_size: 'yolo26n', status: 'completed',
      progress: 100, current_epoch: 50, total_epochs: 50,
      metrics: { map50: 0.845, precision: 0.82, recall: 0.79 }, created_at: '2026-06-18T13:00:00Z',
    },
  ],
  '**/api/training/jobs/current/status**': {
    job: {
      id: 'qjb-031', preset: 'balanced', model_size: 'yolo26s', status: 'completed',
      progress: 100, current_epoch: 60, total_epochs: 60,
      metrics: { map50: 0.902, precision: 0.884, recall: 0.861 }, created_at: '2026-07-01T08:40:00Z',
    },
    gpu_enabled: true,
    live: null,
  },
}

const TRAIN_EMPTY_FIXTURES = {
  '**/api/training/images**': { frames: [], total: 0, page: 1, page_size: 24, total_pages: 0 },
  '**/api/training/models': [],
  '**/api/classes': [],
  '**/api/training/jobs': [],
  '**/api/training/jobs/current/status**': { job: null, gpu_enabled: true, live: null },
}

// ---------------------------------------------------------------------------
// Fixtures — Anotação de frames NOK
// ---------------------------------------------------------------------------

const QUALITY_CLASSES = [
  { id: 0, name: 'produto_ok', color: '#43D186', label: 'Produto OK', category: 'ok' },
  { id: 1, name: 'produto_nok', color: '#EF5350', label: 'Produto NOK', category: 'nok' },
  { id: 5, name: 'bolha', color: '#CE93D8', label: 'Bolha', category: 'nok' },
  { id: 6, name: 'mancha', color: '#4FC3F7', label: 'Mancha', category: 'nok' },
  { id: 7, name: 'montagem_faltando', color: '#E57373', label: 'Montagem faltando', category: 'nok' },
]

const ANNOTATION_FRAMES = Array.from({ length: 8 }).map((_, i) => ({
  id: `afr-${String(i + 1).padStart(2, '0')}`,
  inspection_id: 'insp-0107',
  frame_sequence: i + 1,
  r2_key: `tenant-rvb/annotation/insp-0107/frame-${i + 1}.jpg`,
  status: i < 3 ? 'annotated' : i === 3 ? 'skipped' : 'pending',
  annotations:
    i === 0
      ? [
          { id: 'bb-01', class_id: 1, cx: 0.42, cy: 0.5, w: 0.24, h: 0.32 },
          { id: 'bb-02', class_id: 5, cx: 0.7, cy: 0.34, w: 0.1, h: 0.12 },
        ]
      : [],
}))

/** Frame NOK 16:9 servido no lugar da presigned URL do R2. */
const NOK_FRAME_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720">
  <rect width="1280" height="720" fill="#151b24"/>
  <circle cx="560" cy="380" r="190" fill="none" stroke="#8ba3bc" stroke-width="22"/>
  <path d="M 160 620 C 360 470, 460 440, 560 380" stroke="#f59e0b" stroke-width="14" fill="none"/>
  <path d="M 560 380 C 760 310, 940 330, 1130 240" stroke="#06b6d4" stroke-width="14" fill="none"/>
  <ellipse cx="880" cy="250" rx="52" ry="34" fill="#3a2530" stroke="#ef4444" stroke-width="4"/>
  <text x="32" y="58" font-size="30" fill="#668096" font-family="monospace">insp-0107 · Câmera Bancada A close-up</text>
</svg>`

const ANNOTATION_FIXTURES = {
  '**/api/v1/quality/inspections/*/annotation-frames**': { frames: ANNOTATION_FRAMES },
  '**/api/v1/quality/classes**': { classes: QUALITY_CLASSES },
  '**/api/v1/quality/annotation-frames/*/url**': { url: '/audit-assets/frame-nok.svg', expires_in: 3600 },
  '**/api/v1/quality/inspections/*/annotation-progress**': {
    total: 8, annotated: 3, skipped: 1, pending: 4, can_create_job: false,
  },
}

const AUDIT_ASSETS_RAW = {
  '**/audit-assets/**': { status: 200, contentType: 'image/svg+xml', body: NOK_FRAME_SVG },
}

// ---------------------------------------------------------------------------
// Fixtures — Andon
// ---------------------------------------------------------------------------

const ANDON_RICO = {
  camera_id: 'cam-0042',
  camera_name: 'Câmera Bancada A — Close-up',
  last_result: 'ok',
  nok_rate_1h: 0.042,
  total_ok: 318,
  total_nok: 14,
  cep_status: 'in_control',
  recent_inspections: [
    { result: 'ok', defect_class: null, confidence: 0.96, timestamp: minAgo(2) },
    { result: 'ok', defect_class: null, confidence: 0.94, timestamp: minAgo(4) },
    { result: 'nok', defect_class: 5, confidence: 0.88, timestamp: minAgo(7) },
    { result: 'ok', defect_class: null, confidence: 0.97, timestamp: minAgo(9) },
    { result: 'ok', defect_class: null, confidence: 0.95, timestamp: minAgo(12) },
  ],
}

const ANDON_VAZIO = {
  camera_id: 'cam-0042',
  camera_name: 'Câmera Bancada A — Close-up',
  last_result: null,
  nok_rate_1h: 0,
  total_ok: 0,
  total_nok: 0,
  cep_status: 'unknown',
  recent_inspections: [],
}

// ===========================================================================
// PÁGINA 1 — quality-reports (/quality/reports)
// ===========================================================================

test('quality-reports — default (peças agrupadas por OP, Wiser misto)', async ({ page }) => {
  await setupApp(page, { fixtures: { '**/api/v1/quality/gate/pieces**': { pieces: GATE_PIECES } } })
  await gotoAudit(page, '/quality/reports')
  await page.getByRole('heading', { name: 'Relatórios — Quality Gate' }).waitFor({ timeout: 30_000 })
  await page.getByText('OP-2026-0107').waitFor()
  await page.getByRole('button', { name: /Exportar Wiser \(3\)/ }).waitFor()
  await settle(page)
  await shootBothThemes(page, 'quality-reports', 'default', true)
})

test('quality-reports — empty', async ({ page }) => {
  await setupApp(page, { fixtures: { '**/api/v1/quality/gate/pieces**': { pieces: [] } } })
  await gotoAudit(page, '/quality/reports')
  await page.getByRole('heading', { name: 'Relatórios — Quality Gate' }).waitFor({ timeout: 30_000 })
  await page.getByText('Nenhuma peça aprovada encontrada').waitFor()
  await settle(page)
  await shootBothThemes(page, 'quality-reports', 'empty')
})

// ===========================================================================
// PÁGINA 2 — quality-rework (/quality/rework)
// ===========================================================================

const REWORK_FIXTURES = {
  '**/api/v1/quality/gate/reworks**': { reworks: GATE_REWORKS, total: 27 },
  '**/api/v1/quality/gate/stats/rework**': REWORK_METRICS,
}

test('quality-rework — default (métricas + tabela paginada)', async ({ page }) => {
  await setupApp(page, { fixtures: REWORK_FIXTURES })
  await gotoAudit(page, '/quality/rework')
  await page.getByRole('heading', { name: 'Retrabalhos — Quality Gate' }).waitFor({ timeout: 30_000 })
  await page.getByText('Distribuição por Validação').waitFor()
  await page.getByText('Fio desalinhado no anel').first().waitFor()
  await settle(page)
  await shootBothThemes(page, 'quality-rework', 'default', true)
})

test('quality-rework — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/quality/gate/reworks**': { reworks: [], total: 0 },
      '**/api/v1/quality/gate/stats/rework**': REWORK_METRICS_EMPTY,
    },
  })
  await gotoAudit(page, '/quality/rework')
  await page.getByRole('heading', { name: 'Retrabalhos — Quality Gate' }).waitFor({ timeout: 30_000 })
  await page.getByText('Nenhum retrabalho encontrado.').waitFor()
  await settle(page)
  await shootBothThemes(page, 'quality-rework', 'empty')
})

test('quality-rework — modal-fotos (antes/depois)', async ({ page }) => {
  await setupApp(page, {
    fixtures: REWORK_FIXTURES,
    raw: { '**/api/v1/quality/gate/photos/**': { status: 200, contentType: 'image/svg+xml', body: PHOTO_SVG } },
  })
  await gotoAudit(page, '/quality/rework')
  await page.getByRole('heading', { name: 'Retrabalhos — Quality Gate' }).waitFor({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Ver fotos' }).first().click()
  await page.getByText('Fotos do Retrabalho — V1').waitFor({ timeout: 15_000 })
  await page.getByText('Antes do retrabalho').waitFor()
  await settle(page, 500)
  await shootBothThemes(page, 'quality-rework', 'modal-fotos')
})

// ===========================================================================
// PÁGINA 3 — quality-training (/quality/training — TrainingPage compartilhada)
// ===========================================================================

test('quality-training — default (tab Imagens, galeria rica)', async ({ page }) => {
  await setupApp(page, {
    fixtures: TRAIN_FIXTURES,
    raw: { '**/api/training/frames/*/image**': { status: 200, contentType: 'image/svg+xml', body: FRAME_SVG } },
  })
  await gotoAudit(page, '/quality/training')
  await page.getByRole('heading', { name: 'Treinamento' }).waitFor({ timeout: 30_000 })
  await page.getByText('Página 1 de 4').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'quality-training', 'default', true)
})

test('quality-training — empty', async ({ page }) => {
  await setupApp(page, { fixtures: TRAIN_EMPTY_FIXTURES })
  await gotoAudit(page, '/quality/training')
  await page.getByRole('heading', { name: 'Treinamento' }).waitFor({ timeout: 30_000 })
  await page.getByText('Nenhuma imagem de treino').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'quality-training', 'empty')
})

// ===========================================================================
// PÁGINA 4 — quality-annotation (/quality/inspections/:id/annotate)
// ===========================================================================

test('quality-annotation — default (canvas + bboxes + thumbnails)', async ({ page }) => {
  await setupApp(page, { fixtures: ANNOTATION_FIXTURES, raw: AUDIT_ASSETS_RAW })
  await gotoAudit(page, '/quality/inspections/insp-0107/annotate')
  await page.getByText('Frame 1 / 8').waitFor({ timeout: 30_000 })
  await page.getByText('Classe Ativa').waitFor()
  await page.getByRole('button', { name: 'Produto NOK' }).waitFor()
  await settle(page)
  await shootBothThemes(page, 'quality-annotation', 'default')
})

test('quality-annotation — empty (sem frames extraídos)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      ...ANNOTATION_FIXTURES,
      '**/api/v1/quality/inspections/*/annotation-frames**': { frames: [] },
    },
  })
  await gotoAudit(page, '/quality/inspections/insp-0107/annotate')
  await page.getByText('Nenhum frame disponível para anotação.').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'quality-annotation', 'empty')
})

// ===========================================================================
// PÁGINA 5 — quality-andon (/quality/andon/:cameraId)
// ===========================================================================

test('quality-andon — default (OK, CEP em controle)', async ({ page }) => {
  await setupApp(page, { fixtures: { '**/api/v1/quality/andon/**': ANDON_RICO } })
  await gotoAudit(page, '/quality/andon/cam-0042')
  await page.getByText('ANDON MONITOR').waitFor({ timeout: 30_000 })
  await page.getByText('PROCESSO EM CONTROLE').waitFor()
  await settle(page)
  await shootBothThemes(page, 'quality-andon', 'default')
})

test('quality-andon — empty (sem inspeções, CEP sem baseline)', async ({ page }) => {
  await setupApp(page, { fixtures: { '**/api/v1/quality/andon/**': ANDON_VAZIO } })
  await gotoAudit(page, '/quality/andon/cam-0042')
  await page.getByText('ANDON MONITOR').waitFor({ timeout: 30_000 })
  await page.getByText('CEP: SEM BASELINE').waitFor()
  await settle(page)
  await shootBothThemes(page, 'quality-andon', 'empty')
})

// ===========================================================================
// PÁGINA 6 — tablet-kiosk (/tablet/:station)
// ===========================================================================
// ACHADO: apesar do comentário "rota pública sem JWT" no AppRoutes.tsx, o auth
// gate do App.tsx renderiza <Login /> para QUALQUER rota sem token — inclusive
// /tablet/*. Sem JWT o tablet nunca abre (bug funcional registrado na
// auditoria). Capturamos com auth (comportamento real do app deployado).
// O kiosk é 100% dirigido por WebSocket (socket.io /quality). Sem backend o
// socket nunca conecta → view "idle" permanente, que É o estado default/vazio.
// Views identified/validating/ok/nok/transition/approved exigem eventos WS
// reais — registradas como deferred.
// NÃO usar settle(): o socket.io em reconexão contínua impede o networkidle.

test('tablet-kiosk — default (idle, /tablet/estacao-1)', async ({ page }) => {
  await setupApp(page, {})
  await gotoAudit(page, '/tablet/estacao-1')
  await page.getByText('Aguardando Peça').waitFor({ timeout: 30_000 })
  await page.getByText('RECOGNITION · QUALITY GATE').waitFor()
  await page.waitForTimeout(900)
  await shootBothThemes(page, 'tablet-kiosk', 'default')
})

test('tablet-kiosk — empty (idle na Bancada A, /tablet/bench-a)', async ({ page }) => {
  // Mesma view idle exibindo o rótulo da bancada real ("Bancada A — V1 e V2")
  await setupApp(page, {})
  await gotoAudit(page, '/tablet/bench-a')
  await page.getByText('Aguardando Peça').waitFor({ timeout: 30_000 })
  await page.getByText('Bancada A — V1 e V2').waitFor()
  await page.waitForTimeout(900)
  await shootBothThemes(page, 'tablet-kiosk', 'empty')
})
