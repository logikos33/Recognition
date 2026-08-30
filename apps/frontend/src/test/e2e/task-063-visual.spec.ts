/**
 * Task-063 — evidência visual do painel "Desempenho por câmera" (CamerasPage)
 * e da tela de Operação (TrainingModeLayout).
 *
 * PR-B (30/08) demoliu `EpiCameras.tsx`/`EpiOperationsPage.tsx`; o FLIP (29/08,
 * mergeado depois) tirou o prefixo `/novo`. Juntos: `/epi/cameras` e
 * `/epi/cameras/:id/operations` são hoje SOMBREADAS pelo front novo — mesmo
 * endereço, o front novo (estático) sempre vence o antigo (ver teste "só as
 * rotas antigas explicitamente sombreadas..." em `app/coexistencia.test.tsx`).
 * `CamerasPage` e `TrainingModeLayout` ficam inalcançáveis nessas URLs até a
 * demolição completa (`docs/migration/MANIFESTO-FRONT-ANTIGO.md`). Este
 * harness passou a provar a MESMA FUNÇÃO nas telas substitutas: o painel de
 * FPS/qualidade + saúde do equipamento virou a 5ª aba "Desempenho" de
 * `app/epi/Cameras.tsx` (handoff-v2 Main, PR #576); a lista de
 * ferramentas/operações registradas virou `app/epi/Operacoes.tsx` (spec
 * `Câmera Operações.dc.html`). Recuperação das telas antigas: `git show
 * archive/front-antigo-epi-lote1-2026-08-30:apps/frontend/src/pages/epi/EpiCameras.tsx`.
 *
 * Não faz asserções funcionais: captura screenshots antes/depois da correção
 * visual (tokens WS1). Controle do prefixo via env SHOT_PREFIX=before|after.
 *
 * Uso:
 *   SHOT_PREFIX=before npx playwright test task-063-visual
 *   SHOT_PREFIX=after  npx playwright test task-063-visual
 */
import { test, type Page } from '@playwright/test'
import * as path from 'node:path'
import * as fs from 'node:fs'

const PREFIX = process.env.SHOT_PREFIX ?? 'after'
// apps/frontend → raiz do repo → docs/quality/evidence/task-063
// EVIDENCE_DIR permite rodar o harness num worktree (ex.: staging) gravando
// as evidências no worktree do fix.
const OUT_DIR =
  process.env.EVIDENCE_DIR ??
  path.resolve(process.cwd(), '../../docs/quality/evidence/task-063')

const CAMERA = {
  id: '1',
  name: 'Câmera Pátio',
  location: 'Pátio Norte',
  manufacturer: 'hikvision',
  ip_address: '10.0.0.5',
  port: 554,
  stream_status: 'inactive',
  is_active: true,
  fps_target: 5,
  quality_preset: 'medium',
}

// Campos consumidos por `app/epi/Operacoes.tsx` (operation_repository.py:24-26).
const OPERATIONS = [
  {
    id: 101,
    camera_id: '1',
    module_id: 'ppe',
    type_id: 'position',
    name: 'Zona Portão Leste',
    status: 'active',
    version: 1,
    last_evaluated_at: new Date().toISOString(),
  },
  {
    id: 102,
    camera_id: '1',
    module_id: 'ppe',
    type_id: 'count_static',
    name: 'Contagem Doca 2',
    status: 'error',
    version: 1,
    last_evaluated_at: null,
  },
]

// Operacoes.tsx resolve `module_id` → `module_code` via GET /modules/ — a
// tela antiga usava operation-types (form de criação, que Operacoes.tsx não
// tem: "Nova operação" fica desabilitado, sem endpoint desenhado).
const MODULES = [{ id: 'ppe', module_code: 'ppe' }]

