/**
 * Auditoria visual — Grupo 23: Admin Branding / White-Label (tier 2, superadmin).
 *
 * Branding é o CORAÇÃO do WS1 — o editor é capturado com valores de
 * superfície PREENCHIDOS (Containers & Superfícies expandido).
 *
 * Páginas e endpoints reais consumidos (adminService → api.ts, base /api):
 * - /admin/branding/tenants        → GET /api/v1/admin/tenants                    → { tenants: Tenant[] }
 *                                    GET /api/v1/admin/tenants/:id/branding (xN)  → { branding: TenantBranding }
 * - /admin/branding/tenants/:id    → GET /api/v1/admin/tenants/:id                → { tenant: Tenant }
 *                                    GET /api/v1/admin/tenants/:id/branding       → { branding: TenantBranding }
 * - /admin/branding/default        → estático (catálogo de tokens, read-only)
 * - /admin/branding/sandbox        → estático (estado local, nada salvo)
 * - /design-system                 → estático (fora do AdminLayout, gate AdminRoute)
 *
 * AdminLayout chama GET /api/v1/admin/dashboard em toda rota /admin/* (badges)
 * e o ThemeProvider chama GET /api/v1/tenant/branding no boot — ambos mockados.
 */
import { test, type Page } from '@playwright/test'
import { setupApp, shootBothThemes, shoot, settle, gotoAudit } from './helpers'

/* ── Helpers de data ────────────────────────────────────────────── */

const daysAgo = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString()

/* ── Fixtures pt-BR ─────────────────────────────────────────────── */

// Logo inline (data URL) — evita fetch externo no screenshot
const RVB_LOGO =
  'data:image/svg+xml;base64,' +
  Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40">` +
      `<rect width="120" height="40" rx="6" fill="#16a34a"/>` +
      `<text x="60" y="26" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#ffffff" text-anchor="middle">RVB</text>` +
      `</svg>`,
  ).toString('base64')

// Badges da sidebar do AdminLayout (mesmo shape do grupo 19)
const DASHBOARD = {
  tenants_active: 8,
  users_total: 164,
  cameras_online: 42,
  alerts_24h: 37,
  training_approvals_pending: 3,
  tickets_open: 5,
  mrr_estimated: 48200,
  workers: { online: 6, fallback: 2, offline: 1 },
  recent_critical_events: [],
  top_tenants_users: [],
}

const TENANTS = [
  {
    id: 't-0001', slug: 'rvb-industrial', name: 'Tenant RVB Industrial', plan: 'enterprise',
    schema_name: 'tenant_rvb', modules_enabled: ['epi', 'quality'], is_active: true,
    requires_training_approval: true, mrr_per_camera: {}, contract_cameras: 12,
    user_count: 32, worker_status: 'onpremise', created_at: daysAgo(236),
  },
  {
    id: 't-0002', slug: 'horizonte-sul', name: 'Construtora Horizonte Sul', plan: 'premium',
    schema_name: 'tenant_horizonte', modules_enabled: ['epi'], is_active: true,
    requires_training_approval: true, mrr_per_camera: {}, contract_cameras: 8,
    user_count: 18, worker_status: 'railway', created_at: daysAgo(180),
  },
  {
    id: 't-0003', slug: 'metalurgica-sao-carlos', name: 'Metalúrgica São Carlos', plan: 'standard',
    schema_name: 'tenant_msc', modules_enabled: ['epi'], is_active: true,
    requires_training_approval: false, mrr_per_camera: {}, contract_cameras: 5,
    user_count: 9, worker_status: 'offline', created_at: daysAgo(120),
  },
  {
    id: 't-0004', slug: 'vale-verde', name: 'Agroindústria Vale Verde', plan: 'basic',
    schema_name: 'tenant_valeverde', modules_enabled: ['epi'], is_active: false,
    suspended_at: daysAgo(6), requires_training_approval: false, mrr_per_camera: {},
    contract_cameras: 2, user_count: 4, created_at: daysAgo(90),
  },
  {
    id: 't-0005', slug: 'transportadora-andrade', name: 'Transportadora Andrade & Filhos', plan: 'standard',
    schema_name: 'tenant_andrade', modules_enabled: ['epi'], is_active: true,
    requires_training_approval: false, mrr_per_camera: {}, contract_cameras: 6,
    user_count: 12, worker_status: 'railway', created_at: daysAgo(45),
  },
]

// Branding padrão Recognition (sem customização)
const BRANDING_DEFAULT = {
  product_name: 'Recognition',
  color_primary: '#06b6d4',
  color_secondary: '#ea580c',
  logo_url: null,
  favicon_url: null,
}

