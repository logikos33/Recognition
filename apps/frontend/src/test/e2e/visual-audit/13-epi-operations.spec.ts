/**
 * Visual-audit — Grupo 13: EPI Operations (tier 1).
 *
 * Páginas:
 *   - /epi/cameras/1/operations  (EpiOperationsPage → TrainingModeLayout, moduleId='ppe')
 *   - /epi/cameras/1/scenario    (EpiScenarioEditorPage → ScenarioEditor)
 *
 * Foco crítico (tasks 063/066): modal "Nova Operação" aberto em cada etapa do
 * wizard (Tipo → Configuração → Revisão) nos DOIS temas — o defeito 066 é o
 * modal sem fundo opaco sobre o painel de vídeo.
 *
 * Endpoints reais descobertos no source:
 *   - GET /api/cameras/1/operations?module_id=ppe     (useOperations)
 *   - GET /api/modules/ppe/operation-types            (useOperationTypes — só em modo edição)
 *   - GET /api/cameras/1/scenario                     (useScenario)
 *   - GET /api/scenarios/operation-types?module=epi   (useScenarioOperationTypes)
 *   - GET /api/cameras/1/stream/stream.m3u8           (HLS — 404 pelo harness)
 *   - WS  socket.io /monitor (useMonitoringSocket / useOperationLiveStatus — sem backend, degrada)
 */
import { test, type Page, type Locator } from '@playwright/test'
import { setupApp, shootBothThemes, shoot, settle, gotoAudit } from './helpers'

const minAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()

// ---------------------------------------------------------------------------
// Fixtures — pt-BR, paridade com o harness da task-063
// ---------------------------------------------------------------------------

const OPERATION_TYPES = [
  {
    type_id: 'count_static',
    type_label: 'Contagem estática',
    description: 'Conta objetos de uma classe dentro de uma zona fixa',
    available_modules: ['ppe', 'epi'],
    config_schema: { roi_points: { type: 'polygon', min_points: 3 }, target_class: { type: 'string' }, threshold: { type: 'number' } },
    metric_options: ['count', 'boolean_above', 'boolean_below'],
    output_formats: ['physical', 'conditional'],
  },
  {
    type_id: 'overlap_dynamic',
    type_label: 'Sobreposição dinâmica',
    description: 'Mede sobreposição (IoU) entre duas classes móveis',
    available_modules: ['ppe', 'epi'],
    config_schema: { class_a: { type: 'string' }, class_b: { type: 'string' }, iou_threshold: { type: 'number' } },
    metric_options: ['iou_percent', 'min_distance', 'overlap_time_seconds'],
    output_formats: ['physical', 'conditional', 'both'],
  },
  {
    type_id: 'position',
    type_label: 'Posição',
    description: 'Verifica permanência de uma classe dentro da zona de interesse',
    available_modules: ['ppe', 'epi'],
    config_schema: { roi_points: { type: 'polygon', min_points: 3 }, target_class: { type: 'string' } },
    metric_options: ['state', 'coordinates', 'both'],
    output_formats: ['physical', 'conditional'],
  },
  {
    type_id: 'count_line',
    type_label: 'Linha de contagem',
    description: 'Conta cruzamentos de objetos sobre uma linha virtual',
    available_modules: ['ppe', 'epi'],
    config_schema: { line_points: { type: 'line', points: 2 }, target_class: { type: 'string' } },
    metric_options: ['entry_exit_count', 'count'],
    output_formats: ['physical'],
  },
]

// Tipo extra só do editor de cenário — exercita a ferramenta "ponto"
const SCENARIO_TYPES = [
  ...OPERATION_TYPES,
  {
    type_id: 'point_interest',
    type_label: 'Ponto de interesse',
    description: 'Monitora presença de classe em um ponto fixo do cenário',
    available_modules: ['epi'],
    config_schema: { point: { type: 'point' }, target_class: { type: 'string' } },
    metric_options: ['state'],
    output_formats: ['conditional'],
  },
]

