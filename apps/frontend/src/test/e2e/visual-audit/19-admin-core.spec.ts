/**
 * Auditoria visual — Grupo 19: Admin Core (tier 1, role superadmin).
 *
 * Páginas e endpoints reais consumidos (adminService → api.ts, base /api):
 * - /admin                    → GET /api/v1/admin/dashboard          → AdminDashboard
 * - /admin/tenants            → GET /api/v1/admin/tenants            → { tenants: Tenant[] }
 * - /admin/tenants/:id        → GET /api/v1/admin/tenants/:id        → { tenant: Tenant }
 *                               GET /api/v1/admin/feature-flags/tenant/:id → { flags: Record<string,boolean> }
 *                               GET /api/v1/admin/tenants/:id/plan-history → { history: [...] }
 * - /admin/users              → GET /api/v1/admin/users?…            → { items: AdminUser[], total }
 *
 * O AdminLayout também chama GET /v1/admin/dashboard em toda rota (badges da
 * sidebar) — o fixture DASHBOARD é incluído nos estados ricos pra badges reais.
 *
 * ATENÇÃO fixtures: AdminDashboard NÃO tolera catch-all {} (mrr_estimated
 * .toLocaleString e workers.online quebram) — estado "empty" usa fixture zerado.
 * Tenants/Users idem (data.tenants / data.items undefined) — vazio explícito.
 */
import { test, type Page } from '@playwright/test'
import { setupApp, shootBothThemes, shoot, settle, gotoAudit } from './helpers'

/* ── Helpers de data ────────────────────────────────────────────── */

const minsAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()
const daysAgo = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString()

/* ── Fixtures pt-BR ─────────────────────────────────────────────── */

const DASHBOARD = {
  tenants_active: 8,
  users_total: 164,
  cameras_online: 42,
  alerts_24h: 37,
  training_approvals_pending: 3,
  tickets_open: 5,
  mrr_estimated: 48200,
  workers: { online: 6, fallback: 2, offline: 1 },
  recent_critical_events: [
    { id: 'ev-01', action: 'tenant.suspend',            target_type: 'tenant',  actor_role: 'superadmin', actor_email: 'vitor@logikos.com.br',   tenant_name: 'Agroindústria Vale Verde',        created_at: minsAgo(35) },
    { id: 'ev-02', action: 'user.force_password_reset', target_type: 'user',    actor_role: 'superadmin', actor_email: 'vitor@logikos.com.br',   tenant_name: 'Tenant RVB Industrial',           created_at: minsAgo(140) },
    { id: 'ev-03', action: 'version.rollback',          target_type: 'version', actor_role: 'superadmin', actor_email: 'suporte@logikos.com.br', tenant_name: 'Construtora Horizonte Sul',       created_at: minsAgo(300) },
    { id: 'ev-04', action: 'auth.login_failed_burst',   target_type: 'user',    actor_role: 'system',                                            tenant_name: 'Metalúrgica São Carlos',          created_at: minsAgo(410) },
    { id: 'ev-05', action: 'tenant.plan_change',        target_type: 'tenant',  actor_role: 'superadmin', actor_email: 'vitor@logikos.com.br',   tenant_name: 'Transportadora Andrade & Filhos', created_at: minsAgo(980) },
  ],
  top_tenants_users: [
    { tenant_name: 'Tenant RVB Industrial',           user_count: 32 },
    { tenant_name: 'Construtora Horizonte Sul',       user_count: 18 },
    { tenant_name: 'Transportadora Andrade & Filhos', user_count: 12 },
    { tenant_name: 'Metalúrgica São Carlos',          user_count: 9 },
    { tenant_name: 'Agroindústria Vale Verde',        user_count: 4 },
  ],
}

const DASHBOARD_EMPTY = {
  tenants_active: 0,
  users_total: 0,
  cameras_online: 0,
  alerts_24h: 0,
  training_approvals_pending: 0,
  tickets_open: 0,
  mrr_estimated: 0,
  workers: { online: 0, fallback: 0, offline: 0 },
  recent_critical_events: [],
  top_tenants_users: [],
}

