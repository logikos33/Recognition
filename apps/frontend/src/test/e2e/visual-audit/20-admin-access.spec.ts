/**
 * Auditoria visual — grupo 20-admin-access (tier 1).
 *
 * Páginas (todas sob AdminLayout, guard superadmin):
 *   /admin/roles          — AdminRolesPage: tabela de roles customizadas + modal
 *                           criar/editar com checkboxes por PERMISSION_GROUPS.
 *   /admin/plans          — AdminPlansPage: grid de cards de planos + modal editar/criar.
 *   /admin/integrations   — AdminIntegrationsPage (task-058): 4 cards fixos
 *                           (R2, Vast.ai, GPU genérico, Notificações), secrets
 *                           mascarados ••••XXXX, botão Testar conexão.
 *   /admin/settings       — AdminSettingsPage: matriz de permissões (roles × perms).
 *   /admin/feature-flags  — AdminFeatureFlagsPage: tabela de flags globais + toggle.
 *
 * Endpoints reais consumidos:
 *   GET   /api/admin/roles[?tenant_id]          → { roles: CustomRole[], total }   (SEM /v1!)
 *   GET   /api/v1/admin/plans                   → { plans: Plan[] }
 *   GET   /api/v1/admin/integrations/           → { integrations: Integration[] }  (trailing slash)
 *   POST  /api/v1/admin/integrations/:type/test → { ok, error }
 *   GET   /api/v1/admin/permissions/matrix      → { matrix: {perm: role[]} }
 *   GET   /api/v1/admin/feature-flags           → { flags: FeatureFlag[] }
 *   PATCH /api/v1/admin/feature-flags/:key      → { updated }
 *   GET   /api/v1/admin/dashboard               → badges do AdminLayout (sidebar)
 *
 * Candidatos a defeito conhecidos (registrar nos screenshots):
 *   - Roles/Plans: overlay de modal caseiro (TODO-WS1 no source) — validar
 *     fundo opaco + legibilidade sob superfície clara (classe task-066).
 *   - Badges com rgba(...) hardcoded (task-063/065) em roles e plans.
 */
import { test, type Page } from '@playwright/test'
import { setupApp, shootBothThemes, shoot, settle, gotoAudit } from './helpers'

/* ------------------------------------------------------------------ */
/* Fixtures compartilhadas — Tenant RVB Industrial                     */
/* ------------------------------------------------------------------ */

/** Badges da sidebar do AdminLayout (evita `undefined` nos contadores). */
const LAYOUT_FIXTURES: Record<string, unknown> = {
  '**/api/v1/admin/dashboard': { training_approvals_pending: 3, tickets_open: 2 },
}

// ── Roles ─────────────────────────────────────────────────────────────

const perms = (keys: string[]): Record<string, boolean> =>
  Object.fromEntries(keys.map((k) => [k, true]))

const ROLES_FIXTURE = {
  roles: [
    {
      id: 'role-1',
      tenant_id: '00000000-0000-0000-0000-000000000001',
      name: 'Supervisor de Segurança',
      permissions: perms([
        'cameras:read', 'alerts:read', 'alerts:export',
        'reports:read', 'reports:export', 'training:approve',
      ]),
      user_count: 4,
      created_at: '2026-03-14T12:00:00Z',
      updated_at: '2026-06-02T09:30:00Z',
    },
    {
      id: 'role-2',
      tenant_id: '00000000-0000-0000-0000-000000000001',
      name: 'Operador de Câmeras',
      permissions: perms(['cameras:read', 'cameras:write', 'alerts:read']),
      user_count: 7,
      created_at: '2026-02-01T15:20:00Z',
      updated_at: '2026-02-01T15:20:00Z',
    },
    {
      id: 'role-3',
      tenant_id: '00000000-0000-0000-0000-000000000001',
      name: 'Analista de Alertas',
      permissions: perms(['alerts:read', 'alerts:export', 'reports:read']),
      user_count: 3,
      created_at: '2026-04-22T10:05:00Z',
      updated_at: '2026-05-10T18:44:00Z',
    },
    {
      id: 'role-4',
      tenant_id: '00000000-0000-0000-0000-000000000001',
      name: 'Gestor de Treinamento',
      permissions: perms(['training:read', 'training:write', 'training:approve']),
      user_count: 2,
      created_at: '2026-05-05T08:12:00Z',
      updated_at: '2026-05-05T08:12:00Z',
    },
    {
      id: 'role-5',
      tenant_id: '00000000-0000-0000-0000-000000000001',
      name: 'Auditor Externo',
      permissions: perms(['reports:read']),
      user_count: 0,
      created_at: '2026-06-18T14:00:00Z',
      updated_at: '2026-06-18T14:00:00Z',
    },
    {
      id: 'role-6',
      tenant_id: '00000000-0000-0000-0000-000000000001',
      name: 'Recepção Portaria',
      permissions: {},
      user_count: 0,
      created_at: '2026-06-30T11:47:00Z',
      updated_at: '2026-06-30T11:47:00Z',
    },
  ],
  total: 6,
}