const OPERATIONS = [
  {
    id: 1, camera_id: '1', module_id: 'ppe', type_id: 'position', type_label: 'Posição',
    name: 'Zona Portão Leste', status: 'active', version: 3,
    config: { roi_points: [[0.08, 0.2], [0.38, 0.16], [0.42, 0.58], [0.12, 0.66]], target_class: 'person', metric: 'state', confidence_threshold: 0.6 },
    last_value_json: { metric_value: 'dentro' }, last_evaluated_at: minAgo(1), created_at: '2026-06-28T14:22:00Z',
  },
  {
    id: 2, camera_id: '1', module_id: 'ppe', type_id: 'count_static', type_label: 'Contagem estática',
    name: 'Contagem Doca 2', status: 'error', version: 1,
    config: { roi_points: [[0.55, 0.28], [0.9, 0.25], [0.93, 0.7], [0.58, 0.78]], target_class: 'person', threshold: 12 },
    last_value_json: { metric_value: 7 }, last_evaluated_at: minAgo(42), created_at: '2026-07-01T09:10:00Z',
  },
  {
    id: 3, camera_id: '1', module_id: 'ppe', type_id: 'overlap_dynamic', type_label: 'Sobreposição dinâmica',
    name: 'Empilhadeira × Pedestre — Ala Norte', status: 'warning', version: 2,
    config: { class_a: 'forklift', class_b: 'person', metric: 'iou_percent', iou_threshold: 15 },
    last_value_json: { metric_value: 18.4 }, last_evaluated_at: minAgo(6), created_at: '2026-06-30T16:45:00Z',
  },
  {
    id: 4, camera_id: '1', module_id: 'ppe', type_id: 'overlap_fixed', type_label: 'Sobreposição fixa',
    name: 'Colete Zona de Carga', status: 'inactive', version: 1,
    config: { roi_points: [[0.6, 0.08], [0.85, 0.1], [0.83, 0.3], [0.58, 0.26]], target_class: 'vest' },
    created_at: '2026-06-25T08:00:00Z',
  },
  {
    id: 5, camera_id: '1', module_id: 'ppe', type_id: 'count_static', type_label: 'Contagem estática',
    name: 'Contagem Pátio Norte', status: 'active', version: 5,
    config: { roi_points: [[0.15, 0.72], [0.5, 0.7], [0.52, 0.92], [0.18, 0.95]], target_class: 'person', threshold: 20 },
    last_value_json: { metric_value: 12 }, last_evaluated_at: minAgo(3), created_at: '2026-06-20T10:30:00Z',
  },
]

const SCENARIO_OPERATIONS = [
  { ...OPERATIONS[0], module_id: 'epi' },
  { ...OPERATIONS[1], module_id: 'epi' },
]

const SCENARIO = {
  camera: { id: '1', name: 'Câmera Pátio Norte', site_id: 'site-rvb-01' },
  modules: [
    {
      module_code: 'epi', enabled: true, config: null, activated_at: '2026-05-02T12:00:00Z', expires_at: null,
      classes: [
        { id: 1, class_name: 'helmet', display_name: 'Capacete', color: '#10b981' },
        { id: 2, class_name: 'no_helmet', display_name: 'Sem capacete', color: '#ef4444' },
        { id: 3, class_name: 'vest', display_name: 'Colete', color: '#06b6d4' },
        { id: 4, class_name: 'no_vest', display_name: 'Sem colete', color: '#f59e0b' },
        { id: 5, class_name: 'person', display_name: 'Pessoa', color: '#8ba3bc' },
      ],
    },
    { module_code: 'fueling', enabled: false, config: null, activated_at: null, expires_at: null, classes: [] },
  ],
  operations: [],
  alert_rules: [],
  schedule: [],
}

const OPS_FIXTURES = {
  '**/api/cameras/1/operations**': { operations: OPERATIONS },
  '**/api/modules/ppe/operation-types**': { types: OPERATION_TYPES },
}

const SCENARIO_FIXTURES = {
  '**/api/cameras/1/scenario**': { scenario: SCENARIO },
  '**/api/scenarios/operation-types**': { types: SCENARIO_TYPES },
  '**/api/cameras/1/operations**': { operations: SCENARIO_OPERATIONS },
}

// ---------------------------------------------------------------------------
// Helpers de navegação/interação
// ---------------------------------------------------------------------------

async function openOperationsDefault(page: Page) {
  await setupApp(page, { fixtures: OPS_FIXTURES })
  await gotoAudit(page, '/epi/cameras/1/operations')
  await page.getByText('Zona Portão Leste').first().waitFor({ timeout: 30_000 })
  await settle(page)
}