async function setupRoutes(page: Page, theme: 'recognition-dark' | 'professional') {
  // Catch-all PRIMEIRO — Playwright avalia rotas na ordem inversa de registro,
  // então as rotas específicas abaixo têm precedência sobre esta.
  await page.route('**/api/**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: {} }),
    })
  )

  await page.route('**/api/cameras/1/health-context**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        data: {
          has_telemetry: false,
          derived_status: null,
          metrics: null,
          fps_demand_total: 0,
          cameras_active_count: 0,
        },
      }),
    })
  )

  await page.route('**/api/cameras/1/operations**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: { operations: OPERATIONS } }),
    })
  )

  // Operacoes.tsx busca a câmera SEM o sufixo /operations, à parte — a rota
  // antiga não precisava porque o nome já vinha embutido no payload da lista.
  await page.route('**/api/cameras/1', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: CAMERA }),
    })
  )

  await page.route('**/api/modules/**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: { modules: MODULES } }),
    })
  )

  await page.route('**/api/cameras', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        data: { cameras: [CAMERA], gateway_status: { status: 'online' } },
      }),
    })
  )

  await page.addInitScript(
    ([mode]) => {
      localStorage.setItem('token', 'fake-jwt-token')
      localStorage.setItem(
        'user',
        JSON.stringify({ email: 'test@test.com', role: 'admin', full_name: 'Test Admin' })
      )
      localStorage.setItem(
        'recognition-theme',
        JSON.stringify({ state: { mode }, version: 0 })
      )
    },
    [theme]
  )
}

async function shoot(page: Page, name: string) {
  fs.mkdirSync(OUT_DIR, { recursive: true })
  await page.screenshot({ path: path.join(OUT_DIR, `${PREFIX}-${name}.png`), fullPage: false })
}

/**
 * Simula um tenant white-label com superfícies CLARAS (WS1 permite o tenant
 * configurar bgBase/bgSurface/bgCard/textPrimary/... em runtime).
 *
 * Estratégia dupla:
 * 1. Sobrescreve as CSS custom properties planas da bridge WS1 em :root
 *    (--color-bg-base etc.) — é exatamente o mecanismo que o resolver de
 *    tenant-theme usa em produção.
 * 2. Fallback por enumeração: varre as custom props computadas do body e,
 *    para as que ainda resolvem nos hex default da marca (vars hasheadas do
 *    vanilla-extract sem bridge), aplica o tom claro/escuro correspondente
 *    inline em documentElement.
 *
 * Resultado: componentes tokenizados acompanham (ficam legíveis); texto
 * rgba(255,255,255,x) hardcoded fica ilegível sobre superfícies claras =
 * reprodução do bug relatado na staging.
 */
const LIGHT_SURFACE_CSS = `:root {
  --color-bg-base: #f4f5f7;
  --color-bg-surface: #ffffff;
  --color-bg-card: #eceef1;
  --color-bg-elevated: #ffffff;
  --color-bg-hover: #e2e5ea;
  --color-text-primary: #1a1d23;
  --color-text-secondary: #3f4650;
  --color-text-muted: #6b7280;
  --color-border-subtle: #e2e5ea;
  --color-border: #d4d8de;
  --color-border-strong: #b8bec7;
}`

const DARK_TO_LIGHT_MAP: Record<string, string> = {
  // superfícies escuras default → tons claros
  'rgb(10, 12, 16)': '#f4f5f7',   // bgBase #0a0c10
  'rgb(17, 19, 24)': '#ffffff',   // bgSurface #111318
  'rgb(22, 26, 32)': '#eceef1',   // bgCard #161a20
  'rgb(30, 35, 48)': '#ffffff',   // bgElevated #1e2330
  'rgb(26, 31, 39)': '#e2e5ea',   // bgHover #1a1f27
  // textos claros default → tons escuros
  'rgb(240, 244, 248)': '#1a1d23', // textPrimary #f0f4f8
  'rgb(139, 163, 188)': '#3f4650', // textSecondary #8ba3bc
  'rgb(102, 128, 150)': '#6b7280', // textMuted #668096
}