const ROLES_FIXTURES: Record<string, unknown> = {
  ...LAYOUT_FIXTURES,
  '**/api/admin/roles*': ROLES_FIXTURE,
}

// ── Plans ─────────────────────────────────────────────────────────────

const PLANS_FIXTURE = {
  plans: [
    {
      id: 'plan-1', slug: 'basic', name: 'Essencial',
      modules_allowed: ['epi'],
      max_cameras: 5, video_retention_days: 15,
      requires_training_approval: false,
      price_per_camera: { brl: 79.9 }, active: true,
    },
    {
      id: 'plan-2', slug: 'standard', name: 'Profissional',
      modules_allowed: ['epi', 'fueling'],
      max_cameras: 12, video_retention_days: 30,
      requires_training_approval: false,
      price_per_camera: { brl: 129.9 }, active: true,
    },
    {
      id: 'plan-3', slug: 'premium', name: 'Avançado',
      modules_allowed: ['epi', 'fueling', 'quality'],
      max_cameras: 24, video_retention_days: 60,
      requires_training_approval: true,
      price_per_camera: { brl: 189.9 }, active: true,
    },
    {
      id: 'plan-4', slug: 'enterprise', name: 'Corporativo RVB',
      modules_allowed: ['epi', 'fueling', 'quality'],
      max_cameras: 60, video_retention_days: 90,
      requires_training_approval: true,
      price_per_camera: { brl: 249.0 }, active: true,
    },
  ],
}

const PLANS_FIXTURES: Record<string, unknown> = {
  ...LAYOUT_FIXTURES,
  '**/api/v1/admin/plans': PLANS_FIXTURE,
}

// ── Integrations (task-058) ───────────────────────────────────────────

const INTEGRATIONS_FIXTURE = {
  integrations: [
    {
      id: 'int-1', integration_type: 'r2', label: 'R2 Produção RVB',
      config: {
        endpoint: 'https://f8a2c1.r2.cloudflarestorage.com',
        bucket: 'recognition-rvb-prod',
      },
      secret_display: '••••4f2a',
      status: 'ok',
      last_tested_at: '2026-07-05T22:14:00Z',
      last_error: null,
    },
    {
      id: 'int-2', integration_type: 'vast_ai', label: 'Vast.ai Treinos',
      config: { gpu_type: 'RTX_4090' },
      secret_display: '••••9c1e',
      status: 'error',
      last_tested_at: '2026-07-04T03:40:00Z',
      last_error: 'Falha na autenticação: chave de API expirada',
    },
    {
      id: 'int-3', integration_type: 'generic_gpu', label: 'generic_gpu',
      config: {},
      secret_display: null,
      status: 'unconfigured',
      last_tested_at: null,
      last_error: null,
    },
    {
      id: 'int-4', integration_type: 'notification', label: 'Webhook Alertas Slack',
      config: { webhook_url: 'https://hooks.slack.com/services/T0RVB/B44/xyz' },
      secret_display: '••••b7d0',
      status: 'ok',
      last_tested_at: '2026-07-06T08:02:00Z',
      last_error: null,
    },
  ],
}

