/**
 * Auditoria visual — Grupo 21: Admin Health / Observability (tier 1, WS11).
 *
 * Páginas e endpoints reais consumidos (adminService → api.ts, base /api):
 * - /admin/health    → GET /api/v1/admin/health/platform → PlatformHealth
 *                      { status, services: Record<nome,{status,latency_ms?,details?}>,
 *                        celery_queues: Record<fila, tamanho> }
 * - /admin/workers   → GET /api/v1/admin/workers         → { workers: WorkerInfo[] }
 *                      POST /api/v1/admin/workers/:schema/restart (confirm nativo — não capturável)
 * - /admin/versions  → GET /api/v1/admin/versions        → { versions: SystemVersion[] }
 *                      POST /api/v1/admin/versions (modal Nova Versão)
 * - /admin/changelog → GET /api/v1/admin/changelog?…     → { items, total, page, per_page }
 *                      POST /api/v1/admin/changelog (modal Nova Entrada)
 *
 * O AdminLayout chama GET /v1/admin/dashboard em toda rota (badges da sidebar)
 * — fixture DASHBOARD incluída em todos os estados.
 *
 * ATENÇÃO: PlatformHealthCard NÃO tolera catch-all {} (Object.entries de
 * services/celery_queues) — estado "empty" usa fixture explícito zerado.
 */
import { test, type Page } from '@playwright/test'
import { setupApp, shootBothThemes, shoot, settle, gotoAudit } from './helpers'

/* ── Helpers de data ────────────────────────────────────────────── */

const minsAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()
const daysAgo = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString()

/* ── Fixtures compartilhadas ────────────────────────────────────── */

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

const ERROR_500 = {
  status: 500,
  body: { status: 'error', error: 'Erro interno do servidor' },
}

/* ═══════════════════════════════════════════════════════════════════
 * 1) /admin/health — Saúde da Plataforma
 * ═══════════════════════════════════════════════════════════════════ */

const HEALTH_SLUG = 'admin-health'

const HEALTH_RICO = {
  status: 'degraded',
  services: {
    'PostgreSQL': { status: 'ok', latency_ms: 12.4 },
    'Redis': { status: 'ok', latency_ms: 2.8 },
    'Celery Worker': { status: 'ok', details: '3 workers ativos · fila inference drenando' },
    'R2 Storage': { status: 'degraded', latency_ms: 843.6, details: 'latência alta região GRU' },
    'WS Gateway': { status: 'critical', details: 'sem heartbeat há 4 min' },
    'Pre-annotation (DINO/SAM)': { status: 'ok', latency_ms: 210.5 },
    'Camera Gateway': { status: 'ok', latency_ms: 38.1 },
  },
  celery_queues: { inference: 12, training: 2, extraction: 0, quality: 7, versioning: 1 },
}

const HEALTH_VAZIO = { status: 'healthy', services: {}, celery_queues: {} }

async function gotoHealthRich(page: Page) {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/admin/dashboard': DASHBOARD,
      '**/api/v1/admin/health/platform': HEALTH_RICO,
    },
  })
  await gotoAudit(page, '/admin/health')
  await page.getByText('PostgreSQL').waitFor()
  await settle(page)
}

test('admin-health — default (rico, degradado) + hover Atualizar', async ({ page }) => {
  await gotoHealthRich(page)
  await page.getByRole('button', { name: /Atualizar/ }).hover()
  await page.waitForTimeout(250)
  await shoot(page, HEALTH_SLUG, 'dark-hover-atualizar')
  await page.mouse.move(10, 10)
  await page.waitForTimeout(250)
  await shootBothThemes(page, HEALTH_SLUG, 'default', true)
})

test('admin-health — empty (sem serviços reportados)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/admin/dashboard': DASHBOARD,
      '**/api/v1/admin/health/platform': HEALTH_VAZIO,
    },
  })
  await gotoAudit(page, '/admin/health')
  await page.getByText('Saúde da Plataforma').first().waitFor()
  await settle(page)
  await shootBothThemes(page, HEALTH_SLUG, 'empty', true)
})

test('admin-health — loading (stall)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    stall: ['**/api/v1/admin/health/platform'],
  })
  await gotoAudit(page, '/admin/health')
  await page.getByText('Carregando...').waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, HEALTH_SLUG, 'loading', true)
})