async function applyLightSurfaces(page: Page) {
  await page.addStyleTag({ content: LIGHT_SURFACE_CSS })
  await page.evaluate((mapping: Record<string, string>) => {
    const hexToRgb = (hex: string): string => {
      const n = hex.replace('#', '')
      const r = parseInt(n.slice(0, 2), 16)
      const g = parseInt(n.slice(2, 4), 16)
      const b = parseInt(n.slice(4, 6), 16)
      return `rgb(${r}, ${g}, ${b})`
    }
    const hexMap: Record<string, string> = {}
    for (const [k, v] of Object.entries(mapping)) hexMap[k] = v
    const cs = getComputedStyle(document.body)
    for (let i = 0; i < cs.length; i++) {
      const prop = cs[i]
      if (!prop.startsWith('--')) continue
      const raw = cs.getPropertyValue(prop).trim()
      // resolve valores hex diretos comparando na forma rgb()
      const asRgb = raw.startsWith('#') ? hexToRgb(raw) : raw
      const light = hexMap[asRgb]
      if (light) document.documentElement.style.setProperty(prop, light)
    }
  }, DARK_TO_LIGHT_MAP)
  await page.waitForTimeout(400)
}

const THEMES = ['recognition-dark', 'professional'] as const

for (const theme of THEMES) {
  test.describe(`task-063 evidência visual — tema ${theme}`, () => {
    test(`Cameras — aba Desempenho (${theme})`, async ({ page }) => {
      await setupRoutes(page, theme)
      await page.goto('/epi/cameras')
      // Seleciona a câmera na lista lateral
      await page.getByText('Câmera Pátio').first().click()
      await page.getByRole('tab', { name: 'Desempenho' }).click()
      await page.getByText('Quadros por segundo analisados').waitFor({ state: 'visible' })
      await page.waitForTimeout(800)
      await shoot(page, `cameras-fps-${theme}`)
    })

    test(`Operações da câmera — app/epi/Operacoes (${theme})`, async ({ page }) => {
      await setupRoutes(page, theme)
      await page.goto('/epi/cameras/1/operations')
      await page.getByText('Zona Portão Leste').first().waitFor({ state: 'visible' })
      await page.waitForTimeout(800)
      await shoot(page, `operations-${theme}`)
    })
  })
}

test.describe('task-063 — white-label com superfícies claras (repro do bug)', () => {
  test('Cameras · aba Desempenho sob superfícies claras', async ({ page }) => {
    await setupRoutes(page, 'recognition-dark')
    await page.goto('/epi/cameras')
    await page.getByText('Câmera Pátio').first().click()
    await page.getByRole('tab', { name: 'Desempenho' }).click()
    await page.getByText('Quadros por segundo analisados').waitFor({ state: 'visible' })
    await page.waitForTimeout(500)
    await applyLightSurfaces(page)
    await shoot(page, 'lightsurface-cameras-fps')
  })

  test('Operações sob superfícies claras', async ({ page }) => {
    await setupRoutes(page, 'recognition-dark')
    await page.goto('/epi/cameras/1/operations')
    await page.getByText('Zona Portão Leste').first().waitFor({ state: 'visible' })
    await page.waitForTimeout(500)
    await applyLightSurfaces(page)
    await shoot(page, 'lightsurface-operations')
  })
})

// Hovers só fazem sentido no código do fix (:hover via .css.ts).
// SKIP_HOVER=1 ao rodar no worktree da staging.
test.describe('task-063 — estados de hover (fix)', () => {
  test.skip(!!process.env.SKIP_HOVER, 'hover states não aplicáveis neste branch')

  test('hover em botão de FPS da aba Desempenho', async ({ page }) => {
    await setupRoutes(page, 'recognition-dark')
    await page.goto('/epi/cameras')
    await page.getByText('Câmera Pátio').first().click()
    await page.getByRole('tab', { name: 'Desempenho' }).click()
    await page.getByRole('button', { name: '10 fps' }).hover()
    await page.waitForTimeout(400)
    await shoot(page, 'hover-fps-btn')
  })

  test('hover em cartão de operação', async ({ page }) => {
    await setupRoutes(page, 'recognition-dark')
    await page.goto('/epi/cameras/1/operations')
    await page.getByText('Zona Portão Leste').first().hover()
    await page.waitForTimeout(400)
    await shoot(page, 'hover-tools-card')
  })

  test('hover em item da lista lateral de câmeras', async ({ page }) => {
    await setupRoutes(page, 'recognition-dark')
    await page.goto('/epi/cameras')
    await page.getByText('Câmera Pátio').first().waitFor({ state: 'visible' })
    await page.getByText('Câmera Pátio').first().hover()
    await page.waitForTimeout(400)
    await shoot(page, 'hover-camera-list')
  })
})
