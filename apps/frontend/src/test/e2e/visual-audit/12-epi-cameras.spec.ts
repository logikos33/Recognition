/**
 * Auditoria visual — grupo 12-epi-cameras (tier 1).
 *
 * /epi/cameras — lista de câmeras + painel de detalhe + wizard "Nova Câmera"
 * (CameraOnboardingWizard, task-046) + "Desempenho por câmera" (CameraFpsConfig,
 * task-063) + atribuição de modelos (CameraModelAssignment, task-045) +
 * modal de edição (CameraWizard) + ConfirmDialog de exclusão.
 *
 * Endpoints reais consumidos pela página:
 *   GET  /api/cameras                  → { cameras[], gateway_status }
 *   GET  /api/cameras/:id/models       → { camera_id, models: {epi,quality,counting} }
 *   GET  /api/training/models          → { models: [{id,name,map50}] }
 *   POST /api/cameras/probe            → ProbeResult (wizard, etapa Verificação)
 *   POST /api/cameras/:id/test         → TestResult (botão Testar Conexao)
 */
import { test, type Page } from '@playwright/test'
import { setupApp, shootBothThemes, shoot, settle, gotoAudit } from './helpers'

const SCREEN = 'epi-cameras'
const ROUTE = '/epi/cameras'

/* ------------------------------------------------------------------ */
/* Fixtures pt-BR — Tenant RVB Industrial                              */
/* ------------------------------------------------------------------ */

const CAMERAS = [
  {
    id: 'cam-1',
    name: 'Câmera Pátio Norte',
    location: 'Pátio Norte — Galpão A',
    manufacturer: 'intelbras',
    host: '10.20.30.101',
    ip_address: '10.20.30.101',
    port: 554,
    username: 'admin',
    channel: 1,
    is_active: true,
    stream_status: 'active',
    fps_target: 10,
    quality_preset: 'medium',
    created_at: '2026-05-02T08:12:00Z',
  },
  {
    id: 'cam-2',
    name: 'Câmera Doca de Carga 2',
    location: 'Doca 2 — Expedição',
    manufacturer: 'hikvision',
    host: '10.20.30.102',
    ip_address: '10.20.30.102',
    port: 554,
    username: 'admin',
    channel: 1,
    is_active: true,
    stream_status: 'inactive',
    fps_target: 5,
    quality_preset: 'high',
    created_at: '2026-05-10T10:40:00Z',
  },
  {
    id: 'cam-3',
    name: 'Câmera Linha de Produção',
    location: 'Linha 1 — Envase',
    manufacturer: 'dahua',
    host: '10.20.30.103',
    ip_address: '10.20.30.103',
    port: 554,
    username: 'operador',
    channel: 1,
    is_active: true,
    stream_status: 'error',
    last_error: 'timeout',
    fps_target: 15,
    quality_preset: 'low',
    created_at: '2026-05-18T14:05:00Z',
  },
  {
    id: 'cam-4',
    name: 'Câmera Portaria Principal',
    location: 'Portaria — Entrada de Veículos',
    manufacturer: 'intelbras',
    host: '10.20.30.104',
    ip_address: '10.20.30.104',
    port: 554,
    username: 'admin',
    channel: 1,
    is_active: true,
    stream_status: 'active',
    fps_target: 5,
    quality_preset: 'medium',
    created_at: '2026-06-01T09:00:00Z',
  },
  {
    id: 'cam-5',
    name: 'Câmera Almoxarifado',
    location: 'Almoxarifado Central',
    manufacturer: 'generic',
    host: '10.20.30.105',
    ip_address: '10.20.30.105',
    port: 8554,
    username: 'visita',
    channel: 1,
    is_active: false,
    stream_status: 'inactive',
    fps_target: 1,
    quality_preset: 'low',
    created_at: '2026-06-12T16:22:00Z',
  },
  {
    id: 'cam-6',
    name: 'Câmera Estacionamento Sul',
    location: 'Estacionamento — Bloco S',
    manufacturer: 'hikvision',
    host: '10.20.30.106',
    ip_address: '10.20.30.106',
    port: 554,
    username: 'admin',
    channel: 2,
    is_active: true,
    stream_status: 'offline',
    fps_target: 5,
    quality_preset: 'medium',
    created_at: '2026-06-20T11:45:00Z',
  },
]

