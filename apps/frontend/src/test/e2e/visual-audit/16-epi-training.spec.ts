/**
 * Visual-audit — Grupo 16: EPI Training (tier 1).
 *
 * Páginas:
 *   - /epi/training          (TrainingPage — abas Imagens / Modelo / Treino ao Vivo)
 *   - /epi/training/classes  (ModuleClassesPage — classes YOLO + teste DINO)
 *   - /epi/verification      (VerificationQueuePage — fila de revisão humana)
 *
 * Endpoints reais descobertos no source:
 *   TrainingPage:
 *     - GET /api/training/images?page=&page_size=24[&is_annotated=]  → {frames,total,page,page_size,total_pages}
 *     - GET /api/training/models                                    → TrainedModel[]
 *     - GET /api/classes                                            → YoloClass[]
 *     - GET /api/training/jobs                                      → TrainingJob[]
 *     - GET /api/training/jobs/current/status (poll 3s)             → {job,gpu_enabled,live}
 *     - GET /api/training/frames/<id>/image                         → thumbnail (SVG mockado)
 *     - WS  socket.io /training (useTrainingSocket — sem backend, degrada)
 *   AnnotationInterface (full-screen ao clicar numa imagem — shape LEGADO {success:true,...}):
 *     - GET /api/training/videos/<id>/frames                        → {success, frames}
 *     - GET /api/modules/epi/classes                                → {success, data:{classes}}
 *     - GET /api/training/frames/<id>/annotations                   → {success, annotations}
 *   ModuleClassesPage:
 *     - GET   /api/modules/epi/classes                              → {classes: ModuleClass[]}
 *     - POST  /api/modules/epi/classes/detect                       → {detections}
 *   VerificationQueuePage:
 *     - GET  /api/verification/queue (poll 15s)                     → {items}
 *     - POST /api/verification/<id>/review
 */
import { test, type Page } from '@playwright/test'
import { setupApp, shootBothThemes, shoot, settle, gotoAudit } from './helpers'

const minAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()

// ---------------------------------------------------------------------------
// Fixtures — pt-BR
// ---------------------------------------------------------------------------

/** Thumbnail SVG servido no lugar dos frames JPEG (o <img> aceita SVG). */
const FRAME_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="160" height="90">
  <rect width="160" height="90" fill="#243040"/>
  <rect x="16" y="34" width="30" height="42" rx="3" fill="#3b4d63"/>
  <circle cx="31" cy="24" r="8" fill="#8ba3bc"/>
  <rect x="66" y="48" width="74" height="28" rx="3" fill="#314054"/>
  <text x="66" y="18" font-size="9" fill="#668096" font-family="monospace">cam-patio-norte</text>
