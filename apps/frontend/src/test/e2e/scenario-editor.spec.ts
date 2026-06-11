/**
 * E2E tests — Editor visual de cenário (task-023 + task-039).
 * Usa mocks de API via page.route() — sem backend real.
 * Auth: page.addInitScript() seta localStorage antes de qualquer navegação.
 * task-039: testes de máscara de exclusão e perfil dia/noite.
 */
import { test, expect, type Page } from '@playwright/test'

const TEST_CAMERA_ID = 'cam1'
const SCENARIO_URL = `/epi/cameras/${TEST_CAMERA_ID}/scenario`

const MOCK_USER = {
  id: 'user1',
  email: 'test@test.com',
  name: 'Test User',
  role: 'operator' as const,
  tenant_id: 'tenant1',
  modules: ['ppe', 'fueling'],
}

const MOCK_TYPES = [
  {
    type_id: 'zone_presence',
    type_label: 'Zona de Presença',
    description: '',
    available_modules: ['ppe'],
    config_schema: {},
    metric_options: [],
    output_formats: [],
  },
]

async function setupAuth(page: Page) {
  await page.addInitScript(user => {
    localStorage.setItem('token', 'test-token-e2e-abc123')
    localStorage.setItem('user', JSON.stringify(user))
  }, MOCK_USER)
}

async function mockOperationTypes(page: Page) {
  await page.route('**/api/modules/**/operation-types', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: { types: MOCK_TYPES } }),
    })
  )
}

async function mockFallbackApi(page: Page) {
  await page.route('**/api/**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: {} }),
    })
  )
}

// ─── Teste 1: redirect para login sem autenticação ─────────────────────────

test('usuário não autenticado é redirecionado para login ao acessar o editor', async ({ page }) => {
  await page.route('**/api/**', route =>
    route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'unauthorized' }),
    })
  )
  // Sem setupAuth — localStorage vazio
  await page.goto(SCENARIO_URL)
  await expect(page.locator('input[type="email"]')).toBeVisible()
})

// ─── Teste 2: desenhar zona, salvar, verificar na sidebar ──────────────────

test('desenhar zona + salvar → operação aparece na sidebar', async ({ page }) => {
  const savedOps: unknown[] = []

  await setupAuth(page)
  await mockFallbackApi(page)  // LIFO: registrar primeiro → prioridade mais baixa
  await mockOperationTypes(page)

  await page.route(`**/api/cameras/${TEST_CAMERA_ID}/operations**`, async route => {
    const method = route.request().method()
    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: { operations: savedOps } }),
      })
    } else {
      const op = {
        id: 1,
        camera_id: TEST_CAMERA_ID,
        module_id: 'ppe',
        type_id: 'zone_presence',
        type_label: 'Zona de Presença',
        name: 'Zona Teste',
        config: {
          roi: [{ x: 0.1, y: 0.1 }, { x: 0.5, y: 0.1 }, { x: 0.5, y: 0.5 }],
          classes: [],
          threshold: 0.5,
        },
        status: 'active',
        version: 1,
        created_at: new Date().toISOString(),
      }
      savedOps.push(op)
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: { operation: op } }),
      })
    }
  })

  await page.goto(SCENARIO_URL)

  // Editor carregou
  await expect(page.locator('text=Editor de Cenário')).toBeVisible()

  // Seleciona tipo de operação
  await page.selectOption('[aria-label="Selecionar tipo de operação"]', 'zone_presence')

  // Desenha 3 pontos no canvas (zona)
  const canvas = page.locator('[data-testid="canvas-interaction-layer"]')
  await canvas.click({ position: { x: 100, y: 80 } })
  await canvas.click({ position: { x: 300, y: 80 } })
  await canvas.click({ position: { x: 200, y: 200 } })

  // Preenche nome
  await page.fill('[aria-label="Nome da operação"]', 'Zona Teste')

  // Salva
  await page.click('[aria-label="Salvar operação"]')

  // Feedback de sucesso
  await expect(page.locator('text=Operação salva!')).toBeVisible()

  // Operação aparece na sidebar
  await expect(page.locator('[data-testid="operation-item-1"]')).toBeVisible()
  await expect(page.locator('[data-testid="operation-item-1"]')).toContainText('Zona Teste')
})

// ─── Teste 3: após reload, geometria persiste ──────────────────────────────

test('após salvar e recarregar, operação persiste (geometria volta na sidebar)', async ({ page }) => {
  // Simula operação já existente no backend (como se tivesse sido salva anteriormente)
  const persistedOp = {
    id: 42,
    camera_id: TEST_CAMERA_ID,
    module_id: 'ppe',
    type_id: 'zone_presence',
    type_label: 'Zona de Presença',
    name: 'Zona Persistida',
    config: {
      roi: [{ x: 0.1, y: 0.1 }, { x: 0.5, y: 0.1 }, { x: 0.5, y: 0.5 }],
      classes: ['helmet'],
      threshold: 0.7,
    },
    status: 'active',
    version: 1,
    created_at: '2024-01-01T00:00:00Z',
  }

  await setupAuth(page)
  await mockFallbackApi(page)  // LIFO: registrar primeiro → prioridade mais baixa
  await mockOperationTypes(page)

  await page.route(`**/api/cameras/${TEST_CAMERA_ID}/operations**`, route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: { operations: [persistedOp] } }),
    })
  )

  await page.goto(SCENARIO_URL)

  // Operação aparece na primeira carga
  await expect(page.locator('[data-testid="operation-item-42"]')).toBeVisible()
  await expect(page.locator('[data-testid="operation-item-42"]')).toContainText('Zona Persistida')

  // Recarrega a página (simula navegação de volta)
  await page.reload()

  // Após reload, operação ainda está presente (geometry persisted)
  await expect(page.locator('[data-testid="operation-item-42"]')).toBeVisible()
  await expect(page.locator('[data-testid="operation-item-42"]')).toContainText('Zona Persistida')
})