// White-label completo do RVB — CORAÇÃO do WS1: superfícies claras preenchidas
const BRANDING_RVB_FULL = {
  product_name: 'RVB Safety Vision',
  color_primary: '#16a34a',
  color_secondary: '#f59e0b',
  logo_url: RVB_LOGO,
  favicon_url: null,
  color_bg_base: '#f4f5f7',
  color_bg_surface: '#ffffff',
  color_bg_elevated: '#ffffff',
  color_bg_card: '#eceef1',
  color_text_primary: '#1a1d23',
  color_text_secondary: '#3f4650',
  color_border: '#d4d8de',
}

const BRANDING_HORIZONTE = {
  product_name: 'Horizonte Vision',
  color_primary: '#2563eb',
  color_secondary: '#f59e0b',
  logo_url: null,
  favicon_url: null,
}

const BRANDING_ANDRADE = {
  product_name: 'Andrade Monitor',
  color_primary: '#7c3aed',
  color_secondary: '#f97316',
  logo_url: null,
  favicon_url: null,
}

// ThemeProvider (boot) — tema default, não sobrescreve nada
const BOOT_BRANDING = { branding: null, is_default: true }

const BASE_FIXTURES = {
  '**/api/v1/tenant/branding*': BOOT_BRANDING,
  '**/api/v1/admin/dashboard': DASHBOARD,
}

/* ═══════════════════════════════════════════════════════════════════
 * 1) /admin/branding/tenants — Lista White-label por tenant
 * ═══════════════════════════════════════════════════════════════════ */

const LIST_SLUG = 'admin-branding-tenants'

const LIST_FIXTURES = {
  ...BASE_FIXTURES,
  '**/api/v1/admin/tenants': { tenants: TENANTS },
  '**/api/v1/admin/tenants/t-0001/branding': { branding: BRANDING_RVB_FULL },
  '**/api/v1/admin/tenants/t-0002/branding': { branding: BRANDING_HORIZONTE },
  '**/api/v1/admin/tenants/t-0003/branding': { branding: BRANDING_DEFAULT },
  '**/api/v1/admin/tenants/t-0004/branding': { branding: BRANDING_DEFAULT },
  '**/api/v1/admin/tenants/t-0005/branding': { branding: BRANDING_ANDRADE },
}

test('admin-branding-tenants — default (rico)', async ({ page }) => {
  await setupApp(page, { fixtures: LIST_FIXTURES })
  await gotoAudit(page, '/admin/branding/tenants')
  await page.getByText('Identidade Visual por Tenant').waitFor()
  await page.getByText('RVB Safety Vision').waitFor()
  await settle(page)
  await shootBothThemes(page, LIST_SLUG, 'default', true)
})

test('admin-branding-tenants — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...BASE_FIXTURES, '**/api/v1/admin/tenants': { tenants: [] } },
  })
  await gotoAudit(page, '/admin/branding/tenants')
  await page.getByText('Nenhum tenant encontrado.').waitFor()
  await settle(page)
  await shootBothThemes(page, LIST_SLUG, 'empty', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 2) /admin/branding/tenants/t-0001 — Editor White-Label (WS1)
 * ═══════════════════════════════════════════════════════════════════ */

const EDIT_SLUG = 'admin-branding-editor'
const EDIT_ROUTE = '/admin/branding/tenants/t-0001'

const EDIT_FIXTURES = {
  ...BASE_FIXTURES,
  '**/api/v1/admin/tenants/t-0001': { tenant: TENANTS[0] },
  '**/api/v1/admin/tenants/t-0001/branding': { branding: BRANDING_RVB_FULL },
}

async function gotoEditorRich(page: Page) {
  await setupApp(page, { fixtures: EDIT_FIXTURES })
  await gotoAudit(page, EDIT_ROUTE)
  await page.getByText('Configurações de Marca').waitFor()
  await settle(page)
}

test('admin-branding-editor — default (superfícies preenchidas, seção aberta)', async ({ page }) => {
  await gotoEditorRich(page)
  // Expande "Containers & Superfícies" — mostra os 7 valores customizados do tenant
  await page.getByRole('button', { name: /Containers & Superfícies/ }).click()
  await page.getByText('Fundo base do app').waitFor()
  await settle(page, 400)
  await shootBothThemes(page, EDIT_SLUG, 'default', true)
})