test('admin-health — error (500)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    raw: { '**/api/v1/admin/health/platform': ERROR_500 },
  })
  await gotoAudit(page, '/admin/health')
  await page.getByText('Erro interno do servidor').first().waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, HEALTH_SLUG, 'error', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 2) /admin/workers — Workers On-Premise
 * ═══════════════════════════════════════════════════════════════════ */

const WRK_SLUG = 'admin-workers'

const WORKERS = [
  {
    id: 'w-001', tenant_id: 't-0001', tenant_schema: 'tenant_rvb',
    tenant_name: 'Tenant RVB Industrial', tenant_slug: 'rvb-industrial',
    hostname: 'rvb-edge-01', tailscale_ip: '100.64.10.11', software_version: '2.3.0',
    gpu_model: 'NVIDIA RTX 4070', gpu_vram_gb: 12, status: 'onpremise',
    last_heartbeat_at: minsAgo(1), registered_at: daysAgo(236),
    live_metrics: { gpu_pct: 62.4, vram_used_gb: 9.8, fps_avg: 24.6, cameras_active: 11, timestamp: minsAgo(1), hostname: 'rvb-edge-01' },
  },
  {
    id: 'w-002', tenant_id: 't-0006', tenant_schema: 'tenant_boavista',
    tenant_name: 'Frigorífico Boa Vista', tenant_slug: 'frigorifico-boa-vista',
    hostname: 'bvista-gpu-02', tailscale_ip: '100.64.10.24', software_version: '2.3.0',
    gpu_model: 'NVIDIA RTX 3060', gpu_vram_gb: 12, status: 'onpremise',
    last_heartbeat_at: minsAgo(2), registered_at: daysAgo(60),
    live_metrics: { gpu_pct: 91.2, vram_used_gb: 11.4, fps_avg: 17.3, cameras_active: 9, timestamp: minsAgo(2), hostname: 'bvista-gpu-02' },
  },
  {
    id: 'w-003', tenant_id: 't-0002', tenant_schema: 'tenant_horizonte',
    tenant_name: 'Construtora Horizonte Sul', tenant_slug: 'horizonte-sul',
    hostname: null, gpu_model: null, status: 'railway',
    last_heartbeat_at: minsAgo(6), registered_at: daysAgo(180),
    live_metrics: null,
  },
  {
    id: 'w-004', tenant_id: 't-0005', tenant_schema: 'tenant_andrade',
    tenant_name: 'Transportadora Andrade & Filhos', tenant_slug: 'transportadora-andrade',
    hostname: null, gpu_model: null, status: 'railway',
    last_heartbeat_at: minsAgo(15), registered_at: daysAgo(45),
    live_metrics: null,
  },
  {
    id: 'w-005', tenant_id: 't-0003', tenant_schema: 'tenant_msc',
    tenant_name: 'Metalúrgica São Carlos', tenant_slug: 'metalurgica-sao-carlos',
    hostname: 'msc-edge-01', tailscale_ip: '100.64.10.31', software_version: '2.2.1',
    gpu_model: 'NVIDIA GTX 1660 Super', gpu_vram_gb: 6, status: 'offline',
    last_heartbeat_at: daysAgo(2), registered_at: daysAgo(120),
    live_metrics: null,
  },
  {
    id: 'w-006', tenant_id: 't-0004', tenant_schema: 'tenant_valeverde',
    tenant_name: 'Agroindústria Vale Verde', tenant_slug: 'vale-verde',
    hostname: 'valeverde-nuc', software_version: '2.1.0',
    gpu_model: 'NVIDIA RTX 3050', gpu_vram_gb: 8, status: 'offline',
    last_heartbeat_at: daysAgo(7), registered_at: daysAgo(90),
    live_metrics: null,
  },
]

async function gotoWorkersRich(page: Page) {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/admin/dashboard': DASHBOARD,
      '**/api/v1/admin/workers': { workers: WORKERS },
    },
  })
  await gotoAudit(page, '/admin/workers')
  await page.getByText('Workers On-Premise').waitFor()
  await page.getByText('rvb-edge-01').waitFor()
  await settle(page)
}

test('admin-workers — default (rico) + hover linha e Restart', async ({ page }) => {
  await gotoWorkersRich(page)
  await page.getByText('Tenant RVB Industrial').hover()
  await page.waitForTimeout(250)
  await shoot(page, WRK_SLUG, 'dark-hover-row')
  await page.getByRole('button', { name: /Restart/ }).first().hover()
  await page.waitForTimeout(250)
  await shoot(page, WRK_SLUG, 'dark-hover-restart')
  await page.mouse.move(10, 10)
  await page.waitForTimeout(250)
  await shootBothThemes(page, WRK_SLUG, 'default', true)
})