const TENANTS = [
  {
    id: 't-0001', slug: 'rvb-industrial', name: 'Tenant RVB Industrial', plan: 'enterprise',
    schema_name: 'tenant_rvb', modules_enabled: ['epi', 'quality', 'analytics'], is_active: true,
    requires_training_approval: true, mrr_per_camera: {}, contract_cameras: 12,
    user_count: 32, worker_status: 'onpremise', created_at: daysAgo(236),
  },
  {
    id: 't-0002', slug: 'horizonte-sul', name: 'Construtora Horizonte Sul', plan: 'premium',
    schema_name: 'tenant_horizonte', modules_enabled: ['epi', 'basic'], is_active: true,
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
    schema_name: 'tenant_valeverde', modules_enabled: ['basic'], is_active: false,
    suspended_at: daysAgo(6), requires_training_approval: false, mrr_per_camera: {},
    contract_cameras: 2, user_count: 4, created_at: daysAgo(90),
  },
  {
    id: 't-0005', slug: 'transportadora-andrade', name: 'Transportadora Andrade & Filhos', plan: 'standard',
    schema_name: 'tenant_andrade', modules_enabled: ['epi', 'counting'], is_active: true,
    requires_training_approval: false, mrr_per_camera: {}, contract_cameras: 6,
    user_count: 12, worker_status: 'railway', created_at: daysAgo(45),
  },
]

const TENANT_USERS = [
  { id: 'u-101', email: 'joana.melo@rvb.ind.br',      role: 'admin',    tenant_id: 't-0001', is_active: true,  last_login_at: minsAgo(42),   login_count: 318, force_password_reset: false, created_at: daysAgo(230) },
  { id: 'u-102', email: 'carlos.tavares@rvb.ind.br',  role: 'operator', tenant_id: 't-0001', is_active: true,  last_login_at: minsAgo(190),  login_count: 512, force_password_reset: false, created_at: daysAgo(228) },
  { id: 'u-103', email: 'ana.beatriz@rvb.ind.br',     role: 'analyst',  tenant_id: 't-0001', is_active: true,  last_login_at: daysAgo(1),    login_count: 96,  force_password_reset: false, created_at: daysAgo(150) },
  { id: 'u-104', email: 'ricardo.nunes@rvb.ind.br',   role: 'trainer',  tenant_id: 't-0001', is_active: true,  last_login_at: daysAgo(4),    login_count: 44,  force_password_reset: false, created_at: daysAgo(110) },
  { id: 'u-105', email: 'estagiario.seg@rvb.ind.br',  role: 'viewer',   tenant_id: 't-0001', is_active: false, last_login_at: daysAgo(31),   login_count: 12,  force_password_reset: true,  created_at: daysAgo(88) },
]

const TENANT_DETAIL = {
  ...TENANTS[0],
  internal_notes: 'Contrato renovado em maio/2026 — POC de contagem agendada para agosto.',
  video_retention_days: 30,
  worker_metrics: {
    gpu_pct: 62.4,
    vram_used_gb: 9.8,
    fps_avg: 24.6,
    cameras_active: 11,
    timestamp: minsAgo(1),
    hostname: 'rvb-edge-01',
  },
  users: TENANT_USERS,
}

const TENANT_DETAIL_EMPTY = {
  id: 't-0001', slug: 'novo-cadastro', name: 'Tenant Novo Cadastro', plan: 'basic',
  schema_name: 'tenant_novo', modules_enabled: [], is_active: true,
  requires_training_approval: false, mrr_per_camera: {}, contract_cameras: 0,
  users: [], created_at: minsAgo(20),
}

const TENANT_FLAGS = {
  'epi.live_view_substream': true,
  'epi.alert_webhooks': true,
  'reports.auto_export_pdf': false,
  'training.auto_approve': false,
  'quality.pre_annotation_dino': true,
}

const PLAN_HISTORY = [
  { created_at: daysAgo(12),  old_plan: 'premium',  new_plan: 'enterprise', changed_by_email: 'vitor@logikos.com.br' },
  { created_at: daysAgo(120), old_plan: 'standard', new_plan: 'premium',    changed_by_email: 'vitor@logikos.com.br' },
  { created_at: daysAgo(236), old_plan: null,       new_plan: 'standard',   changed_by_email: 'suporte@logikos.com.br' },
]