// ─── Teste 4 (task-039): desenhar máscara → salvar → config tem exclude_zones ──

test('desenhar máscara de exclusão + salvar → config inclui exclude_zones', async ({ page }) => {
  let capturedBody: Record<string, unknown> | null = null

  await setupAuth(page)
  await mockFallbackApi(page)
  await mockOperationTypes(page)

  await page.route(`**/api/cameras/${TEST_CAMERA_ID}/operations**`, async route => {
    const method = route.request().method()
    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: { operations: [] } }),
      })
    } else {
      capturedBody = route.request().postDataJSON() as Record<string, unknown>
      const op = {
        id: 10, camera_id: TEST_CAMERA_ID, module_id: 'ppe',
        type_id: 'zone_presence', name: 'Zona com Máscara',
        config: capturedBody?.config ?? {},
        status: 'active', version: 1, created_at: new Date().toISOString(),
      }
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: { operation: op } }),
      })
    }
  })

  await page.goto(SCENARIO_URL)
  await expect(page.locator('text=Editor de Cenário')).toBeVisible()

  // Seleciona tipo
  await page.selectOption('[aria-label="Selecionar tipo de operação"]', 'zone_presence')

  // Muda para ferramenta de máscara
  await page.click('button:has-text("Máscara (exclusão)")')

  // Desenha 3 pontos de exclusão
  const canvas = page.locator('[data-testid="canvas-interaction-layer"]')
  await canvas.click({ position: { x: 50, y: 50 } })
  await canvas.click({ position: { x: 100, y: 50 } })
  await canvas.click({ position: { x: 75, y: 100 } })

  // Confirma a máscara
  await page.click('[aria-label="Adicionar zona de exclusão"]')

  // Verifica resumo
  await expect(page.locator('text=1 zona(s) de exclusão')).toBeVisible()

  // Volta para zona e preenche nome
  await page.click('button:has-text("Zona (polígono)")')
  await page.fill('[aria-label="Nome da operação"]', 'Zona com Máscara')

  // Salva
  await page.click('[aria-label="Salvar operação"]')
  await expect(page.locator('text=Operação salva!')).toBeVisible()

  // Após salvar: resumo de máscaras sumiu
  await expect(page.locator('text=zona(s) de exclusão')).not.toBeVisible()

  // Verifica payload enviado ao backend
  expect(capturedBody).not.toBeNull()
  const config = (capturedBody as { config?: { exclude_zones?: unknown[] } }).config
  expect(Array.isArray(config?.exclude_zones)).toBe(true)
  expect(config?.exclude_zones?.length).toBe(1)
})

// ─── Teste 5 (task-039): campos dia/noite salvos no config ────────────────

test('configurar confidence dia/noite → config inclui day_night_profile', async ({ page }) => {
  let capturedBody: Record<string, unknown> | null = null

  await setupAuth(page)
  await mockFallbackApi(page)
  await mockOperationTypes(page)

  await page.route(`**/api/cameras/${TEST_CAMERA_ID}/operations**`, async route => {
    const method = route.request().method()
    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: { operations: [] } }),
      })
    } else {
      capturedBody = route.request().postDataJSON() as Record<string, unknown>
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: {
            operation: {
              id: 11, camera_id: TEST_CAMERA_ID, module_id: 'ppe',
              type_id: 'zone_presence', name: 'Zona Dia Noite',
              config: capturedBody?.config ?? {},
              status: 'active', version: 1, created_at: new Date().toISOString(),
            },
          },
        }),
      })
    }
  })

  await page.goto(SCENARIO_URL)
  await expect(page.locator('text=Editor de Cenário')).toBeVisible()

  await page.selectOption('[aria-label="Selecionar tipo de operação"]', 'zone_presence')
  await page.fill('[aria-label="Nome da operação"]', 'Zona Dia Noite')
  await page.fill('[aria-label="Confidence (dia)"]', '0.4')
  await page.fill('[aria-label="Confidence (noite)"]', '0.8')

  await page.click('[aria-label="Salvar operação"]')
  await expect(page.locator('text=Operação salva!')).toBeVisible()

  expect(capturedBody).not.toBeNull()
  type ProfileType = { day?: { confidence: number }; night?: { confidence: number } }
  const config = (capturedBody as { config?: { day_night_profile?: ProfileType } }).config
  expect(config?.day_night_profile?.day?.confidence).toBe(0.4)
  expect(config?.day_night_profile?.night?.confidence).toBe(0.8)
})
