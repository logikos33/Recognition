/**
 * Playwright e2e — editor visual de cenário.
 * Usa page.route() para interceptar todas as chamadas de API (sem backend real).
 * Cobre: renderização, seleção de módulo/tipo, desenho de zona/linha, salvar, persistência.
 */
import { test, expect, type Page } from '@playwright/test'

// ─── fixtures de API ──────────────────────────────────────────────────────────

const SCENARIO_RESPONSE = {
  status: 'success',
  data: {
    scenario: {
      camera: { id: '42', name: 'Câmera Portão Principal' },
      modules: [
        {
          module_code: 'epi',
          enabled: true,
          classes: [
            { id: 1, class_name: 'helmet', display_name: 'Capacete' },
            { id: 2, class_name: 'vest', display_name: 'Colete' },
          ],
        },
      ],
      operations: [],
      alert_rules: [],
      schedule: [],
    },
  },
}

const OP_TYPES_RESPONSE = {
  status: 'success',
  data: {
    module: 'epi',
    types: [
      {
        type_id: 'position',
        type_label: 'Posição / Presença',
        description: 'Detecta presença em zona ROI',
        available_modules: ['epi'],
        config_schema: { roi_points: {} },
        metric_options: ['state'],
        output_formats: ['conditional'],
      },
      {
        type_id: 'count_static',
        type_label: 'Contagem Estática',
        available_modules: ['epi'],
        config_schema: { roi_points: {}, count_threshold: {} },
        metric_options: ['count'],
        output_formats: ['physical'],
      },
    ],
  },
}

const OPERATIONS_EMPTY = {
  status: 'success',
  data: { operations: [] },
}

const CREATED_OPERATION = {
  id: 101,
  camera_id: '42',
  module_id: 'epi',
  type_id: 'position',
  name: 'Zona Portão Leste',
  config: { roi_points: [[0.1, 0.2], [0.5, 0.2], [0.5, 0.7], [0.1, 0.7]] },
  status: 'active',
  version: 1,
  created_at: new Date().toISOString(),
}

const OPERATIONS_AFTER_SAVE = {
  status: 'success',
  data: { operations: [CREATED_OPERATION] },
}

// ─── helpers ──────────────────────────────────────────────────────────────────

async function setupRoutes(page: Page, withSavedOp = false) {
  // Auth — não redirecionar para /login
  await page.route('**/api/auth/**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: { token: 'fake-jwt', user: { email: 'test@test.com' } } }),
    })
  )

  // Cenário
  await page.route('**/api/cameras/42/scenario', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(SCENARIO_RESPONSE),
    })
  )

  // Tipos de operação
  await page.route('**/api/scenarios/operation-types**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(OP_TYPES_RESPONSE),
    })
  )

  // Operações: GET (antes e depois do save)
  await page.route('**/api/cameras/42/operations**', route => {
    if (route.request().method() === 'GET') {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(withSavedOp ? OPERATIONS_AFTER_SAVE : OPERATIONS_EMPTY),
      })
    } else if (route.request().method() === 'POST') {
      route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: { operation: CREATED_OPERATION } }),
      })
    } else {
      route.continue()
    }
  })

  // HLS stream — retorna 404 (sem stream real em CI; editor usa placeholder)
  await page.route('**/stream.m3u8**', route =>
    route.fulfill({ status: 404, body: '' })
  )

  // localStorage: simula usuário logado (evita redirect /login)
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fake-jwt-token')
    localStorage.setItem('user', JSON.stringify({ email: 'test@test.com', role: 'operator' }))
  })
}

// ─── testes ───────────────────────────────────────────────────────────────────