/** Abre o modal "Nova Operação" (wizard) clicando no botão do painel de vídeo. */
async function openWizard(page: Page): Promise<Locator> {
  await openOperationsDefault(page)
  await page.getByRole('button', { name: 'Operação', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('heading', { name: 'Nova Operação' }).waitFor()
  await dialog.getByRole('button', { name: /^Contagem estática/ }).waitFor()
  return dialog
}

/** Avança o wizard até a etapa Configuração usando Sobreposição dinâmica (sem ROI obrigatória). */
async function wizardToStep2(page: Page): Promise<Locator> {
  const dialog = await openWizard(page)
  await dialog.getByRole('button', { name: /^Sobreposição dinâmica/ }).click()
  await dialog.getByRole('button', { name: 'Próximo: Configurar →' }).click()
  await dialog.getByText('Nome da operação *').waitFor()
  await dialog.getByPlaceholder(/^Ex:/).fill('Sobreposição Empilhadeira × Pedestre')
  await dialog.locator('select').nth(0).selectOption('forklift')
  await dialog.locator('select').nth(1).selectOption('person')
  return dialog
}

async function openScenarioDefault(page: Page) {
  await setupApp(page, { fixtures: SCENARIO_FIXTURES })
  await gotoAudit(page, '/epi/cameras/1/scenario')
  await page.getByRole('heading', { name: 'Editor de Cenário' }).waitFor({ timeout: 30_000 })
  await page.getByTestId('module-btn-epi').waitFor()
  await settle(page)
}

const CANVAS = '[data-testid="canvas-interaction-layer"]'

async function drawPoints(page: Page, pts: Array<{ x: number; y: number }>) {
  for (const p of pts) {
    await page.locator(CANVAS).click({ position: p })
    await page.waitForTimeout(120)
  }
}

// ===========================================================================
// PÁGINA 1 — epi-operations (/epi/cameras/1/operations)
// ===========================================================================

test('epi-operations — default (dark + light)', async ({ page }) => {
  await openOperationsDefault(page)
  await shootBothThemes(page, 'epi-operations', 'default')
})

test('epi-operations — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/cameras/1/operations**': { operations: [] },
      '**/api/modules/ppe/operation-types**': { types: OPERATION_TYPES },
    },
  })
  await gotoAudit(page, '/epi/cameras/1/operations')
  await page.getByText('Nenhuma operação cadastrada').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'epi-operations', 'empty')
})

test('epi-operations — loading (stall)', async ({ page }) => {
  await setupApp(page, { stall: ['**/api/cameras/1/operations**'] })
  await gotoAudit(page, '/epi/cameras/1/operations')
  await page.getByText('Carregando operações...').waitFor({ timeout: 30_000 })
  await page.waitForTimeout(1200)
  await shootBothThemes(page, 'epi-operations', 'loading')
})

test('epi-operations — error (500)', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/cameras/1/operations**': {
        status: 500,
        body: { status: 'error', error: 'Erro interno do servidor' },
      },
    },
  })
  await gotoAudit(page, '/epi/cameras/1/operations')
  // A UI não renderiza estado de erro dedicado — cai no vazio (registrado como issue)
  await page.getByText('Nenhuma operação cadastrada').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'epi-operations', 'error')
})

test('epi-operations — wizard step 1 (Tipo)', async ({ page }) => {
  const dialog = await openWizard(page)
  // Seleciona "Posição" para registrar o highlight de seleção
  await dialog.getByRole('button', { name: /^Posição/ }).click()
  await settle(page, 400)
  await shootBothThemes(page, 'epi-operations', 'wizard-step1-tipo')
})

test('epi-operations — wizard step 2 (Configuração)', async ({ page }) => {
  await wizardToStep2(page)
  await settle(page, 400)
  await shootBothThemes(page, 'epi-operations', 'wizard-step2-configuracao')
})

test('epi-operations — wizard step 3 (Revisão)', async ({ page }) => {
  const dialog = await wizardToStep2(page)
  await dialog.getByRole('button', { name: 'Próximo: Revisar →' }).click()
  await dialog.getByText('Ver configuração JSON').waitFor()
  await settle(page, 400)
  await shootBothThemes(page, 'epi-operations', 'wizard-step3-revisao')
})

test('epi-operations — modal editar operação', async ({ page }) => {
  await openOperationsDefault(page)
  await page.getByTitle('Editar operação').first().click()
  await page.getByRole('heading', { name: 'Editar: Zona Portão Leste' }).waitFor()
  await settle(page, 400)
  await shootBothThemes(page, 'epi-operations', 'modal-editar-operacao')
})

test('epi-operations — modal excluir operação', async ({ page }) => {
  await openOperationsDefault(page)
  await page.getByTitle('Excluir operação').first().click()
  await page.getByRole('heading', { name: 'Confirmar exclusão' }).waitFor()
  await settle(page, 400)
  await shootBothThemes(page, 'epi-operations', 'modal-excluir-operacao')
})