const ADMIN_USERS = [
  { id: 'u-101', email: 'joana.melo@rvb.ind.br',           role: 'admin',    tenant_id: 't-0001', tenant_name: 'Tenant RVB Industrial',           is_active: true,  last_login_at: minsAgo(42),  login_count: 318, force_password_reset: false, created_at: daysAgo(230) },
  { id: 'u-201', email: 'pedro.assis@horizontesul.com.br', role: 'admin',    tenant_id: 't-0002', tenant_name: 'Construtora Horizonte Sul',       is_active: true,  last_login_at: minsAgo(300), login_count: 205, force_password_reset: false, created_at: daysAgo(178) },
  { id: 'u-102', email: 'carlos.tavares@rvb.ind.br',       role: 'operator', tenant_id: 't-0001', tenant_name: 'Tenant RVB Industrial',           is_active: true,  last_login_at: minsAgo(190), login_count: 512, force_password_reset: false, created_at: daysAgo(228) },
  { id: 'u-301', email: 'seguranca@msc.ind.br',            role: 'operator', tenant_id: 't-0003', tenant_name: 'Metalúrgica São Carlos',          is_active: true,  last_login_at: daysAgo(2),   login_count: 154, force_password_reset: false, created_at: daysAgo(119) },
  { id: 'u-103', email: 'ana.beatriz@rvb.ind.br',          role: 'analyst',  tenant_id: 't-0001', tenant_name: 'Tenant RVB Industrial',           is_active: true,  last_login_at: daysAgo(1),   login_count: 96,  force_password_reset: false, created_at: daysAgo(150) },
  { id: 'u-501', email: 'frota@andradefilhos.com.br',      role: 'trainer',  tenant_id: 't-0005', tenant_name: 'Transportadora Andrade & Filhos', is_active: true,  last_login_at: daysAgo(7),   login_count: 33,  force_password_reset: false, created_at: daysAgo(44) },
  { id: 'u-401', email: 'gestor@valeverde.agr.br',         role: 'viewer',   tenant_id: 't-0004', tenant_name: 'Agroindústria Vale Verde',        is_active: false, last_login_at: daysAgo(30),  login_count: 8,   force_password_reset: true,  created_at: daysAgo(89) },
]

const ERROR_500 = {
  status: 500,
  body: { status: 'error', error: 'Erro interno do servidor' },
}

/* ═══════════════════════════════════════════════════════════════════
 * 1) /admin — Dashboard Admin
 * ═══════════════════════════════════════════════════════════════════ */

const DASH_SLUG = 'admin-dashboard'

async function gotoDashboardRich(page: Page) {
  await setupApp(page, { fixtures: { '**/api/v1/admin/dashboard': DASHBOARD } })
  await gotoAudit(page, '/admin')
  await page.getByText('Dashboard Admin').waitFor()
  await settle(page)
}

test('admin-dashboard — default (rico) + hover Ver workers', async ({ page }) => {
  await gotoDashboardRich(page)
  // hover (só dark) antes da transformação clara irreversível
  await page.getByRole('button', { name: /Ver workers/ }).hover()
  await page.waitForTimeout(250)
  await shoot(page, DASH_SLUG, 'dark-hover-ver-workers')
  await page.mouse.move(10, 10)
  await page.waitForTimeout(250)
  await shootBothThemes(page, DASH_SLUG, 'default', true)
})

test('admin-dashboard — empty (zerado)', async ({ page }) => {
  await setupApp(page, { fixtures: { '**/api/v1/admin/dashboard': DASHBOARD_EMPTY } })
  await gotoAudit(page, '/admin')
  await page.getByText('Dashboard Admin').waitFor()
  await settle(page)
  await shootBothThemes(page, DASH_SLUG, 'empty', true)
})

test('admin-dashboard — loading (stall)', async ({ page }) => {
  await setupApp(page, { stall: ['**/api/v1/admin/dashboard'] })
  await gotoAudit(page, '/admin')
  await page.getByText('Logikos · Recognition').waitFor()
  await page.waitForTimeout(1500) // deixa o chunk lazy montar os skeletons
  await shootBothThemes(page, DASH_SLUG, 'loading', true)
})

test('admin-dashboard — error (500)', async ({ page }) => {
  await setupApp(page, { raw: { '**/api/v1/admin/dashboard': ERROR_500 } })
  await gotoAudit(page, '/admin')
  await page.getByText('Erro interno do servidor').first().waitFor()
  await page.waitForTimeout(1200) // deixa toast de erro aparecer
  await shootBothThemes(page, DASH_SLUG, 'error', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 2) /admin/tenants — Lista de tenants
 * ═══════════════════════════════════════════════════════════════════ */

const TEN_SLUG = 'admin-tenants'

const TENANTS_FIXTURES = {
  '**/api/v1/admin/dashboard': DASHBOARD,
  '**/api/v1/admin/tenants': { tenants: TENANTS },
}

async function gotoTenantsRich(page: Page) {
  await setupApp(page, { fixtures: TENANTS_FIXTURES })
  await gotoAudit(page, '/admin/tenants')
  await page.getByText(/clientes cadastrados/).waitFor()
  await page.getByText('Tenant RVB Industrial').waitFor()
  await settle(page)
}

test('admin-tenants — default (rico) + hover linha', async ({ page }) => {
  await gotoTenantsRich(page)
  await page.getByText('Tenant RVB Industrial').hover()
  await page.waitForTimeout(250)
  await shoot(page, TEN_SLUG, 'dark-hover-row')
  await page.mouse.move(10, 10)
  await page.waitForTimeout(250)
  await shootBothThemes(page, TEN_SLUG, 'default', true)
})

test('admin-tenants — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD, '**/api/v1/admin/tenants': { tenants: [] } },
  })
  await gotoAudit(page, '/admin/tenants')
  await page.getByText('Nenhum tenant encontrado').waitFor()
  await settle(page)
  await shootBothThemes(page, TEN_SLUG, 'empty', true)
})