test('admin-branding-editor — seção Superfícies rolada à vista (valores preenchidos)', async ({ page }) => {
  await gotoEditorRich(page)
  await page.getByRole('button', { name: /Containers & Superfícies/ }).click()
  const firstField = page.getByText('Fundo base do app')
  await firstField.waitFor()
  // O conteúdo rola num container interno do AdminLayout — fullPage não o
  // alcança; rola o último campo à vista pra capturar os 7 valores.
  await page.getByRole('button', { name: /Restaurar padrão da seção/ }).scrollIntoViewIfNeeded()
  await settle(page, 400)
  await shootBothThemes(page, EDIT_SLUG, 'tab-superficies')
})

test('admin-branding-editor — empty (branding padrão Recognition)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      ...BASE_FIXTURES,
      '**/api/v1/admin/tenants/t-0001': { tenant: TENANTS[0] },
      '**/api/v1/admin/tenants/t-0001/branding': { branding: BRANDING_DEFAULT },
    },
  })
  await gotoAudit(page, EDIT_ROUTE)
  await page.getByText('Configurações de Marca').waitFor()
  await settle(page)
  await shootBothThemes(page, EDIT_SLUG, 'empty', true)
})

test('admin-branding-editor — preview aplicado na página (Visualizar como tenant)', async ({ page }) => {
  await gotoEditorRich(page)
  await page.getByRole('button', { name: /Visualizar como tenant/ }).click()
  await page.getByText('Visualizando', { exact: true }).waitFor()
  await settle(page, 600)
  // O preview já recolore a página com as superfícies claras do tenant —
  // aplicar a transformação clara por cima distorceria; captura única.
  await shoot(page, EDIT_SLUG, 'dark-preview-tenant', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 3) /admin/branding/default — Tema padrão (read-only)
 * ═══════════════════════════════════════════════════════════════════ */

const DEF_SLUG = 'admin-branding-default'

test('admin-branding-default — default (catálogo estático)', async ({ page }) => {
  await setupApp(page, { fixtures: BASE_FIXTURES })
  await gotoAudit(page, '/admin/branding/default')
  await page.getByText('Tema Padrão Recognition').waitFor()
  await page.getByText('Somente leitura').waitFor()
  await settle(page)
  await shootBothThemes(page, DEF_SLUG, 'default', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 4) /admin/branding/sandbox — Sandbox de paletas
 * ═══════════════════════════════════════════════════════════════════ */

const SBX_SLUG = 'admin-branding-sandbox'

async function gotoSandbox(page: Page) {
  await setupApp(page, { fixtures: BASE_FIXTURES })
  await gotoAudit(page, '/admin/branding/sandbox')
  await page.getByText('Experimente combinações de cores livremente').waitFor()
  await settle(page)
}

test('admin-branding-sandbox — default', async ({ page }) => {
  await gotoSandbox(page)
  await shootBothThemes(page, SBX_SLUG, 'default', true)
})

test('admin-branding-sandbox — preset Verde Industrial aplicado na página', async ({ page }) => {
  await gotoSandbox(page)
  await page.getByRole('button', { name: /Verde Industrial/ }).click()
  await page.getByRole('button', { name: 'Aplicar na página' }).click()
  await page.getByText('Aplicado na página').waitFor()
  await settle(page, 500)
  // Vars do preset já aplicadas via style#recognition-tenant-theme — captura única.
  await shoot(page, SBX_SLUG, 'dark-preset-aplicado', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 5) /design-system — Vitrine dos tokens (FULLPAGE)
 * ═══════════════════════════════════════════════════════════════════ */

const DS_SLUG = 'design-system'

async function gotoDesignSystem(page: Page) {
  await setupApp(page, { fixtures: BASE_FIXTURES })
  await gotoAudit(page, '/design-system')
  await page.getByRole('heading', { name: 'Design System' }).waitFor()
  await page.getByText('Color Tokens').waitFor()
  await settle(page)
}

test('design-system — default (fullpage, vitrine dos tokens)', async ({ page }) => {
  await gotoDesignSystem(page)
  await shootBothThemes(page, DS_SLUG, 'default', true)
})

test('design-system — modal canônico aberto', async ({ page }) => {
  await gotoDesignSystem(page)
  await page.getByRole('button', { name: 'Abrir Modal' }).click()
  await page.getByText('Modal canônico').waitFor()
  await settle(page, 500)
  await shootBothThemes(page, DS_SLUG, 'modal-canonico')
})

test('design-system — AppDrawer canônico aberto', async ({ page }) => {
  await gotoDesignSystem(page)
  await page.getByRole('button', { name: 'Abrir AppDrawer' }).click()
  await page.getByText('AppDrawer canônico').waitFor()
  await settle(page, 500)
  await shootBothThemes(page, DS_SLUG, 'modal-appdrawer')
})