test('epi-operations — hovers (dark)', async ({ page }) => {
  await openOperationsDefault(page)
  await page.getByRole('button', { name: 'Operação', exact: true }).hover()
  await page.waitForTimeout(300)
  await shoot(page, 'epi-operations', 'hover-btn-operacao')

  await page.getByTitle('Editar operação').first().hover()
  await page.waitForTimeout(300)
  await shoot(page, 'epi-operations', 'hover-editar')
})

// ===========================================================================
// PÁGINA 2 — epi-scenario-editor (/epi/cameras/1/scenario)
// ===========================================================================

test('epi-scenario-editor — default com zona desenhada (dark + light)', async ({ page }) => {
  await openScenarioDefault(page)
  // Seleciona tipo "Posição" → ferramenta zona
  await page.getByTestId('type-btn-position').click()
  await page.getByTestId('op-name-input').waitFor()
  await page.getByTestId('op-name-input').fill('Zona Estoque Químico')
  await page.getByLabel('Classe Capacete', { exact: true }).check()
  await page.getByLabel('Classe Colete', { exact: true }).check()
  // Desenha polígono de 4 pontos sobre o vídeo (ROIs existentes vêm da fixture)
  await drawPoints(page, [
    { x: 150, y: 95 },
    { x: 430, y: 82 },
    { x: 470, y: 255 },
    { x: 160, y: 285 },
  ])
  await settle(page, 500)
  await shootBothThemes(page, 'epi-scenario-editor', 'default')
})

test('epi-scenario-editor — empty (sem módulos)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/cameras/1/scenario**': { scenario: { ...SCENARIO, modules: [] } },
      '**/api/cameras/1/operations**': { operations: [] },
    },
  })
  await gotoAudit(page, '/epi/cameras/1/scenario')
  await page.getByText('Nenhum módulo habilitado').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'epi-scenario-editor', 'empty')
})

test('epi-scenario-editor — loading (stall)', async ({ page }) => {
  await setupApp(page, { stall: ['**/api/cameras/1/scenario**'] })
  await gotoAudit(page, '/epi/cameras/1/scenario')
  await page.getByText('Carregando cenário...').waitFor({ timeout: 30_000 })
  await page.waitForTimeout(1200)
  await shootBothThemes(page, 'epi-scenario-editor', 'loading')
})

test('epi-scenario-editor — error (500)', async ({ page }) => {
  await setupApp(page, {
    raw: {
      '**/api/cameras/1/scenario**': {
        status: 500,
        body: { status: 'error', error: 'Erro interno do servidor' },
      },
    },
  })
  await gotoAudit(page, '/epi/cameras/1/scenario')
  await page.getByRole('alert').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, 'epi-scenario-editor', 'error')
})

test('epi-scenario-editor — ferramenta linha', async ({ page }) => {
  await openScenarioDefault(page)
  await page.getByTestId('type-btn-count_line').click()
  await page.getByLabel('Ferramenta line (ativa)').waitFor()
  await page.getByTestId('op-name-input').fill('Linha Portaria Principal')
  await drawPoints(page, [
    { x: 110, y: 290 },
    { x: 520, y: 110 },
  ])
  await settle(page, 500)
  await shootBothThemes(page, 'epi-scenario-editor', 'tool-linha')
})

test('epi-scenario-editor — ferramenta ponto', async ({ page }) => {
  await openScenarioDefault(page)
  await page.getByTestId('type-btn-point_interest').click()
  await page.getByLabel('Ferramenta point (ativa)').waitFor()
  await page.getByTestId('op-name-input').fill('Ponto Extintor Corredor B')
  await drawPoints(page, [{ x: 320, y: 180 }])
  await settle(page, 500)
  await shootBothThemes(page, 'epi-scenario-editor', 'tool-ponto')
})

test('epi-scenario-editor — hover canvas (dark)', async ({ page }) => {
  await openScenarioDefault(page)
  await page.getByTestId('type-btn-position').click()
  await page.getByTestId('op-name-input').waitFor()
  await drawPoints(page, [
    { x: 180, y: 120 },
    { x: 420, y: 130 },
  ])
  // Hover no meio do canvas → indicador de hover + linha elástica do desenho
  await page.locator(CANVAS).hover({ position: { x: 330, y: 250 } })
  await page.waitForTimeout(300)
  await shoot(page, 'epi-scenario-editor', 'hover-canvas')
})