test('admin-workers — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/admin/dashboard': DASHBOARD,
      '**/api/v1/admin/workers': { workers: [] },
    },
  })
  await gotoAudit(page, '/admin/workers')
  await page.getByText('Nenhum worker registrado').waitFor()
  await settle(page)
  await shootBothThemes(page, WRK_SLUG, 'empty', true)
})

test('admin-workers — loading (stall)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    stall: ['**/api/v1/admin/workers'],
  })
  await gotoAudit(page, '/admin/workers')
  await page.getByText('Carregando...').waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, WRK_SLUG, 'loading', true)
})

test('admin-workers — error (500)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    raw: { '**/api/v1/admin/workers': ERROR_500 },
  })
  await gotoAudit(page, '/admin/workers')
  await page.getByText('Erro interno do servidor').first().waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, WRK_SLUG, 'error', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 3) /admin/versions — Versões do Sistema
 * ═══════════════════════════════════════════════════════════════════ */

const VER_SLUG = 'admin-versions'

const CHANGELOG_V230 = [
  { id: 'cl-101', version_id: 'v-006', version_label: '2.3.0', category: 'feature',  importance: 'high',   title: 'Substream padrão no live view',           affected_area: 'live-view',  created_at: daysAgo(2) },
  { id: 'cl-102', version_id: 'v-006', version_label: '2.3.0', category: 'fix',      importance: 'critical', title: 'Modal de operação com fundo opaco',    affected_area: 'operations', created_at: daysAgo(2) },
  { id: 'cl-103', version_id: 'v-006', version_label: '2.3.0', category: 'infra',    importance: 'normal', title: 'Guard-rail CI contra cores hardcoded',    affected_area: 'ci',         created_at: daysAgo(3) },
  { id: 'cl-104', version_id: 'v-006', version_label: '2.3.0', category: 'config',   importance: 'low',    title: 'Tuning de latência HLS (playlist 3)',     affected_area: 'streaming',  created_at: daysAgo(3) },
]

const VERSIONS = [
  {
    id: 'v-006', version: '2.3.0', version_type: 'minor',
    title: 'Live view com substream padrão',
    description: 'Substream ativado por padrão em todas as câmeras, redução de 40% no consumo de banda do live view.',
    created_by_email: 'vitor@logikos.com.br', created_at: daysAgo(2),
    is_current: true, changelog_count: 4, changelog: CHANGELOG_V230,
  },
  {
    id: 'v-005', version: '2.2.1', version_type: 'patch',
    title: 'Correções no painel de operação',
    description: 'Hotfix de contraste do painel de vídeo sob superfícies claras de white-label.',
    created_by_email: 'suporte@logikos.com.br', created_at: daysAgo(9),
    is_current: false, changelog_count: 2, changelog: [],
  },
  {
    id: 'v-004', version: '2.2.0', version_type: 'minor',
    title: 'White-label de superfícies (WS1)',
    created_by_email: 'vitor@logikos.com.br', created_at: daysAgo(21),
    is_current: false, rolled_back_at: daysAgo(18), rolled_back_by_email: 'vitor@logikos.com.br',
    changelog_count: 3, changelog: [],
  },
  {
    id: 'v-003', version: '2.1.0', version_type: 'minor',
    title: 'Módulo Fueling em beta',
    created_by_email: 'vitor@logikos.com.br', created_at: daysAgo(40),
    is_current: false, changelog_count: 5, changelog: [],
  },
  {
    id: 'v-002', version: '2.0.0', version_type: 'major',
    title: 'Recognition V2 — arquitetura multi-tenant',
    description: 'Migração completa para schemas por tenant, workers on-premise e módulos plugáveis.',
    created_by_email: 'vitor@logikos.com.br', created_at: daysAgo(88),
    is_current: false, changelog_count: 12, changelog: [],
  },
  {
    id: 'v-001', version: '1.9.4', version_type: 'patch',
    title: 'Hotfix reconexão HLS',
    created_by_email: 'suporte@logikos.com.br', created_at: daysAgo(120),
    is_current: false, changelog_count: 1, changelog: [],
  },
]

async function gotoVersionsRich(page: Page) {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/admin/dashboard': DASHBOARD,
      '**/api/v1/admin/versions': { versions: VERSIONS },
    },
  })
  await gotoAudit(page, '/admin/versions')
  await page.getByText('Versões do Sistema').waitFor()
  await page.getByText('Live view com substream padrão').waitFor()
  await settle(page)
}