test('admin-tenants — loading (stall)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    stall: ['**/api/v1/admin/tenants'],
  })
  await gotoAudit(page, '/admin/tenants')
  await page.getByRole('button', { name: 'Novo Tenant' }).waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, TEN_SLUG, 'loading', true)
})

test('admin-tenants — error (500)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    raw: { '**/api/v1/admin/tenants': ERROR_500 },
  })
  await gotoAudit(page, '/admin/tenants')
  await page.getByText('Erro interno do servidor').first().waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, TEN_SLUG, 'error', true)
})

test('admin-tenants — modal Novo Tenant', async ({ page }) => {
  await gotoTenantsRich(page)
  await page.getByRole('button', { name: 'Novo Tenant' }).click()
  await page.getByText('Nome da empresa').waitFor()
  // preenche pra retratar o modal em uso real
  await page.getByText('Nome da empresa').locator('..').locator('input').fill('Frigorífico Boa Vista')
  await page.getByText('Slug (ex: empresa-abc)').locator('..').locator('input').fill('frigorifico-boa-vista')
  await settle(page, 400)
  await shootBothThemes(page, TEN_SLUG, 'modal-novo-tenant')
})

/* ═══════════════════════════════════════════════════════════════════
 * 3) /admin/tenants/t-0001 — Detalhe do tenant (tabs)
 * ═══════════════════════════════════════════════════════════════════ */

const DET_SLUG = 'admin-tenant-detail'
const DET_ROUTE = '/admin/tenants/t-0001'

const DETAIL_FIXTURES = {
  '**/api/v1/admin/dashboard': DASHBOARD,
  '**/api/v1/admin/tenants/t-0001': { tenant: TENANT_DETAIL },
  '**/api/v1/admin/tenants/t-0001/plan-history': { history: PLAN_HISTORY },
  '**/api/v1/admin/feature-flags/tenant/**': { flags: TENANT_FLAGS },
}

async function gotoDetailRich(page: Page) {
  await setupApp(page, { fixtures: DETAIL_FIXTURES })
  await gotoAudit(page, DET_ROUTE)
  await page.getByText('Informações').waitFor()
  await settle(page)
}

test('admin-tenant-detail — default (overview rico) + hover Suspender', async ({ page }) => {
  await gotoDetailRich(page)
  await page.getByRole('button', { name: /Suspender/ }).hover()
  await page.waitForTimeout(250)
  await shoot(page, DET_SLUG, 'dark-hover-suspender')
  await page.mouse.move(10, 10)
  await page.waitForTimeout(250)
  await shootBothThemes(page, DET_SLUG, 'default', true)
})

test('admin-tenant-detail — empty (tenant recém-criado)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/admin/dashboard': DASHBOARD,
      '**/api/v1/admin/tenants/t-0001': { tenant: TENANT_DETAIL_EMPTY },
    },
  })
  await gotoAudit(page, DET_ROUTE)
  await page.getByText('Informações').waitFor()
  await settle(page)
  await shootBothThemes(page, DET_SLUG, 'empty', true)
})

test('admin-tenant-detail — loading (stall)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    stall: ['**/api/v1/admin/tenants/t-0001'],
  })
  await gotoAudit(page, DET_ROUTE)
  await page.getByText('Logikos · Recognition').waitFor()
  await page.waitForTimeout(1500)
  await shootBothThemes(page, DET_SLUG, 'loading', true)
})

test('admin-tenant-detail — error (500)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    raw: { '**/api/v1/admin/tenants/t-0001': ERROR_500 },
  })
  await gotoAudit(page, DET_ROUTE)
  await page.getByText('Erro interno do servidor').first().waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, DET_SLUG, 'error', true)
})

test('admin-tenant-detail — tab Usuários', async ({ page }) => {
  await gotoDetailRich(page)
  await page.getByRole('button', { name: 'Usuários', exact: true }).click()
  await page.getByText('Usuários do tenant').waitFor()
  await settle(page, 400)
  await shootBothThemes(page, DET_SLUG, 'tab-users', true)
})