const TRAINED_MODELS = {
  models: [
    { id: 'mdl-epi-v3', name: 'EPI RVB Industrial v3', map50: 0.87 },
    { id: 'mdl-qual-v1', name: 'Qualidade Solda v1', map50: 0.79 },
    { id: 'mdl-cnt-v2', name: 'Contagem Pallets v2', map50: 0.91 },
  ],
}

const RICH_FIXTURES: Record<string, unknown> = {
  '**/api/cameras': {
    cameras: CAMERAS,
    gateway_status: { status: 'online' },
  },
  '**/api/cameras/*/models': {
    camera_id: 'cam-2',
    models: { epi: 'mdl-epi-v3', quality: null, counting: null },
  },
  '**/api/training/models': TRAINED_MODELS,
  '**/api/cameras/*/test': {
    camera_id: 'cam-2',
    success: true,
    error: null,
    suggestion: null,
    checks: {
      url_format: { status: 'ok', message: 'URL RTSP válida' },
      host_reachable: { status: 'ok', message: 'Host alcançável' },
      port_open: { status: 'ok', message: 'Porta 554 aberta' },
      rtsp_response: { status: 'ok', message: 'RTSP respondeu DESCRIBE' },
      stream_available: { status: 'ok', message: 'Stream H.264 disponível' },
    },
  },
  '**/api/cameras/probe': {
    ok: true,
    method: 'ffprobe',
    codec: 'h264',
    resolution: '1280x720',
    fps: 15,
    substream_url_sugerida:
      'rtsp://10.20.30.110:554/cam/realmonitor?channel=1&subtype=1',
    gateway_available: false,
    warning: null,
    error: null,
  },
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

async function openPage(page: Page) {
  await gotoAudit(page, ROUTE)
  await page.getByText('Câmera Pátio Norte').waitFor({ timeout: 30_000 })
  await settle(page)
}

/** Seleciona a câmera inativa (cam-2) → painel de detalhe sem player HLS. */
async function selectCamera(page: Page) {
  await page.getByText('Câmera Doca de Carga 2').click()
  await page.getByText('Desempenho por câmera').waitFor({ timeout: 15_000 })
  await settle(page, 500)
}

/** Avança o wizard "Nova Câmera" (onboarding, task-046) até a etapa alvo (1..4). */
async function openWizardToStep(page: Page, targetStep: 1 | 2 | 3 | 4) {
  await page.getByRole('button', { name: /Nova Camera/i }).click()
  await page.getByText('Selecione o fabricante da câmera').waitFor({ timeout: 10_000 })
  if (targetStep === 1) return

  await page.getByRole('button', { name: /Intelbras/ }).click()
  await page.getByRole('button', { name: 'Próximo →' }).click()
  await page.getByText('Informe o endereço e credenciais da câmera').waitFor({ timeout: 10_000 })
  await page.getByPlaceholder('Ex: Portão principal').fill('Câmera Pátio Sul')
  await page.getByPlaceholder('192.168.1.100 ou camera.local').fill('10.20.30.110')
  await page.getByPlaceholder('••••••••').fill('senha-forte-123')
  if (targetStep === 2) return

  await page.getByRole('button', { name: /Verificar conexão/ }).click()
  await page.getByText('Câmera encontrada!').waitFor({ timeout: 15_000 })
  if (targetStep === 3) return

  await page.getByRole('button', { name: 'Confirmar →' }).click()
  await page.getByText('Revise os dados antes de salvar').waitFor({ timeout: 10_000 })
}

/* ------------------------------------------------------------------ */
/* Estados                                                             */
/* ------------------------------------------------------------------ */

test('epi-cameras — default (lista rica, sem seleção)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)
  await page.getByText('Selecione uma camera para ver detalhes').waitFor()
  await shootBothThemes(page, SCREEN, 'default')
})