test('admin-versions — default (rico) + hover Rollback', async ({ page }) => {
  await gotoVersionsRich(page)
  await page.getByRole('button', { name: /Rollback/ }).first().hover()
  await page.waitForTimeout(250)
  await shoot(page, VER_SLUG, 'dark-hover-rollback')
  await page.mouse.move(10, 10)
  await page.waitForTimeout(250)
  await shootBothThemes(page, VER_SLUG, 'default', true)
})

test('admin-versions — expanded (detalhes da versão atual com changelog)', async ({ page }) => {
  await gotoVersionsRich(page)
  await page.getByRole('button', { name: /Detalhes/ }).first().click()
  await page.getByText('Substream padrão no live view').waitFor()
  await settle(page, 400)
  await shootBothThemes(page, VER_SLUG, 'expanded-detalhes', true)
})

test('admin-versions — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/admin/dashboard': DASHBOARD,
      '**/api/v1/admin/versions': { versions: [] },
    },
  })
  await gotoAudit(page, '/admin/versions')
  await page.getByText('Checkpoints de configuração').waitFor()
  await settle(page)
  await shootBothThemes(page, VER_SLUG, 'empty', true)
})

test('admin-versions — loading (stall)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    stall: ['**/api/v1/admin/versions'],
  })
  await gotoAudit(page, '/admin/versions')
  await page.getByText('Carregando...').waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, VER_SLUG, 'loading', true)
})

test('admin-versions — error (500)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    raw: { '**/api/v1/admin/versions': ERROR_500 },
  })
  await gotoAudit(page, '/admin/versions')
  await page.getByText('Erro interno do servidor').first().waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, VER_SLUG, 'error', true)
})

test('admin-versions — modal Nova Versão', async ({ page }) => {
  await gotoVersionsRich(page)
  await page.getByRole('button', { name: /Nova Versão/ }).click()
  await page.getByPlaceholder('1.2.0').waitFor()
  await page.getByPlaceholder('1.2.0').fill('2.4.0')
  await page.getByText('Tipo', { exact: true }).locator('..').locator('select').selectOption('minor')
  await page.getByText('Título', { exact: true }).locator('..').locator('input').fill('Estabilidade do streaming em escala')
  await page.getByText('Descrição (opcional)').locator('..').locator('textarea')
    .fill('Consolida lifecycle do live view, substream padrão e redução de footprint de recursos.')
  await settle(page, 400)
  await shootBothThemes(page, VER_SLUG, 'modal-nova-versao')
})

/* ═══════════════════════════════════════════════════════════════════
 * 4) /admin/changelog — Histórico de mudanças
 * ═══════════════════════════════════════════════════════════════════ */

const CHG_SLUG = 'admin-changelog'

const CHANGELOG_ITEMS = [
  { id: 'cl-201', version_label: '2.3.0', category: 'fix',      importance: 'critical', title: 'Modal de operação com fundo opaco',              affected_area: 'operations',  description: 'Corrige vídeo vazando atrás do modal de operação em tenants white-label com superfícies claras.', created_by_email: 'vitor@logikos.com.br',   created_at: daysAgo(2) },
  { id: 'cl-202', version_label: '2.3.0', category: 'feature',  importance: 'high',     title: 'Substream padrão no live view',                   affected_area: 'live-view',   description: 'Live view abre no substream por padrão, com upgrade manual para o mainstream.',                    created_by_email: 'vitor@logikos.com.br',   created_at: daysAgo(2) },
  { id: 'cl-203', version_label: '2.3.0', category: 'security', importance: 'critical', title: 'Isolamento de tenant nas queries de validação',   affected_area: 'backend',     description: 'count_validated e get_annotated_by_video passam a filtrar por tenant_id.',                          created_by_email: 'suporte@logikos.com.br', created_at: daysAgo(3) },
  { id: 'cl-204', version_label: '2.3.0', category: 'infra',    importance: 'normal',   title: 'Guard-rail CI contra cores hardcoded',            affected_area: 'ci',          description: 'Falha o build quando encontra rgba(255,255,255,x) fora dos tokens do tema.',                        created_by_email: 'vitor@logikos.com.br',   created_at: daysAgo(3) },
  { id: 'cl-205', version_label: '2.2.1', category: 'fix',      importance: 'high',     title: 'Contraste do painel de vídeo em superfície clara', affected_area: 'operations', created_by_email: 'suporte@logikos.com.br', created_at: daysAgo(9) },
  { id: 'cl-206', version_label: '2.2.1', category: 'config',   importance: 'low',      title: 'Tuning de latência HLS (playlist 3, segmento 1s)', affected_area: 'streaming',  created_by_email: 'vitor@logikos.com.br',   created_at: daysAgo(10) },
  { id: 'cl-207', version_label: '2.2.0', category: 'breaking', importance: 'high',     title: 'CSS vars planas para white-label de superfícies',  affected_area: 'frontend',   description: 'Tenants precisam redeclarar overrides usando --color-bg-base e afins.',                            created_by_email: 'vitor@logikos.com.br',   created_at: daysAgo(21) },
  { id: 'cl-208', version_label: '2.1.0', category: 'feature',  importance: 'normal',   title: 'Módulo Fueling em beta para tenants selecionados', affected_area: 'modules',    created_by_email: 'vitor@logikos.com.br',   created_at: daysAgo(40) },
]