const INTEGRATIONS_FIXTURES: Record<string, unknown> = {
  ...LAYOUT_FIXTURES,
  '**/api/v1/admin/integrations/': INTEGRATIONS_FIXTURE,
}

// ── Permission matrix (settings) ─────────────────────────────────────

const MATRIX_FIXTURE = {
  matrix: {
    'cameras:read':     ['superadmin', 'admin', 'operator', 'analyst', 'viewer'],
    'cameras:write':    ['superadmin', 'admin', 'operator'],
    'cameras:delete':   ['superadmin', 'admin'],
    'alerts:read':      ['superadmin', 'admin', 'operator', 'analyst', 'trainer', 'viewer'],
    'alerts:export':    ['superadmin', 'admin', 'analyst'],
    'training:read':    ['superadmin', 'admin', 'trainer'],
    'training:write':   ['superadmin', 'trainer'],
    'training:approve': ['superadmin'],
    'reports:read':     ['superadmin', 'admin', 'analyst', 'viewer'],
    'reports:export':   ['superadmin', 'admin', 'analyst'],
    'admin:users':      ['superadmin', 'admin'],
    'admin:roles':      ['superadmin'],
    'admin:settings':   ['superadmin'],
  },
}

const SETTINGS_FIXTURES: Record<string, unknown> = {
  ...LAYOUT_FIXTURES,
  '**/api/v1/admin/permissions/matrix': MATRIX_FIXTURE,
}

// ── Feature flags ─────────────────────────────────────────────────────

const FLAGS_FIXTURE = {
  flags: [
    {
      id: 'ff-1', flag_key: 'platform.maintenance_mode', flag_value: false,
      description: 'Bloqueia login de usuários não-superadmin durante manutenção',
      updated_at: '2026-06-12T10:00:00Z',
    },
    {
      id: 'ff-2', flag_key: 'training.auto_approve', flag_value: false,
      description: 'Aprova jobs de treinamento automaticamente (sem revisão manual)',
      updated_at: '2026-05-28T16:30:00Z',
    },
    {
      id: 'ff-3', flag_key: 'alerts.email_notifications', flag_value: true,
      description: 'Envia e-mail para admins do tenant a cada alerta crítico',
      updated_at: '2026-07-01T09:15:00Z',
    },
    {
      id: 'ff-4', flag_key: 'monitoring.live_substream', flag_value: true,
      description: 'Usa substream RTSP como padrão no live view',
      updated_at: '2026-07-04T21:50:00Z',
    },
    {
      id: 'ff-5', flag_key: 'billing.enforce_camera_limit', flag_value: true,
      description: 'Bloqueia cadastro de câmeras acima do limite do plano',
      updated_at: '2026-04-19T13:05:00Z',
    },
    {
      id: 'ff-6', flag_key: 'branding.white_label', flag_value: true,
      description: 'Habilita personalização de identidade visual por tenant (WS1)',
    },
  ],
}

const FLAGS_FIXTURES: Record<string, unknown> = {
  ...LAYOUT_FIXTURES,
  '**/api/v1/admin/feature-flags': FLAGS_FIXTURE,
}

/* ================================================================== */
/* admin-roles — /admin/roles                                          */
/* ================================================================== */

const ROLES_SCREEN = 'admin-roles'
const ROLES_ROUTE = '/admin/roles'

async function openRoles(page: Page) {
  await gotoAudit(page, ROLES_ROUTE)
  await page.getByText('Supervisor de Segurança').waitFor({ timeout: 30_000 })
  await settle(page)
}

test('admin-roles — default (tabela de roles customizadas)', async ({ page }) => {
  await setupApp(page, { fixtures: ROLES_FIXTURES })
  await openRoles(page)
  await shootBothThemes(page, ROLES_SCREEN, 'default', true)
})

