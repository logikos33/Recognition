/**
 * Visual-audit harness — helpers compartilhados (AUDITORIA, não altera produção).
 *
 * Adaptado do harness de evidência da task-063 (branch fix/task-063):
 * - Mock de API por rota (catch-all + fixtures específicas por endpoint)
 * - JWT fake via localStorage (sem backend)
 * - Tema via localStorage `recognition-theme`
 * - Simulação de tenant white-label com superfícies CLARAS (mesmo mecanismo
 *   do resolver de tenant-theme: CSS custom properties planas em :root,
 *   com fallback por enumeração das vars hasheadas do vanilla-extract)
 *
 * Screenshots: docs/quality/visual-audit/screenshots/<tela>/<tema>-<estado>.png
 */
import { type Page } from '@playwright/test'
import * as path from 'node:path'
import * as fs from 'node:fs'

export const OUT_DIR =
  process.env.AUDIT_OUT_DIR ??
  path.resolve(process.cwd(), '../../docs/quality/visual-audit/screenshots')

export interface SetupOptions {
  /** false = sem token → App renderiza a tela de Login */
  auth?: boolean
  role?: 'superadmin' | 'admin' | 'operator' | 'viewer'
  /** glob de URL → payload de `data` (embrulhado em {status:'success', data}) */
  fixtures?: Record<string, unknown>
  /** glob → resposta crua (status/erro/formatos especiais) */
  raw?: Record<string, { status?: number; body?: unknown; contentType?: string }>
  /** globs que NUNCA respondem → estado de carregando persistente */
  stall?: string[]
}

export async function setupApp(page: Page, opts: SetupOptions = {}) {
  const { auth = true, role = 'superadmin', fixtures = {}, raw = {}, stall = [] } = opts

  // Catch-all PRIMEIRO — Playwright avalia rotas na ordem inversa de registro,
  // então as rotas específicas registradas depois têm precedência.
  await page.route('**/api/**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: {} }),
    })
  )

  for (const [glob, data] of Object.entries(fixtures)) {
    await page.route(glob, route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data }),
      })
    )
  }

  for (const [glob, r] of Object.entries(raw)) {
    await page.route(glob, route =>
      route.fulfill({
        status: r.status ?? 200,
        contentType: r.contentType ?? 'application/json',
        body: typeof r.body === 'string' ? r.body : JSON.stringify(r.body ?? {}),
      })
    )
  }

  for (const glob of stall) {
    await page.route(glob, () => {
      /* nunca responde → loading persistente pro screenshot */
    })
  }

  // Sem stream HLS nos screenshots
  await page.route('**/*.m3u8**', route => route.fulfill({ status: 404, body: '' }))

  await page.addInitScript(
    ([withAuth, userRole]) => {
      if (withAuth === 'yes') {
        localStorage.setItem('token', 'fake-jwt-token')
        localStorage.setItem(
          'user',
          JSON.stringify({
            id: 'u-audit-1',
            email: 'auditor@recognition.dev',
            name: 'Auditor Visual',
            role: userRole,
            tenant_id: '00000000-0000-0000-0000-000000000001',
            modules: ['epi', 'fueling', 'quality'],
          })
        )
      }
      localStorage.setItem(
        'recognition-theme',
        JSON.stringify({ state: { mode: 'recognition-dark' }, version: 0 })
      )
    },
    [auth ? 'yes' : 'no', role]
  )
}

/**
 * Superfícies claras de tenant white-label (WS1). Mesmos valores usados na
 * reprodução do bug da task-063 na staging.
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
  'rgb(10, 12, 16)': '#f4f5f7', // bgBase #0a0c10
  'rgb(17, 19, 24)': '#ffffff', // bgSurface #111318
  'rgb(22, 26, 32)': '#eceef1', // bgCard #161a20
  'rgb(30, 35, 48)': '#ffffff', // bgElevated #1e2330
  'rgb(26, 31, 39)': '#e2e5ea', // bgHover #1a1f27
  // textos claros default → tons escuros
  'rgb(240, 244, 248)': '#1a1d23', // textPrimary #f0f4f8
  'rgb(139, 163, 188)': '#3f4650', // textSecondary #8ba3bc
  'rgb(102, 128, 150)': '#6b7280', // textMuted #668096
}

export async function applyLightSurfaces(page: Page) {
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
      const asRgb = raw.startsWith('#') ? hexToRgb(raw) : raw
      const light = hexMap[asRgb]
      if (light) document.documentElement.style.setProperty(prop, light)
    }
  }, DARK_TO_LIGHT_MAP)
  await page.waitForTimeout(400)
}

export async function shoot(page: Page, screen: string, name: string, fullPage = false) {
  const dir = path.join(OUT_DIR, screen)
  fs.mkdirSync(dir, { recursive: true })
  await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage })
}

/**
 * Captura a MESMA visão nos dois temas: dark primeiro, depois aplica as
 * superfícies claras (irreversível na page — re-navegar pro próximo estado).
 */
export async function shootBothThemes(
  page: Page,
  screen: string,
  state: string,
  fullPage = false
) {
  await shoot(page, screen, `dark-${state}`, fullPage)
  await applyLightSurfaces(page)
  await shoot(page, screen, `light-${state}`, fullPage)
}

export async function settle(page: Page, ms = 800) {
  await page.waitForLoadState('networkidle').catch(() => {})
  await page.waitForTimeout(ms)
}

/**
 * Navegação tolerante a cold-compile do Vite dev server (primeira request
 * numa rota compila on-demand e pode passar de 30s).
 */
export async function gotoAudit(page: Page, url: string) {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60_000 })
}