</svg>`

const GALLERY_FRAMES = Array.from({ length: 18 }).map((_, i) => ({
  id: `frm-${String(i + 1).padStart(3, '0')}`,
  video_id: 'vid-patio-norte-01',
  frame_number: 120 + i * 30,
  filename: `frame_${String(120 + i * 30).padStart(6, '0')}.jpg`,
  is_annotated: i % 3 !== 0,
  created_at: minAgo(60 * 24 - i * 15),
  video_name: 'Câmera Pátio Norte — turno manhã',
}))

const IMAGES_PAGE = {
  frames: GALLERY_FRAMES,
  total: 138,
  page: 1,
  page_size: 24,
  total_pages: 6,
}

const YOLO_CLASSES = [
  { id: 0, name: 'Capacete', color: '#10b981' },
  { id: 1, name: 'Sem capacete', color: '#ef4444' },
  { id: 2, name: 'Colete', color: '#06b6d4' },
  { id: 3, name: 'Sem colete', color: '#f59e0b' },
  { id: 4, name: 'Luvas', color: '#8b5cf6' },
  { id: 5, name: 'Sem luvas', color: '#f97316' },
  { id: 6, name: 'Óculos', color: '#22d3ee' },
  { id: 7, name: 'Sem óculos', color: '#e11d48' },
]

const MODELS = [
  {
    id: 'mdl-004', name: 'yolo26s-epi-rvb-v4', model_path: 'models/tenant-rvb/yolo26s-epi-v4.pt',
    map50: 0.913, precision: 0.897, recall: 0.874, is_active: true, created_at: '2026-07-02T14:35:00Z',
  },
  {
    id: 'mdl-003', name: 'yolo26n-epi-rvb-v3', model_path: 'models/tenant-rvb/yolo26n-epi-v3.pt',
    map50: 0.881, precision: 0.862, recall: 0.845, is_active: false, created_at: '2026-06-24T09:12:00Z',
  },
  {
    id: 'mdl-002', name: 'yolo26n-epi-rvb-v2', model_path: 'models/tenant-rvb/yolo26n-epi-v2.pt',
    map50: 0.842, precision: 0.83, recall: 0.79, is_active: false, created_at: '2026-06-10T16:40:00Z',
  },
  {
    id: 'mdl-001', name: 'yolo26n-epi-piloto-v1', model_path: 'models/tenant-rvb/yolo26n-piloto.pt',
    map50: 0.786, is_active: false, created_at: '2026-05-28T11:05:00Z',
  },
]

const JOB_RUNNING = {
  id: 'jb-207', preset: 'balanced', model_size: 'yolo26s', status: 'running',
  progress: 64, current_epoch: 32, total_epochs: 50, metrics: {},
  started_at: minAgo(38), created_at: minAgo(40),
}

const JOB_COMPLETED = {
  id: 'jb-201', preset: 'balanced', model_size: 'yolo26s', status: 'completed',
  progress: 100, current_epoch: 50, total_epochs: 50,
  metrics: { map50: 0.913, precision: 0.897, recall: 0.874 },
  started_at: '2026-07-02T13:10:00Z', completed_at: '2026-07-02T14:35:00Z', created_at: '2026-07-02T13:08:00Z',
}

const JOBS_HISTORY = [
  JOB_RUNNING,
  JOB_COMPLETED,
  {
    id: 'jb-198', preset: 'accurate', model_size: 'yolo26n', status: 'failed',
    progress: 42, current_epoch: 21, total_epochs: 50, metrics: {},
    error_message: 'CUDA out of memory — reduza o batch size', created_at: '2026-06-28T18:22:00Z',
  },
  {
    id: 'jb-195', preset: 'fast', model_size: 'yolo26n', status: 'stopped',
    progress: 30, current_epoch: 15, total_epochs: 50, metrics: {}, created_at: '2026-06-24T08:50:00Z',
  },
  {
    id: 'jb-190', preset: 'balanced', model_size: 'yolo26n', status: 'completed',
    progress: 100, current_epoch: 80, total_epochs: 80,
    metrics: { map50: 0.881, precision: 0.862, recall: 0.845 }, created_at: '2026-06-24T06:00:00Z',
  },
  {
    id: 'jb-182', preset: 'balanced', model_size: 'yolo26n', status: 'completed',
    progress: 100, current_epoch: 50, total_epochs: 50,
    metrics: { map50: 0.842, precision: 0.83, recall: 0.79 }, created_at: '2026-06-10T15:20:00Z',
  },
]

const CURRENT_RUNNING = {
  job: JOB_RUNNING,
  gpu_enabled: true,
  live: {
    job_id: 'jb-207', stage: 'training', progress: 64, epoch: 32,
    metrics: { loss: 0.0412, mAP50: 0.8125 },
  },
}

const CURRENT_COMPLETED = { job: JOB_COMPLETED, gpu_enabled: true, live: null }
const CURRENT_COMPLETED_SEM_GPU = { job: JOB_COMPLETED, gpu_enabled: false, live: null }

const TRAIN_FIXTURES = {
  '**/api/training/images**': IMAGES_PAGE,
  '**/api/training/models': MODELS,
  '**/api/classes': YOLO_CLASSES,
  '**/api/training/jobs': JOBS_HISTORY,
  '**/api/training/jobs/current/status**': CURRENT_RUNNING,
}

const FRAME_IMG_RAW = {
  '**/api/training/frames/*/image**': {
    status: 200, contentType: 'image/svg+xml', body: FRAME_SVG,
  },
}

// ModuleClassesPage — shape ModuleClass
const MODULE_CLASSES = [
  { id: 'mc-01', module_code: 'epi', class_id: 0, class_name: 'helmet', display_name: 'Capacete', dino_prompt: 'construction safety helmet', is_active: true, color: '#10b981' },
  { id: 'mc-02', module_code: 'epi', class_id: 1, class_name: 'no_helmet', display_name: 'Sem capacete', dino_prompt: 'head without helmet', is_active: true, color: '#ef4444' },
  { id: 'mc-03', module_code: 'epi', class_id: 2, class_name: 'vest', display_name: 'Colete', dino_prompt: 'reflective safety vest', is_active: true, color: '#06b6d4' },
  { id: 'mc-04', module_code: 'epi', class_id: 3, class_name: 'no_vest', display_name: 'Sem colete', dino_prompt: 'torso without vest', is_active: true, color: '#f59e0b' },
  { id: 'mc-05', module_code: 'epi', class_id: 4, class_name: 'person', display_name: 'Pessoa', dino_prompt: 'person', is_active: true, color: '#8ba3bc' },
  { id: 'mc-06', module_code: 'epi', class_id: 5, class_name: 'gloves', display_name: 'Luvas', dino_prompt: 'work gloves', is_active: true, color: '#8b5cf6' },
  { id: 'mc-07', module_code: 'epi', class_id: 6, class_name: 'glasses', display_name: 'Óculos de proteção', dino_prompt: 'safety glasses', is_active: false, color: null },
  { id: 'mc-08', module_code: 'epi', class_id: 7, class_name: 'no_glasses', display_name: 'Sem óculos', dino_prompt: 'face without glasses', is_active: false, color: null },
]

const CLASSES_FIXTURES = {
  '**/api/modules/epi/classes': { classes: MODULE_CLASSES },
}

const DINO_DETECTIONS = [
  { bbox: [0.12, 0.18, 0.34, 0.52], label: 'capacete', confidence: 0.91 },
  { bbox: [0.4, 0.3, 0.62, 0.78], label: 'colete', confidence: 0.84 },
  { bbox: [0.1, 0.12, 0.66, 0.95], label: 'pessoa', confidence: 0.97 },
]

// VerificationQueuePage
const QUEUE_ITEMS = [
  {
    id: 'vq-001', camera_id: 'cam-0001', camera_name: 'Câmera Pátio Norte', class_name: 'no_helmet',
    confidence: 0.42, violations: [{ class: 'no_helmet', confidence: 0.42, bbox: [0.2, 0.1, 0.4, 0.6] }],
    verification_reason: 'Oclusão parcial do capacete pela viga — não foi possível confirmar a violação',
    created_at: minAgo(4), timestamp: minAgo(4),
  },
  {
    id: 'vq-002', camera_id: 'cam-0002', camera_name: 'Câmera Doca 2', class_name: 'no_vest',
    confidence: 0.55, violations: [{ class: 'no_vest', confidence: 0.55, bbox: [0.5, 0.2, 0.7, 0.8] }],
    verification_reason: 'Baixa iluminação na zona de carga; colete pode estar presente',
    created_at: minAgo(11), timestamp: minAgo(11),
  },
  {
    id: 'vq-003', camera_id: 'cam-0003', camera_name: 'Câmera Almoxarifado', class_name: 'no_gloves',
    confidence: 0.63, violations: [{ class: 'no_gloves', confidence: 0.63, bbox: [0.3, 0.4, 0.5, 0.7] }],
    verification_reason: 'Mãos parcialmente fora do quadro durante a detecção',
    created_at: minAgo(23), timestamp: minAgo(23),
  },
  {
    id: 'vq-004', camera_id: 'cam-0004', camera_name: 'Câmera Portão Leste', class_name: 'no_glasses',
    confidence: 0.68, violations: [{ class: 'no_glasses', confidence: 0.68, bbox: [0.15, 0.1, 0.3, 0.3] }],
    verification_reason: 'Reflexo na lente pode ter sido confundido com ausência de óculos',
    created_at: minAgo(37), timestamp: minAgo(37),
  },
  {
    id: 'vq-005', camera_id: 'cam-0005', camera_name: 'Câmera Linha de Produção A', class_name: 'no_helmet',
    confidence: 0.74, violations: [{ class: 'no_helmet', confidence: 0.74, bbox: [0.6, 0.05, 0.8, 0.5] }],
    created_at: minAgo(52), timestamp: minAgo(52),
  },
  {
    id: 'vq-006', camera_id: 'cam-0006', camera_name: 'Câmera Oficina', class_name: 'no_vest',
    confidence: 0.88, violations: [{ class: 'no_vest', confidence: 0.88, bbox: [0.25, 0.2, 0.55, 0.9] }],
    verification_reason: 'EPI possivelmente presente, porém fora do padrão de cor do tenant',
    created_at: minAgo(75), timestamp: minAgo(75),
  },
]

// ---------------------------------------------------------------------------
// Helpers de navegação
// ---------------------------------------------------------------------------

async function openTraining(page: Page, fixtures: Record<string, unknown> = TRAIN_FIXTURES) {
  await setupApp(page, { fixtures, raw: FRAME_IMG_RAW })
  await gotoAudit(page, '/epi/training')
  await page.getByRole('heading', { name: 'Treinamento' }).waitFor({ timeout: 30_000 })
}

// ===========================================================================
// PÁGINA 1 — epi-training (/epi/training)
// ===========================================================================

test('epi-training — default (tab Imagens, galeria rica)', async ({ page }) => {
  await openTraining(page)
  await page.getByText('Página 1 de 6').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'epi-training', 'default', true)
})

test('epi-training — tab Modelo', async ({ page }) => {
  await openTraining(page)
  await page.getByRole('tab', { name: 'Modelo' }).click()
  await page.getByText('Modelo Ativo').waitFor({ timeout: 30_000 })
  await page.getByText('Modelos Treinados').waitFor()
  await settle(page)
  await shootBothThemes(page, 'epi-training', 'tab-modelo', true)
})

test('epi-training — tab Treino ao Vivo (job rodando)', async ({ page }) => {
  await openTraining(page)
  await page.getByRole('tab', { name: 'Treino ao Vivo' }).click()
  await page.getByText('Job Atual').waitFor({ timeout: 30_000 })
  await page.getByText('Histórico de Treinos').waitFor()
  // Espera 2 ciclos do polling de 3s para acumular linhas no Log de Eventos
  await page.waitForTimeout(3800)
  await shootBothThemes(page, 'epi-training', 'tab-treino', true)
})

test('epi-training — tab Treino sem GPU (banner simulação)', async ({ page }) => {
  await openTraining(page, {
    ...TRAIN_FIXTURES,
    '**/api/training/jobs/current/status**': CURRENT_COMPLETED_SEM_GPU,
  })
  await page.getByRole('tab', { name: 'Treino ao Vivo' }).click()
  await page.getByText('Chave de GPU não configurada').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'epi-training', 'tab-treino-sem-gpu', true)
})

test('epi-training — modal novo treino (form de configuração)', async ({ page }) => {
  await openTraining(page, {
    ...TRAIN_FIXTURES,
    '**/api/training/jobs/current/status**': CURRENT_COMPLETED,
  })
  await page.getByRole('tab', { name: 'Treino ao Vivo' }).click()
  await page.getByRole('button', { name: 'Novo Treino' }).click()
  await page.getByText('Modelo Base').waitFor({ timeout: 30_000 })
  await page.getByText('Learning Rate').waitFor()
  await settle(page, 400)
  await shootBothThemes(page, 'epi-training', 'modal-novo-treino', true)
})

test('epi-training — empty', async ({ page }) => {
  await openTraining(page, {
    '**/api/training/images**': { frames: [], total: 0, page: 1, page_size: 24, total_pages: 0 },
    '**/api/training/models': [],
    '**/api/classes': [],
    '**/api/training/jobs': [],
    '**/api/training/jobs/current/status**': { job: null, gpu_enabled: true, live: null },
  })
  await page.getByText('Nenhuma imagem de treino').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'epi-training', 'empty')
})

test('epi-training — loading (stall na galeria)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/training/models': MODELS,
      '**/api/classes': YOLO_CLASSES,
      '**/api/training/jobs': JOBS_HISTORY,
      '**/api/training/jobs/current/status**': CURRENT_RUNNING,
    },
    stall: ['**/api/training/images**'],
  })
  await gotoAudit(page, '/epi/training')
  await page.getByRole('heading', { name: 'Treinamento' }).waitFor({ timeout: 30_000 })
  await page.waitForTimeout(1200)
  await shootBothThemes(page, 'epi-training', 'loading')
})

test('epi-training — error (500 em todos os endpoints de treino)', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/training/**': { status: 500, body: { status: 'error', error: 'Erro interno do servidor' } },
      '**/api/classes': { status: 500, body: { status: 'error', error: 'Erro interno do servidor' } },
    },
  })
  await gotoAudit(page, '/epi/training')
  await page.getByRole('heading', { name: 'Treinamento' }).waitFor({ timeout: 30_000 })
  // Catches silenciosos → cai nos estados vazios (toast do errorTranslator pode aparecer)
  await page.getByText('Nenhuma imagem de treino').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'epi-training', 'error')
})

test('epi-training — annotation full-screen (clique numa imagem)', async ({ page }) => {
  // AnnotationInterface (JSX legado) espera shape {success:true,...} — vai via raw
  await setupApp(page, {
    fixtures: TRAIN_FIXTURES,
    raw: {
      ...FRAME_IMG_RAW,
      '**/api/training/videos/*/frames**': {
        status: 200,
        body: { success: true, frames: GALLERY_FRAMES.slice(0, 10) },
      },
      '**/api/modules/epi/classes': {
        status: 200,
        body: { success: true, data: { classes: MODULE_CLASSES } },
      },
      '**/api/training/frames/*/annotations**': {
        status: 200,
        body: { success: true, annotations: [] },
      },
    },
  })
  await gotoAudit(page, '/epi/training')
  await page.getByRole('heading', { name: 'Treinamento' }).waitFor({ timeout: 30_000 })
  await page.getByTitle('Câmera Pátio Norte — turno manhã').first().click()
  try {
    await page.getByText('← Voltar').waitFor({ timeout: 15_000 })
  } catch {
    // never-stop: captura o que estiver na tela mesmo sem a âncora
  }
  await settle(page)
  await shootBothThemes(page, 'epi-training', 'annotation-fullscreen', true)
})

test('epi-training — hovers (dark)', async ({ page }) => {
  await openTraining(page)
  await page.getByText('Página 1 de 6').waitFor({ timeout: 30_000 })
  await settle(page)

  await page.getByRole('button', { name: 'Anotadas', exact: true }).hover()
  await page.waitForTimeout(300)
  await shoot(page, 'epi-training', 'hover-filtro-anotadas')

  await page.getByRole('tab', { name: 'Modelo' }).click()
  await page.getByText('Modelos Treinados').waitFor()
  await page.getByRole('button', { name: 'Ativar', exact: true }).first().hover()
  await page.waitForTimeout(300)
  await shoot(page, 'epi-training', 'hover-btn-ativar-modelo')
})

// ===========================================================================
// PÁGINA 2 — training-classes (/epi/training/classes)
// ===========================================================================

test('training-classes — default (dark + light)', async ({ page }) => {
  await setupApp(page, { fixtures: CLASSES_FIXTURES })
  await gotoAudit(page, '/epi/training/classes')
  await page.getByRole('heading', { name: 'Classes do Módulo EPI' }).waitFor({ timeout: 30_000 })
  await page.getByText('Testar Detecção DINO').waitFor()
  await settle(page)
  await shootBothThemes(page, 'training-classes', 'default', true)
})

test('training-classes — empty', async ({ page }) => {
  await setupApp(page, { fixtures: { '**/api/modules/epi/classes': { classes: [] } } })
  await gotoAudit(page, '/epi/training/classes')
  await page.getByText('Nenhuma classe ativa.').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'training-classes', 'empty')
})

test('training-classes — loading (stall)', async ({ page }) => {
  await setupApp(page, { stall: ['**/api/modules/epi/classes'] })
  await gotoAudit(page, '/epi/training/classes')
  // Loading é só skeleton, sem heading — espera fixa antes do abort de 15s do api.ts
  await page.waitForTimeout(1500)
  await shootBothThemes(page, 'training-classes', 'loading')
})

test('training-classes — error (500)', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/modules/epi/classes': {
        status: 500,
        body: { status: 'error', error: 'Erro interno do servidor' },
      },
    },
  })
  await gotoAudit(page, '/epi/training/classes')
  // Sem UI dedicada de erro — heading + seções vazias + toast "Erro ao carregar classes"
  await page.getByRole('heading', { name: 'Classes do Módulo EPI' }).waitFor({ timeout: 30_000 })
  await page.waitForTimeout(600)
  await shootBothThemes(page, 'training-classes', 'error')
})

test('training-classes — teste DINO com resultado', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      ...CLASSES_FIXTURES,
      '**/api/modules/epi/classes/detect**': { detections: DINO_DETECTIONS },
    },
  })
  await gotoAudit(page, '/epi/training/classes')
  await page.getByRole('heading', { name: 'Classes do Módulo EPI' }).waitFor({ timeout: 30_000 })
  await page.getByPlaceholder('ID do frame (UUID)').fill('9f4e2a10-77b3-4c11-9d42-frame-patio')
  await page.getByRole('button', { name: 'Testar DINO' }).click()
  await page.getByText('capacete (91%)').waitFor({ timeout: 15_000 })
  await settle(page, 400)
  await shootBothThemes(page, 'training-classes', 'detect-resultado', true)
})

test('training-classes — hovers (dark)', async ({ page }) => {
  await setupApp(page, { fixtures: CLASSES_FIXTURES })
  await gotoAudit(page, '/epi/training/classes')
  await page.getByRole('heading', { name: 'Classes do Módulo EPI' }).waitFor({ timeout: 30_000 })
  await settle(page)

  await page.getByRole('button', { name: /^Capacete/ }).hover()
  await page.waitForTimeout(300)
  await shoot(page, 'training-classes', 'hover-classe-ativa')

  await page.getByRole('button', { name: 'Testar DINO' }).hover()
  await page.waitForTimeout(300)
  await shoot(page, 'training-classes', 'hover-btn-testar-dino')
})

// ===========================================================================
// PÁGINA 3 — verification-queue (/epi/verification)
// ===========================================================================

test('verification-queue — default (itens pendentes)', async ({ page }) => {
  await setupApp(page, { fixtures: { '**/api/verification/queue**': { items: QUEUE_ITEMS } } })
  await gotoAudit(page, '/epi/verification')
  await page.getByRole('heading', { name: 'Fila de Verificação' }).waitFor({ timeout: 30_000 })
  await page.getByText('Câmera Pátio Norte').waitFor()
  await settle(page)
  await shootBothThemes(page, 'verification-queue', 'default', true)
})

test('verification-queue — empty', async ({ page }) => {
  await setupApp(page, { fixtures: { '**/api/verification/queue**': { items: [] } } })
  await gotoAudit(page, '/epi/verification')
  await page.getByText('Fila vazia').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'verification-queue', 'empty')
})

test('verification-queue — loading (stall)', async ({ page }) => {
  await setupApp(page, { stall: ['**/api/verification/queue**'] })
  await gotoAudit(page, '/epi/verification')
  // Loading é só skeleton, sem heading — espera fixa antes do abort de 15s do api.ts
  await page.waitForTimeout(1500)
  await shootBothThemes(page, 'verification-queue', 'loading')
})

test('verification-queue — error (500)', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/verification/queue**': {
        status: 500,
        body: { status: 'error', error: 'Erro interno do servidor' },
      },
    },
  })
  await gotoAudit(page, '/epi/verification')
  // Sem UI dedicada de erro — a página cai no estado "Fila vazia" (registrado como issue)
  await page.getByText('Fila vazia').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'verification-queue', 'error')
})

test('verification-queue — hovers (dark)', async ({ page }) => {
  await setupApp(page, { fixtures: { '**/api/verification/queue**': { items: QUEUE_ITEMS } } })
  await gotoAudit(page, '/epi/verification')
  await page.getByRole('heading', { name: 'Fila de Verificação' }).waitFor({ timeout: 30_000 })
  await settle(page)

  await page.getByRole('button', { name: 'Confirmar' }).first().hover()
  await page.waitForTimeout(300)
  await shoot(page, 'verification-queue', 'hover-btn-confirmar')

  await page.getByRole('button', { name: 'Rejeitar' }).first().hover()
  await page.waitForTimeout(300)
  await shoot(page, 'verification-queue', 'hover-btn-rejeitar')
})