test('admin-roles — empty (nenhuma role)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...LAYOUT_FIXTURES, '**/api/admin/roles*': { roles: [], total: 0 } },
  })
  await gotoAudit(page, ROLES_ROUTE)
  await page.getByText('Nenhuma role customizada').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, ROLES_SCREEN, 'empty')
})

test('admin-roles — loading (GET /admin/roles nunca responde)', async ({ page }) => {
  await setupApp(page, { fixtures: LAYOUT_FIXTURES, stall: ['**/api/admin/roles*'] })
  await gotoAudit(page, ROLES_ROUTE)
  await page.getByText('Carregando...').first().waitFor({ timeout: 30_000 })
  await page.waitForTimeout(2000)
  await shootBothThemes(page, ROLES_SCREEN, 'loading')
})

test('admin-roles — error (GET /admin/roles 500)', async ({ page }) => {
  await setupApp(page, {
    fixtures: LAYOUT_FIXTURES,
    raw: {
      '**/api/admin/roles*': {
        status: 500,
        body: { status: 'error', error: 'Falha ao carregar roles do tenant' },
      },
    },
  })
  await gotoAudit(page, ROLES_ROUTE)
  await page.getByText('Falha ao carregar roles do tenant').first().waitFor({ timeout: 30_000 })
  await page.waitForTimeout(800)
  await shootBothThemes(page, ROLES_SCREEN, 'error')
})

test('admin-roles — modal-nova-role (checkboxes por área funcional)', async ({ page }) => {
  await setupApp(page, { fixtures: ROLES_FIXTURES })
  await openRoles(page)
  await page.getByRole('button', { name: 'Nova Role' }).click()
  await page.getByText('Nome da role').waitFor({ timeout: 10_000 })
  await settle(page, 500)
  await shootBothThemes(page, ROLES_SCREEN, 'modal-nova-role')
})

test('admin-roles — modal-editar-role (permissões pré-selecionadas)', async ({ page }) => {
  await setupApp(page, { fixtures: ROLES_FIXTURES })
  await openRoles(page)
  await page.getByTitle('Editar').first().click()
  await page.getByText('Editar Role').waitFor({ timeout: 10_000 })
  await settle(page, 500)
  await shootBothThemes(page, ROLES_SCREEN, 'modal-editar-role')
})

test('admin-roles — hover (botão Nova Role + ação Editar)', async ({ page }) => {
  await setupApp(page, { fixtures: ROLES_FIXTURES })
  await openRoles(page)

  await page.getByRole('button', { name: 'Nova Role' }).hover()
  await page.waitForTimeout(300)
  await shoot(page, ROLES_SCREEN, 'dark-hover-nova-role')

  await page.getByTitle('Editar').first().hover()
  await page.waitForTimeout(300)
  await shoot(page, ROLES_SCREEN, 'dark-hover-editar')
})

/* ================================================================== */
/* admin-plans — /admin/plans                                          */
/* ================================================================== */

const PLANS_SCREEN = 'admin-plans'
const PLANS_ROUTE = '/admin/plans'

async function openPlans(page: Page) {
  await gotoAudit(page, PLANS_ROUTE)
  await page.getByText('Corporativo RVB').waitFor({ timeout: 30_000 })
  await settle(page)
}

test('admin-plans — default (grid de planos com badges por slug)', async ({ page }) => {
  await setupApp(page, { fixtures: PLANS_FIXTURES })
  await openPlans(page)
  await shootBothThemes(page, PLANS_SCREEN, 'default', true)
})

test('admin-plans — empty (nenhum plano)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...LAYOUT_FIXTURES, '**/api/v1/admin/plans': { plans: [] } },
  })
  await gotoAudit(page, PLANS_ROUTE)
  await page.getByText('0 planos cadastrados').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, PLANS_SCREEN, 'empty')
})