test('epi-cameras — detail (câmera selecionada + Desempenho por câmera)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)
  await selectCamera(page)
  await shootBothThemes(page, SCREEN, 'detail', true)
})

test('epi-cameras — detail-logs (Testar Conexao com log de sucesso)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)
  await selectCamera(page)
  await page.getByRole('button', { name: /Testar Conexao/ }).click()
  await page.getByText('Conexao estabelecida').waitFor({ timeout: 10_000 })
  await settle(page, 400)
  await shootBothThemes(page, SCREEN, 'detail-logs', true)
})

test('epi-cameras — empty (nenhuma câmera cadastrada)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/cameras': { cameras: [], gateway_status: { status: 'offline' } },
    },
  })
  await gotoAudit(page, ROUTE)
  await page.getByText('Nenhuma camera cadastrada').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, SCREEN, 'empty')
})

test('epi-cameras — loading (GET /cameras nunca responde)', async ({ page }) => {
  await setupApp(page, { stall: ['**/api/cameras'] })
  await gotoAudit(page, ROUTE)
  // Sem settle: networkidle nunca acontece com request pendurada.
  await page.waitForTimeout(2500)
  await shootBothThemes(page, SCREEN, 'loading')
})

test('epi-cameras — error (GET /cameras 500)', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/cameras': {
        status: 500,
        body: { status: 'error', error: 'Falha ao conectar ao banco de dados' },
      },
    },
  })
  await gotoAudit(page, ROUTE)
  await page
    .getByText('Falha ao conectar ao banco de dados')
    .first()
    .waitFor({ timeout: 15_000 })
    .catch(() => {})
  await page.waitForTimeout(500)
  await shootBothThemes(page, SCREEN, 'error')
})

/* ---------------------- Wizard "Nova Câmera" ---------------------- */

test('epi-cameras — wizard-step1 (Fabricante)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)
  await openWizardToStep(page, 1)
  await settle(page, 400)
  await shootBothThemes(page, SCREEN, 'wizard-step1')
})

test('epi-cameras — wizard-step2 (Acesso preenchido)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)
  await openWizardToStep(page, 2)
  await settle(page, 400)
  await shootBothThemes(page, SCREEN, 'wizard-step2')
})

test('epi-cameras — wizard-step3 (Verificação: probe ok)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)
  await openWizardToStep(page, 3)
  await settle(page, 400)
  await shootBothThemes(page, SCREEN, 'wizard-step3')
})

test('epi-cameras — wizard-step4 (Confirmar)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)
  await openWizardToStep(page, 4)
  await settle(page, 400)
  await shootBothThemes(page, SCREEN, 'wizard-step4')
})

/* --------------------------- Modais ------------------------------- */

test('epi-cameras — modal-edit (Editar Câmera, passo 1)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)
  await selectCamera(page)
  await page.getByRole('button', { name: 'Editar' }).click()
  await page.getByText('Editar Câmera').waitFor({ timeout: 10_000 })
  await settle(page, 400)
  await shootBothThemes(page, SCREEN, 'modal-edit')
})

test('epi-cameras — modal-delete (ConfirmDialog de exclusão)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)
  await selectCamera(page)
  await page.getByRole('button', { name: 'Excluir' }).click()
  await page.getByText('Confirmar exclusão').waitFor({ timeout: 10_000 })
  await settle(page, 400)
  await shootBothThemes(page, SCREEN, 'modal-delete')
})

/* --------------------------- Hover (só dark) ---------------------- */

test('epi-cameras — hover (item da lista + botão Nova Camera)', async ({ page }) => {
  await setupApp(page, { fixtures: RICH_FIXTURES })
  await openPage(page)

  await page.getByText('Câmera Linha de Produção').hover()
  await page.waitForTimeout(300)
  await shoot(page, SCREEN, 'dark-hover-list-item')

  await page.getByRole('button', { name: /Nova Camera/i }).hover()
  await page.waitForTimeout(300)
  await shoot(page, SCREEN, 'dark-hover-nova-camera')
})