const CHANGELOG_PAGE = { items: CHANGELOG_ITEMS, total: CHANGELOG_ITEMS.length, page: 1, per_page: 20 }

async function gotoChangelogRich(page: Page) {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/admin/dashboard': DASHBOARD,
      '**/api/v1/admin/changelog*': CHANGELOG_PAGE,
    },
  })
  await gotoAudit(page, '/admin/changelog')
  await page.getByText('Histórico de mudanças').waitFor()
  await page.getByText('Modal de operação com fundo opaco').waitFor()
  await settle(page)
}

test('admin-changelog — default (rico) + hover linha', async ({ page }) => {
  await gotoChangelogRich(page)
  await page.getByText('Modal de operação com fundo opaco').hover()
  await page.waitForTimeout(250)
  await shoot(page, CHG_SLUG, 'dark-hover-row')
  await page.mouse.move(10, 10)
  await page.waitForTimeout(250)
  await shootBothThemes(page, CHG_SLUG, 'default', true)
})

test('admin-changelog — expanded (linha com descrição aberta)', async ({ page }) => {
  await gotoChangelogRich(page)
  await page.getByText('Modal de operação com fundo opaco').click()
  await page.getByText('Corrige vídeo vazando atrás do modal').waitFor()
  await settle(page, 400)
  await shootBothThemes(page, CHG_SLUG, 'expanded-descricao', true)
})

test('admin-changelog — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/admin/dashboard': DASHBOARD,
      '**/api/v1/admin/changelog*': { items: [], total: 0, page: 1, per_page: 20 },
    },
  })
  await gotoAudit(page, '/admin/changelog')
  await page.getByText('Nenhuma entrada encontrada.').waitFor()
  await settle(page)
  await shootBothThemes(page, CHG_SLUG, 'empty', true)
})

test('admin-changelog — loading (stall)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    stall: ['**/api/v1/admin/changelog*'],
  })
  await gotoAudit(page, '/admin/changelog')
  await page.getByText('Carregando...').waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, CHG_SLUG, 'loading', true)
})

test('admin-changelog — error (500)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/admin/dashboard': DASHBOARD },
    raw: { '**/api/v1/admin/changelog*': ERROR_500 },
  })
  await gotoAudit(page, '/admin/changelog')
  await page.getByText('Erro interno do servidor').first().waitFor()
  await page.waitForTimeout(1200)
  await shootBothThemes(page, CHG_SLUG, 'error', true)
})

test('admin-changelog — modal Nova Entrada', async ({ page }) => {
  await gotoChangelogRich(page)
  await page.getByRole('button', { name: /Adicionar entrada/ }).click()
  await page.getByText('Título *').waitFor()
  await page.getByText('Título *').locator('..').locator('input').fill('Reconexão automática do WS Gateway')
  await page.getByText('Categoria', { exact: true }).locator('..').locator('select').selectOption('fix')
  await page.getByText('Importância', { exact: true }).locator('..').locator('select').selectOption('high')
  await page.getByText('Descrição', { exact: true }).locator('..').locator('textarea')
    .fill('Backoff exponencial na reconexão do gateway de WebSocket após perda de heartbeat.')
  await page.getByText('Área afetada', { exact: true }).locator('..').locator('input').fill('ws-gateway')
  await settle(page, 400)
  await shootBothThemes(page, CHG_SLUG, 'modal-nova-entrada')
})