test('admin-plans — loading (GET /plans nunca responde)', async ({ page }) => {
  await setupApp(page, { fixtures: LAYOUT_FIXTURES, stall: ['**/api/v1/admin/plans'] })
  await gotoAudit(page, PLANS_ROUTE)
  await page.getByText('Carregando...').first().waitFor({ timeout: 30_000 })
  await page.waitForTimeout(2000)
  await shootBothThemes(page, PLANS_SCREEN, 'loading')
})

test('admin-plans — error (GET /plans 500)', async ({ page }) => {
  await setupApp(page, {
    fixtures: LAYOUT_FIXTURES,
    raw: {
      '**/api/v1/admin/plans': {
        status: 500,
        body: { status: 'error', error: 'Falha ao carregar planos' },
      },
    },
  })
  await gotoAudit(page, PLANS_ROUTE)
  await page.getByText('Falha ao carregar planos').first().waitFor({ timeout: 30_000 })
  await page.waitForTimeout(800)
  await shootBothThemes(page, PLANS_SCREEN, 'error')
})

test('admin-plans — modal-novo-plano', async ({ page }) => {
  await setupApp(page, { fixtures: PLANS_FIXTURES })
  await openPlans(page)
  await page.getByRole('button', { name: 'Novo Plano' }).click()
  await page.getByText('Módulos permitidos').waitFor({ timeout: 10_000 })
  await settle(page, 500)
  await shootBothThemes(page, PLANS_SCREEN, 'modal-novo-plano')
})

test('admin-plans — modal-editar-plano (card clicável)', async ({ page }) => {
  await setupApp(page, { fixtures: PLANS_FIXTURES })
  await openPlans(page)
  await page.getByText('Corporativo RVB').first().click()
  await page.getByText('Editar Plano').waitFor({ timeout: 10_000 })
  await settle(page, 500)
  await shootBothThemes(page, PLANS_SCREEN, 'modal-editar-plano')
})

test('admin-plans — hover (card de plano + botão Novo Plano)', async ({ page }) => {
  await setupApp(page, { fixtures: PLANS_FIXTURES })
  await openPlans(page)

  await page.getByText('Profissional').first().hover()
  await page.waitForTimeout(300)
  await shoot(page, PLANS_SCREEN, 'dark-hover-card')

  await page.getByRole('button', { name: 'Novo Plano' }).hover()
  await page.waitForTimeout(300)
  await shoot(page, PLANS_SCREEN, 'dark-hover-novo-plano')
})

/* ================================================================== */
/* admin-integrations — /admin/integrations (task-058)                 */
/* ================================================================== */

const INTEG_SCREEN = 'admin-integrations'
const INTEG_ROUTE = '/admin/integrations'

async function openIntegrations(page: Page) {
  await gotoAudit(page, INTEG_ROUTE)
  await page.getByText('Cloudflare R2').waitFor({ timeout: 30_000 })
  await settle(page)
}

test('admin-integrations — default (cards com secrets mascarados)', async ({ page }) => {
  await setupApp(page, { fixtures: INTEGRATIONS_FIXTURES })
  await openIntegrations(page)
  // secret mascarado visível (task-058: nunca plaintext no DOM)
  await page.getByText('••••4f2a').waitFor({ timeout: 10_000 })
  await shootBothThemes(page, INTEG_SCREEN, 'default', true)
})

test('admin-integrations — empty (nada configurado)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...LAYOUT_FIXTURES, '**/api/v1/admin/integrations/': { integrations: [] } },
  })
  await gotoAudit(page, INTEG_ROUTE)
  await page.getByText('Não configurado').first().waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, INTEG_SCREEN, 'empty', true)
})

test('admin-integrations — loading (GET /integrations nunca responde)', async ({ page }) => {
  await setupApp(page, {
    fixtures: LAYOUT_FIXTURES,
    stall: ['**/api/v1/admin/integrations/'],
  })
  await gotoAudit(page, INTEG_ROUTE)
  await page.getByText('Carregando integrações').waitFor({ timeout: 30_000 })
  await page.waitForTimeout(2000)
  await shootBothThemes(page, INTEG_SCREEN, 'loading')
})