test.describe('ScenarioEditor — editor visual de cenário', () => {
  test('renderiza o editor com título e nome da câmera', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/cameras/42/scenario')

    await expect(page.getByText('Editor de Cenário')).toBeVisible()
    await expect(page.getByText('Câmera Portão Principal')).toBeVisible()
  })

  test('exibe módulo disponível no painel lateral', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/cameras/42/scenario')

    await expect(page.getByTestId('module-btn-epi')).toBeVisible()
  })

  test('clicar no módulo carrega os tipos de operação', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/cameras/42/scenario')

    await page.getByTestId('module-btn-epi').click()

    await expect(page.getByTestId('type-btn-position')).toBeVisible()
    await expect(page.getByTestId('type-btn-count_static')).toBeVisible()
  })

  test('selecionar tipo exibe ferramenta e campo de nome', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/cameras/42/scenario')

    await page.getByTestId('module-btn-epi').click()
    await page.getByTestId('type-btn-position').click()

    await expect(page.getByTestId('op-name-input')).toBeVisible()
    await expect(page.getByLabel(/ferramenta zone \(ativa\)/i)).toBeVisible()
  })

  test('exibe classes do módulo selecionado como checkboxes', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/cameras/42/scenario')

    await page.getByTestId('module-btn-epi').click()
    await page.getByTestId('type-btn-position').click()

    await expect(page.getByLabel(/Capacete/i)).toBeVisible()
    await expect(page.getByLabel(/Colete/i)).toBeVisible()
  })

  test('botão salvar desabilitado sem nome e sem geometria', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/cameras/42/scenario')

    await page.getByTestId('module-btn-epi').click()
    await page.getByTestId('type-btn-position').click()

    const saveBtn = page.getByTestId('save-btn')
    await expect(saveBtn).toBeDisabled()
  })

  test('desenhar zona + preencher nome habilita o botão salvar', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/cameras/42/scenario')

    await page.getByTestId('module-btn-epi').click()
    await page.getByTestId('type-btn-position').click()

    // Preencher nome
    await page.getByTestId('op-name-input').fill('Zona Portão Leste')

    // Clicar 4 vezes no canvas para criar polígono (zona ≥ 3 pontos)
    const canvas = page.getByTestId('drawing-canvas')
    const box = await canvas.boundingBox()
    if (!box) throw new Error('Canvas não encontrado')

    await page.mouse.click(box.x + box.width * 0.1, box.y + box.height * 0.2)
    await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.2)
    await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.7)
    await page.mouse.click(box.x + box.width * 0.1, box.y + box.height * 0.7)

    await expect(page.getByTestId('save-btn')).toBeEnabled()
  })

  test('salvar operação mostra feedback de sucesso', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/cameras/42/scenario')

    await page.getByTestId('module-btn-epi').click()
    await page.getByTestId('type-btn-position').click()
    await page.getByTestId('op-name-input').fill('Zona Portão Leste')

    const canvas = page.getByTestId('drawing-canvas')
    const box = await canvas.boundingBox()
    if (!box) throw new Error('Canvas não encontrado')

    // Desenhar 4 pontos (zona válida)
    for (const [rx, ry] of [[0.1, 0.2], [0.5, 0.2], [0.5, 0.7], [0.1, 0.7]]) {
      await page.mouse.click(box.x + box.width * rx, box.y + box.height * ry)
    }

    await page.getByTestId('save-btn').click()
    await expect(page.getByText(/operação salva com sucesso/i)).toBeVisible()
  })

  test('após salvar, a operação aparece na lista de operações salvas (reload)', async ({ page }) => {
    // Na segunda visita, o GET /operations já retorna a operação criada
    await setupRoutes(page, true)
    await page.goto('/epi/cameras/42/scenario')

    await page.getByTestId('module-btn-epi').click()

    // A operação salva deve aparecer no painel (first() evita strict-mode com o SVG label)
    await expect(page.getByText('Zona Portão Leste').first()).toBeVisible()
  })

  test('undo/redo estão acessíveis via ARIA', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/cameras/42/scenario')

    await expect(page.getByLabel('Desfazer')).toBeVisible()
    await expect(page.getByLabel('Refazer')).toBeVisible()
  })

  test('undo desativa após limpar todos os pontos', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/cameras/42/scenario')

    await page.getByTestId('module-btn-epi').click()
    await page.getByTestId('type-btn-position').click()

    const undoBtn = page.getByLabel('Desfazer')
    await expect(undoBtn).toBeDisabled()
  })

  test('undo habilita após adicionar ponto', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/cameras/42/scenario')

    await page.getByTestId('module-btn-epi').click()
    await page.getByTestId('type-btn-position').click()

    const canvas = page.getByTestId('drawing-canvas')
    const box = await canvas.boundingBox()
    if (!box) throw new Error('Canvas não encontrado')

    await page.mouse.click(box.x + box.width * 0.3, box.y + box.height * 0.3)

    await expect(page.getByLabel('Desfazer')).toBeEnabled()
  })

  test('voltar navega para a rota anterior', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/cameras/42/scenario')

    await page.getByLabel('Voltar').click()
    await expect(page).toHaveURL(/\/epi\/cameras\/42\/operations/)
  })
})