test('admin-tenant-detail — tab Usuários + form Adicionar usuário', async ({ page }) => {
  await gotoDetailRich(page)
  await page.getByRole('button', { name: 'Usuários', exact: true }).click()
  await page.getByText('Usuários do tenant').waitFor()
  await page.getByRole('button', { name: /Adicionar usuário/ }).click()
  await page.getByPlaceholder('email@empresa.com').waitFor()
  await page.getByPlaceholder('email@empresa.com').fill('novo.operador@rvb.ind.br')
  await settle(page, 400)
  await shootBothThemes(page, DET_SLUG, 'modal-add-user', true)
})

test('admin-tenant-detail — tab Worker', async ({ page }) => {
  await gotoDetailRich(page)
  await page.getByRole('button', { name: 'Worker', exact: true }).click()
  await page.getByText('Worker On-Premise').waitFor()
  await settle(page, 400)
  await shootBothThemes(page, DET_SLUG, 'tab-worker')
})

test('admin-tenant-detail — tab Módulos', async ({ page }) => {
  await gotoDetailRich(page)
  await page.getByRole('button', { name: 'Módulos', exact: true }).click()
  await page.getByText('Módulos disponíveis').waitFor()
  await settle(page, 400)
  await shootBothThemes(page, DET_SLUG, 'tab-modules', true)
})

test('admin-tenant-detail — tab Feature Flags', async ({ page }) => {
  await gotoDetailRich(page)
  await page.getByRole('button', { name: 'Feature Flags', exact: true }).click()
  await page.getByText('epi.live_view_substream').waitFor()
  await settle(page, 400)
  await shootBothThemes(page, DET_SLUG, 'tab-flags')
})

test('admin-tenant-detail — tab Histórico de Plano', async ({ page }) => {
  await gotoDetailRich(page)
  await page.getByRole('button', { name: 'Histórico de Plano', exact: true }).click()
  await page.getByText('Data', { exact: true }).waitFor()
  await settle(page, 400)
  await shootBothThemes(page, DET_SLUG, 'tab-history')
})

/* ═══════════════════════════════════════════════════════════════════
 * 4) /admin/users — Usuários da plataforma
 * ═══════════════════════════════════════════════════════════════════ */

const USR_SLUG = 'admin-users'

const USERS_FIXTURES = {
  '**/api/v1/admin/dashboard': DASHBOARD,
  '**/api/v1/admin/users*': { items: ADMIN_USERS, total: ADMIN_USERS.length },
}

async function gotoUsersRich(page: Page) {
  await setupApp(page, { fixtures: USERS_FIXTURES })
  await gotoAudit(page, '/admin/users')
  await page.getByText(/usuários cadastrados/).waitFor()
  await page.getByText('joana.melo@rvb.ind.br').waitFor()
  await settle(page)
}

test('admin-users — default (rico) + hover linha', async ({ page }) => {
  await gotoUsersRich(page)
  await page.getByText('joana.melo@rvb.ind.br').hover()
  await page.waitForTimeout(250)
  await shoot(page, USR_SLUG, 'dark-hover-row')
  await page.mouse.move(10, 10)
  await page.waitForTimeout(250)
  await shootBothThemes(page, USR_SLUG, 'default', true)
})

test('admin-users — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/admin/dashboard': DASHBOARD,
      '**/api/v1/admin/users*': { items: [], total: 0 },
    },
  })
  await gotoAudit(page, '/admin/users')
  await page.getByText('Nenhum usuário encontrado').waitFor()
  await settle(page)
  await shootBothThemes(page, USR_SLUG, 'empty', true)
})

test('admin-users — loading (stall)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    stall: ['**/api/v1/admin/users*'],
  })
  await gotoAudit(page, '/admin/users')
  await page.getByRole('button', { name: 'Novo Usuário' }).waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, USR_SLUG, 'loading', true)
})

test('admin-users — error (500)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    raw: { '**/api/v1/admin/users*': ERROR_500 },
  })
  await gotoAudit(page, '/admin/users')
  await page.getByText('Erro interno do servidor').first().waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, USR_SLUG, 'error', true)
})

test('admin-users — modal Novo Usuário', async ({ page }) => {
  await gotoUsersRich(page)
  await page.getByRole('button', { name: 'Novo Usuário' }).click()
  await page.getByText('Tenant ID').waitFor()
  await page.getByText('Email', { exact: true }).locator('..').locator('input').fill('novo.usuario@horizontesul.com.br')
  await page.getByPlaceholder('UUID do tenant').fill('t-0002')
  await settle(page, 400)
  await shootBothThemes(page, USR_SLUG, 'modal-novo-usuario')
})