test('admin-integrations — error (GET /integrations 500)', async ({ page }) => {
  await setupApp(page, {
    fixtures: LAYOUT_FIXTURES,
    raw: {
      '**/api/v1/admin/integrations/': {
        status: 500,
        body: { status: 'error', error: 'Serviço de integrações indisponível' },
      },
    },
  })
  await gotoAudit(page, INTEG_ROUTE)
  await page.getByText('Serviço de integrações indisponível').waitFor({ timeout: 30_000 })
  await page.waitForTimeout(800)
  await shootBothThemes(page, INTEG_SCREEN, 'error')
})

test('admin-integrations — testing (POST /test pendurado → "Testando...")', async ({ page }) => {
  await setupApp(page, {
    fixtures: INTEGRATIONS_FIXTURES,
    stall: ['**/api/v1/admin/integrations/*/test'],
  })
  await openIntegrations(page)
  await page.getByRole('button', { name: 'Testar conexão' }).first().click()
  await page.getByText('Testando...').waitFor({ timeout: 10_000 })
  await page.waitForTimeout(400)
  await shootBothThemes(page, INTEG_SCREEN, 'testing')
})

test('admin-integrations — hover (Salvar + Testar conexão)', async ({ page }) => {
  await setupApp(page, { fixtures: INTEGRATIONS_FIXTURES })
  await openIntegrations(page)

  await page.getByRole('button', { name: 'Salvar', exact: true }).first().hover()
  await page.waitForTimeout(300)
  await shoot(page, INTEG_SCREEN, 'dark-hover-salvar')

  await page.getByRole('button', { name: 'Testar conexão' }).first().hover()
  await page.waitForTimeout(300)
  await shoot(page, INTEG_SCREEN, 'dark-hover-testar')
})

/* ================================================================== */
/* admin-settings — /admin/settings                                    */
/* ================================================================== */

const SETTINGS_SCREEN = 'admin-settings'
const SETTINGS_ROUTE = '/admin/settings'

test('admin-settings — default (matriz de permissões roles × perms)', async ({ page }) => {
  await setupApp(page, { fixtures: SETTINGS_FIXTURES })
  await gotoAudit(page, SETTINGS_ROUTE)
  await page.getByText('Matriz de Permissões').waitFor({ timeout: 30_000 })
  await page.getByText('training:approve').waitFor({ timeout: 15_000 })
  await settle(page)
  await shootBothThemes(page, SETTINGS_SCREEN, 'default', true)
})

test('admin-settings — empty (matriz indisponível → banner warning)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...LAYOUT_FIXTURES, '**/api/v1/admin/permissions/matrix': { matrix: null } },
  })
  await gotoAudit(page, SETTINGS_ROUTE)
  await page
    .getByText('Não foi possível carregar a matriz de permissões')
    .waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, SETTINGS_SCREEN, 'empty')
})

test('admin-settings — loading (GET /permissions/matrix nunca responde)', async ({ page }) => {
  await setupApp(page, {
    fixtures: LAYOUT_FIXTURES,
    stall: ['**/api/v1/admin/permissions/matrix'],
  })
  await gotoAudit(page, SETTINGS_ROUTE)
  await page.getByText('Carregando...').first().waitFor({ timeout: 30_000 })
  await page.waitForTimeout(2000)
  await shootBothThemes(page, SETTINGS_SCREEN, 'loading')
})

test('admin-settings — error (GET /permissions/matrix 500 → warning silencioso)', async ({ page }) => {
  // usePermissions engole o erro (catch vazio) → mesmo banner do estado vazio.
  await setupApp(page, {
    fixtures: LAYOUT_FIXTURES,
    raw: {
      '**/api/v1/admin/permissions/matrix': {
        status: 500,
        body: { status: 'error', error: 'Falha ao montar matriz' },
      },
    },
  })
  await gotoAudit(page, SETTINGS_ROUTE)
  await page
    .getByText('Não foi possível carregar a matriz de permissões')
    .waitFor({ timeout: 30_000 })
  await page.waitForTimeout(800)
  await shootBothThemes(page, SETTINGS_SCREEN, 'error')
})

test('admin-settings — hover (linha da matriz)', async ({ page }) => {
  await setupApp(page, { fixtures: SETTINGS_FIXTURES })
  await gotoAudit(page, SETTINGS_ROUTE)
  await page.getByText('cameras:write').waitFor({ timeout: 30_000 })
  await settle(page)
  await page.getByText('cameras:write').hover()
  await page.waitForTimeout(300)
  await shoot(page, SETTINGS_SCREEN, 'dark-hover-matrix-row')
})

/* ================================================================== */
/* admin-feature-flags — /admin/feature-flags                          */
/* ================================================================== */

const FLAGS_SCREEN = 'admin-feature-flags'
const FLAGS_ROUTE = '/admin/feature-flags'

async function openFlags(page: Page) {
  await gotoAudit(page, FLAGS_ROUTE)
  await page.getByText('alerts.email_notifications').waitFor({ timeout: 30_000 })
  await settle(page)
}

test('admin-feature-flags — default (tabela de flags globais)', async ({ page }) => {
  await setupApp(page, { fixtures: FLAGS_FIXTURES })
  await openFlags(page)
  await shootBothThemes(page, FLAGS_SCREEN, 'default', true)
})

test('admin-feature-flags — empty (nenhuma flag)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...LAYOUT_FIXTURES, '**/api/v1/admin/feature-flags': { flags: [] } },
  })
  await gotoAudit(page, FLAGS_ROUTE)
  await page.getByText('Nenhuma flag cadastrada').waitFor({ timeout: 30_000 })
  await settle(page)
  await shootBothThemes(page, FLAGS_SCREEN, 'empty')
})

test('admin-feature-flags — loading (GET /feature-flags nunca responde)', async ({ page }) => {
  await setupApp(page, {
    fixtures: LAYOUT_FIXTURES,
    stall: ['**/api/v1/admin/feature-flags'],
  })
  await gotoAudit(page, FLAGS_ROUTE)
  await page.getByText('Carregando...').first().waitFor({ timeout: 30_000 })
  await page.waitForTimeout(2000)
  await shootBothThemes(page, FLAGS_SCREEN, 'loading')
})

test('admin-feature-flags — error (GET /feature-flags 500)', async ({ page }) => {
  await setupApp(page, {
    fixtures: LAYOUT_FIXTURES,
    raw: {
      '**/api/v1/admin/feature-flags': {
        status: 500,
        body: { status: 'error', error: 'Falha ao carregar feature flags' },
      },
    },
  })
  await gotoAudit(page, FLAGS_ROUTE)
  await page.getByText('Falha ao carregar feature flags').first().waitFor({ timeout: 30_000 })
  await page.waitForTimeout(800)
  await shootBothThemes(page, FLAGS_SCREEN, 'error')
})

test('admin-feature-flags — saving (PATCH pendurado → toggle desabilitado)', async ({ page }) => {
  await setupApp(page, {
    fixtures: FLAGS_FIXTURES,
    stall: ['**/api/v1/admin/feature-flags/*'],
  })
  await openFlags(page)
  await page.getByRole('button', { name: 'Ativo', exact: true }).first().click()
  await page.waitForTimeout(600)
  await shootBothThemes(page, FLAGS_SCREEN, 'saving')
})

test('admin-feature-flags — hover (toggle Ativo)', async ({ page }) => {
  await setupApp(page, { fixtures: FLAGS_FIXTURES })
  await openFlags(page)
  await page.getByRole('button', { name: 'Ativo', exact: true }).first().hover()
  await page.waitForTimeout(300)
  await shoot(page, FLAGS_SCREEN, 'dark-hover-toggle')
})
