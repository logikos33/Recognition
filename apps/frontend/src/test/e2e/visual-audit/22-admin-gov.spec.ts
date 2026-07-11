/**
 * Auditoria visual — Grupo 22: Admin Governança (tier 2, role superadmin).
 *
 * Páginas e endpoints reais consumidos (adminService / api.ts, base /api):
 * - /admin/audit-log          → GET /api/v1/admin/audit-log?…            → { items: AuditEntry[], total }
 * - /admin/announcements      → GET /api/v1/admin/announcements          → { announcements: Announcement[] }
 * - /admin/retention          → GET /api/v1/admin/tenants                → { tenants: Tenant[] } (usa video_retention_days)
 * - /admin/tickets            → GET /api/v1/admin/tickets?…              → { items: SupportTicket[], total }
 * - /admin/inventory          → GET /api/v1/admin/inventory?…            → { cameras: Camera[], total } (só carrega ao clicar "Buscar")
 * - /admin/test-console       → GET /api/v1/admin/test-console/status    → TestConsoleStatus
 *                               GET /api/v1/training/models              → { models: [...] }
 *                               GET /api/v1/admin/integrations           → { integrations: Integration[] }
 * - /admin/demo-videos        → GET /api/admin/demo-videos?module=…      → { videos: DemoVideo[] }
 * - /admin/training-approvals → GET /api/v1/admin/training-approvals?…   → { items: TrainingApproval[], total }
 *
 * O AdminLayout chama GET /v1/admin/dashboard em toda rota (badges da
 * sidebar) — fixture DASHBOARD_BADGES incluído em todos os estados.
 *
 * Tier 2: default (fixture rica) + empty por página; modal principal quando barato.
 */
import { test, type Page } from '@playwright/test'
import { setupApp, shootBothThemes, settle, gotoAudit } from './helpers'

/* ── Helpers de data ────────────────────────────────────────────── */

const minsAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()
const daysAgo = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString()

/* ── Fixtures compartilhadas ────────────────────────────────────── */

const DASHBOARD_BADGES = {
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

const BASE_FIXTURES = { '**/api/v1/admin/dashboard': DASHBOARD_BADGES }

/* ═══════════════════════════════════════════════════════════════════
 * 1) /admin/audit-log — Audit Log
 * ═══════════════════════════════════════════════════════════════════ */

const AUD_SLUG = 'admin-audit-log'

const AUDIT_ENTRIES = [
  { id: 'al-001', action: 'tenant.suspend',            target_type: 'tenant',  target_id: 't-0004aa11', actor_role: 'superadmin', actor_email: 'vitor@logikos.com.br',       tenant_name: 'Agroindústria Vale Verde',        ip_address: '187.55.102.14', created_at: minsAgo(18) },
  { id: 'al-002', action: 'camera.create',             target_type: 'camera',  target_id: 'cam-778812', actor_role: 'admin',      actor_email: 'joana.melo@rvb.ind.br',      tenant_name: 'Tenant RVB Industrial',           ip_address: '200.148.33.7',  created_at: minsAgo(95) },
  { id: 'al-003', action: 'training.approve',          target_type: 'training', target_id: 'job-45f2c1', actor_role: 'superadmin', actor_email: 'suporte@logikos.com.br',     tenant_name: 'Construtora Horizonte Sul',       ip_address: '187.55.102.14', created_at: minsAgo(230) },
  { id: 'al-004', action: 'user.force_password_reset', target_type: 'user',    target_id: 'u-30122abc', actor_role: 'superadmin', actor_email: 'vitor@logikos.com.br',       tenant_name: 'Metalúrgica São Carlos',          ip_address: '187.55.102.14', created_at: minsAgo(410) },
  { id: 'al-005', action: 'alert_rule.update',         target_type: 'rule',    target_id: 'r-9982fe01', actor_role: 'admin',      actor_email: 'pedro.assis@horizontesul.com.br', tenant_name: 'Construtora Horizonte Sul',   ip_address: '177.68.90.201', created_at: minsAgo(760) },
  { id: 'al-006', action: 'auth.login_failed_burst',   target_type: 'user',    actor_role: 'system',                                                                          tenant_name: 'Transportadora Andrade & Filhos',                              created_at: daysAgo(1) },
  { id: 'al-007', action: 'tenant.plan_change',        target_type: 'tenant',  target_id: 't-0001bb22', actor_role: 'superadmin', actor_email: 'vitor@logikos.com.br',       tenant_name: 'Tenant RVB Industrial',           ip_address: '187.55.102.14', created_at: daysAgo(2) },
]

test('admin-audit-log — default (rico)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      ...BASE_FIXTURES,
      '**/api/v1/admin/audit-log*': { items: AUDIT_ENTRIES, total: AUDIT_ENTRIES.length },
    },
  })
  await gotoAudit(page, '/admin/audit-log')
  await page.getByText('Audit Log').first().waitFor()
  await page.getByText('tenant.suspend').waitFor()
  await settle(page)
  await shootBothThemes(page, AUD_SLUG, 'default', true)
})

test('admin-audit-log — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...BASE_FIXTURES, '**/api/v1/admin/audit-log*': { items: [], total: 0 } },
  })
  await gotoAudit(page, '/admin/audit-log')
  await page.getByText('Nenhum registro').waitFor()
  await settle(page)
  await shootBothThemes(page, AUD_SLUG, 'empty', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 2) /admin/announcements — Comunicados
 * ═══════════════════════════════════════════════════════════════════ */

const ANN_SLUG = 'admin-announcements'

const ANNOUNCEMENTS = [
  { id: 'an-001', title: 'Manutenção programada — 12/07 às 02h',        content: 'A plataforma ficará indisponível por até 40 minutos para atualização do banco de dados.',      type: 'maintenance', target: 'all',            published_at: daysAgo(1),  expires_at: daysAgo(-6),  created_at: daysAgo(1) },
  { id: 'an-002', title: 'Novo módulo: Contagem de Produtos (beta)',    content: 'O módulo de contagem automática já está disponível para tenants do plano Enterprise.',          type: 'feature',     target: 'all',            published_at: daysAgo(4),  expires_at: daysAgo(-30), created_at: daysAgo(4) },
  { id: 'an-003', title: 'Atualização de política de senhas',          content: 'A partir de agosto, senhas expiram a cada 90 dias conforme política de segurança LGPD.',        type: 'security',    target: 'all',            published_at: daysAgo(9),                            created_at: daysAgo(9) },
  { id: 'an-004', title: 'Treinamento agendado — Tenant RVB',           content: 'Retreino do modelo EPI agendado para o próximo sábado com o novo dataset validado.',            type: 'info',        target: 'tenant:t-0001',  published_at: daysAgo(12), expires_at: daysAgo(-2),  created_at: daysAgo(12) },
  { id: 'an-005', title: 'Relatórios mensais disponíveis',              content: 'Os relatórios consolidados de junho já podem ser exportados na aba Relatórios.',                type: 'info',        target: 'all',            published_at: daysAgo(15),                           created_at: daysAgo(15) },
]

const ANN_FIXTURES = {
  ...BASE_FIXTURES,
  '**/api/v1/admin/announcements': { announcements: ANNOUNCEMENTS },
}

async function gotoAnnouncementsRich(page: Page) {
  await setupApp(page, { fixtures: ANN_FIXTURES })
  await gotoAudit(page, '/admin/announcements')
  await page.getByText('comunicados ativos').waitFor()
  await page.getByText('Manutenção programada — 12/07 às 02h').waitFor()
  await settle(page)
}

test('admin-announcements — default (rico)', async ({ page }) => {
  await gotoAnnouncementsRich(page)
  await shootBothThemes(page, ANN_SLUG, 'default', true)
})

test('admin-announcements — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...BASE_FIXTURES, '**/api/v1/admin/announcements': { announcements: [] } },
  })
  await gotoAudit(page, '/admin/announcements')
  await page.getByText('Nenhum comunicado').waitFor()
  await settle(page)
  await shootBothThemes(page, ANN_SLUG, 'empty', true)
})

test('admin-announcements — modal Novo Comunicado', async ({ page }) => {
  await gotoAnnouncementsRich(page)
  await page.getByRole('button', { name: /Novo Comunicado/ }).click()
  await page.getByText('Conteúdo', { exact: true }).waitFor()
  await page.getByText('Título', { exact: true }).locator('..').locator('input')
    .fill('Janela de manutenção — atualização do worker')
  await page.getByText('Conteúdo', { exact: true }).locator('..').locator('textarea')
    .fill('O worker on-premise do Tenant RVB Industrial será atualizado para a versão 2.4 nesta sexta-feira, sem impacto nas câmeras.')
  await settle(page, 400)
  await shootBothThemes(page, ANN_SLUG, 'modal-novo-comunicado')
})

/* ═══════════════════════════════════════════════════════════════════
 * 3) /admin/retention — Tiers de Retenção
 * ═══════════════════════════════════════════════════════════════════ */

const RET_SLUG = 'admin-retention'

const RETENTION_TENANTS = [
  { id: 't-0001', slug: 'rvb-industrial',          name: 'Tenant RVB Industrial',           plan: 'enterprise', schema_name: 'tenant_rvb',       modules_enabled: ['epi', 'quality'], is_active: true,  requires_training_approval: true,  mrr_per_camera: {}, contract_cameras: 12, video_retention_days: 90, created_at: daysAgo(236) },
  { id: 't-0002', slug: 'horizonte-sul',           name: 'Construtora Horizonte Sul',       plan: 'premium',    schema_name: 'tenant_horizonte', modules_enabled: ['epi'],            is_active: true,  requires_training_approval: true,  mrr_per_camera: {}, contract_cameras: 8,  video_retention_days: 30, created_at: daysAgo(180) },
  { id: 't-0003', slug: 'metalurgica-sao-carlos',  name: 'Metalúrgica São Carlos',          plan: 'standard',   schema_name: 'tenant_msc',       modules_enabled: ['epi'],            is_active: true,  requires_training_approval: false, mrr_per_camera: {}, contract_cameras: 5,  video_retention_days: 7,  created_at: daysAgo(120) },
  { id: 't-0004', slug: 'vale-verde',              name: 'Agroindústria Vale Verde',        plan: 'basic',      schema_name: 'tenant_valeverde', modules_enabled: ['basic'],          is_active: false, requires_training_approval: false, mrr_per_camera: {}, contract_cameras: 2,  video_retention_days: 1,  created_at: daysAgo(90) },
  { id: 't-0005', slug: 'transportadora-andrade',  name: 'Transportadora Andrade & Filhos', plan: 'standard',   schema_name: 'tenant_andrade',   modules_enabled: ['epi'],            is_active: true,  requires_training_approval: false, mrr_per_camera: {}, contract_cameras: 6,                            created_at: daysAgo(45) },
]

const RET_FIXTURES = {
  ...BASE_FIXTURES,
  '**/api/v1/admin/tenants': { tenants: RETENTION_TENANTS },
}

async function gotoRetentionRich(page: Page) {
  await setupApp(page, { fixtures: RET_FIXTURES })
  await gotoAudit(page, '/admin/retention')
  await page.getByText('Tiers de Retenção').waitFor()
  await page.getByText('Tenant RVB Industrial').waitFor()
  await settle(page)
}

test('admin-retention — default (rico)', async ({ page }) => {
  await gotoRetentionRich(page)
  await shootBothThemes(page, RET_SLUG, 'default', true)
})

test('admin-retention — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...BASE_FIXTURES, '**/api/v1/admin/tenants': { tenants: [] } },
  })
  await gotoAudit(page, '/admin/retention')
  await page.getByText('Nenhum tenant encontrado.').waitFor()
  await settle(page)
  await shootBothThemes(page, RET_SLUG, 'empty', true)
})

test('admin-retention — edit-tier (seletor de tier inline)', async ({ page }) => {
  await gotoRetentionRich(page)
  await page.getByRole('button', { name: 'Editar' }).first().click()
  await page.getByRole('button', { name: /^Salvar$/ }).waitFor()
  await settle(page, 400)
  await shootBothThemes(page, RET_SLUG, 'edit-tier', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 4) /admin/tickets — Tickets de Suporte
 * ═══════════════════════════════════════════════════════════════════ */

const TIC_SLUG = 'admin-tickets'

const TICKETS = [
  { id: 'tk-00019a3f', tenant_id: 't-0001', tenant_name: 'Tenant RVB Industrial',           subject: 'Câmera Pátio Norte sem stream desde ontem',      category: 'bug',        priority: 'critical', status: 'open',           created_at: minsAgo(50),  updated_at: minsAgo(50) },
  { id: 'tk-00028b41', tenant_id: 't-0002', tenant_name: 'Construtora Horizonte Sul',       subject: 'Falsos positivos de capacete na Doca 3',          category: 'retrain',    priority: 'high',     status: 'in_progress',    first_responded_at: minsAgo(120), created_at: minsAgo(300), updated_at: minsAgo(60) },
  { id: 'tk-00037c52', tenant_id: 't-0003', tenant_name: 'Metalúrgica São Carlos',          subject: 'Dúvida sobre exportação de relatório mensal',     category: 'question',   priority: 'normal',   status: 'waiting_client', first_responded_at: daysAgo(1),   created_at: daysAgo(2),   updated_at: daysAgo(1) },
  { id: 'tk-00046d63', tenant_id: 't-0005', tenant_name: 'Transportadora Andrade & Filhos', subject: 'Solicitação de módulo de contagem de pallets',    category: 'new_module', priority: 'low',      status: 'open',           created_at: daysAgo(3),   updated_at: daysAgo(3) },
  { id: 'tk-00055e74', tenant_id: 't-0001', tenant_name: 'Tenant RVB Industrial',           subject: 'Cobrança duplicada na fatura de junho',           category: 'billing',    priority: 'high',     status: 'resolved',       first_responded_at: daysAgo(4),   created_at: daysAgo(5),   updated_at: daysAgo(2) },
  { id: 'tk-00064f85', tenant_id: 't-0004', tenant_name: 'Agroindústria Vale Verde',        subject: 'Acesso de novo operador ao dashboard',            category: 'question',   priority: 'normal',   status: 'closed',         first_responded_at: daysAgo(8),   created_at: daysAgo(9),   updated_at: daysAgo(7) },
  { id: 'tk-00073a96', tenant_id: 't-0002', tenant_name: 'Construtora Horizonte Sul',       subject: 'Latência alta no live view do canteiro',          category: 'bug',        priority: 'normal',   status: 'open',           created_at: daysAgo(1),   updated_at: daysAgo(1) },
]

test('admin-tickets — default (rico)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      ...BASE_FIXTURES,
      '**/api/v1/admin/tickets*': { items: TICKETS, total: TICKETS.length },
    },
  })
  await gotoAudit(page, '/admin/tickets')
  await page.getByText('Tickets de Suporte').waitFor()
  await page.getByText('Câmera Pátio Norte sem stream desde ontem').waitFor()
  await settle(page)
  await shootBothThemes(page, TIC_SLUG, 'default', true)
})

test('admin-tickets — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...BASE_FIXTURES, '**/api/v1/admin/tickets*': { items: [], total: 0 } },
  })
  await gotoAudit(page, '/admin/tickets')
  await page.getByText('Nenhum ticket encontrado').waitFor()
  await settle(page)
  await shootBothThemes(page, TIC_SLUG, 'empty', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 5) /admin/inventory — Inventário de Câmeras
 *    (carrega só ao clicar "Buscar" — default inclui o clique)
 * ═══════════════════════════════════════════════════════════════════ */

const INV_SLUG = 'admin-inventory'

const INVENTORY_CAMERAS = [
  { id: 'cam-001', name: 'Câmera Pátio Norte',    brand: 'Intelbras', model: 'VIP 3230 B',   ip: '192.168.10.21', host: '192.168.10.21', port: 554,  manufacturer: 'intelbras', probe_status: 'ok',      codec_detected: 'h264',  substream_ok: true,  last_probe_at: minsAgo(22),  is_active: true,  tenant_name: 'Tenant RVB Industrial',           notes: null },
  { id: 'cam-002', name: 'Câmera Doca 3',         brand: 'Hikvision', model: 'DS-2CD2043G2', ip: '192.168.10.34', host: '192.168.10.34', port: 554,  manufacturer: 'hikvision', probe_status: 'ok',      codec_detected: 'h265',  substream_ok: true,  last_probe_at: minsAgo(22),  is_active: true,  tenant_name: 'Tenant RVB Industrial',           notes: null },
  { id: 'cam-003', name: 'Câmera Almoxarifado',   brand: 'Intelbras', model: 'VIP 1230 B',   ip: '192.168.20.11', host: '192.168.20.11', port: 554,  manufacturer: 'intelbras', probe_status: 'timeout', codec_detected: null,    substream_ok: false, last_probe_at: minsAgo(140), is_active: true,  tenant_name: 'Construtora Horizonte Sul',       notes: null },
  { id: 'cam-004', name: 'Câmera Portaria Sul',   brand: 'Hikvision', model: null,           ip: '10.0.4.18',     host: '10.0.4.18',     port: 8554, manufacturer: 'hikvision', probe_status: 'error',   codec_detected: null,    substream_ok: null,  last_probe_at: daysAgo(1),   is_active: true,  tenant_name: 'Metalúrgica São Carlos',          notes: null },
  { id: 'cam-005', name: 'Câmera Linha Produção A', brand: null,      model: null,           ip: '192.168.30.7',  host: '192.168.30.7',  port: 554,  manufacturer: 'generic',   probe_status: 'pending', codec_detected: null,    substream_ok: null,  last_probe_at: null,         is_active: false, tenant_name: 'Transportadora Andrade & Filhos', notes: null },
  { id: 'cam-006', name: 'Câmera Bomba Diesel 02', brand: 'Intelbras', model: 'VIP 3240',    ip: '172.16.8.42',   host: '172.16.8.42',   port: 554,  manufacturer: 'intelbras', probe_status: 'ok',      codec_detected: 'h264',  substream_ok: false, last_probe_at: minsAgo(65),  is_active: true,  tenant_name: 'Agroindústria Vale Verde',        notes: null },
]

test('admin-inventory — default (rico, após Buscar)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      ...BASE_FIXTURES,
      '**/api/v1/admin/inventory*': { cameras: INVENTORY_CAMERAS, total: INVENTORY_CAMERAS.length },
    },
  })
  await gotoAudit(page, '/admin/inventory')
  await page.getByText('Inventário de Câmeras').waitFor()
  await page.getByRole('button', { name: 'Buscar' }).click()
  await page.getByText('Câmera Pátio Norte').waitFor()
  await settle(page)
  await shootBothThemes(page, INV_SLUG, 'default', true)
})

test('admin-inventory — empty (estado inicial, sem busca)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...BASE_FIXTURES, '**/api/v1/admin/inventory*': { cameras: [], total: 0 } },
  })
  await gotoAudit(page, '/admin/inventory')
  await page.getByText('para carregar o inventário').waitFor()
  await settle(page)
  await shootBothThemes(page, INV_SLUG, 'empty', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 6) /admin/test-console — Console de Teste E2E
 * ═══════════════════════════════════════════════════════════════════ */

const CON_SLUG = 'admin-test-console'

const CONSOLE_STATUS_RUNNING = {
  status: 'running',
  session_id: 'a3f8c2d1-7b4e-4f2a-9c1d-5e6f7a8b9c0d',
  started_at: minsAgo(12),
  stopped_at: null,
  config: {
    camera_count: 8,
    model_id: 'mdl-epi-rvb-v3',
    scenario_config: { classes: ['helmet', 'no_helmet', 'vest', 'no_vest'], confidence_threshold: 0.5 },
    mode: 'harness',
  },
  metrics: { detections_per_sec: 42.7, latency_ms: 187, throughput_infs: 96.3, vram_pct: 71, cameras_active: 8 },
  log_lines: [
    '[14:02:11] Sessão a3f8c2d1 iniciada — 8 câmeras simuladas',
    '[14:02:14] Instância Vast.ai provisionada (RTX 4090, 24GB)',
    '[14:02:31] Modelo mdl-epi-rvb-v3 carregado em 6.2s',
    '[14:03:02] Câmeras 1-8 conectadas — streams RTSP ok',
    '[14:05:47] 2.418 detecções acumuladas · latência média 187ms',
    '[14:09:12] VRAM 71% · throughput estável em 96 inf/s',
  ],
  vast_ai_configured: true,
}

const CONSOLE_STATUS_IDLE = {
  status: 'idle',
  session_id: null,
  started_at: null,
  stopped_at: null,
  config: null,
  metrics: { detections_per_sec: 0, latency_ms: 0, throughput_infs: 0, vram_pct: 0, cameras_active: 0 },
  log_lines: [],
  vast_ai_configured: false,
}

const CONSOLE_MODELS = {
  models: [
    { id: 'mdl-epi-rvb-v3', name: 'EPI RVB Industrial', version: '3.1.0' },
    { id: 'mdl-epi-base-v2', name: 'EPI Base Multi-tenant', version: '2.4.0' },
    { id: 'mdl-fueling-v1', name: 'Fueling Detecção de Bico', version: '1.0.2' },
  ],
}

const INTEGRATIONS = {
  integrations: [
    { id: 'int-001', tenant_id: '00000000-0000-0000-0000-000000000001', tenant_name: 'Logikos (plataforma)',    key: 'vast_ai',      configured: true, created_at: daysAgo(30), updated_at: daysAgo(3) },
    { id: 'int-002', tenant_id: 't-0001',                               tenant_name: 'Tenant RVB Industrial',   key: 'slack_webhook', configured: true, created_at: daysAgo(60), updated_at: daysAgo(14) },
  ],
}

const CONSOLE_FIXTURES_RICH = {
  ...BASE_FIXTURES,
  '**/api/v1/admin/test-console/status': CONSOLE_STATUS_RUNNING,
  '**/api/v1/training/models': CONSOLE_MODELS,
  '**/api/v1/admin/integrations': INTEGRATIONS,
}

async function gotoConsoleRich(page: Page) {
  await setupApp(page, { fixtures: CONSOLE_FIXTURES_RICH })
  await gotoAudit(page, '/admin/test-console')
  await page.getByText('Console de Teste E2E').waitFor()
  await page.getByText('Em andamento').waitFor()
  await settle(page)
}

test('admin-test-console — default (sessão em andamento)', async ({ page }) => {
  await gotoConsoleRich(page)
  await shootBothThemes(page, CON_SLUG, 'default', true)
})

test('admin-test-console — empty (idle, Vast.ai não configurada)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      ...BASE_FIXTURES,
      '**/api/v1/admin/test-console/status': CONSOLE_STATUS_IDLE,
      '**/api/v1/training/models': { models: [] },
      '**/api/v1/admin/integrations': { integrations: [] },
    },
  })
  await gotoAudit(page, '/admin/test-console')
  await page.getByText('Configure sua chave Vast.ai').waitFor()
  await settle(page)
  await shootBothThemes(page, CON_SLUG, 'empty', true)
})

test('admin-test-console — modal-add-integracao (form de segredo)', async ({ page }) => {
  await gotoConsoleRich(page)
  await page.getByRole('button', { name: '+ Adicionar / Atualizar' }).click()
  await page.getByPlaceholder('sk-...').waitFor()
  await page.getByPlaceholder('sk-...').fill('vast-9f83aa71bc55')
  await settle(page, 400)
  await shootBothThemes(page, CON_SLUG, 'modal-add-integracao', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 7) /admin/demo-videos — Vídeos Demo
 * ═══════════════════════════════════════════════════════════════════ */

const DEM_SLUG = 'admin-demo-videos'

const DEMO_VIDEOS = {
  videos: [
    { id: 1, module: 'fueling', camera_id: 12,   label: 'Pátio Baia 01',        r2_url: 'https://r2.recognition.dev/demo/fueling-baia01.mp4', file_size_bytes: 48_234_112, created_at: daysAgo(8) },
    { id: 2, module: 'fueling', camera_id: 14,   label: 'Bomba Diesel 02',      r2_url: 'https://r2.recognition.dev/demo/fueling-bomba02.mp4', file_size_bytes: 61_512_890, created_at: daysAgo(8) },
    { id: 3, module: 'fueling', camera_id: null, label: 'Descarga de Caminhão', r2_url: 'https://r2.recognition.dev/demo/fueling-descarga.mp4', file_size_bytes: 33_780_444, created_at: daysAgo(21) },
    { id: 4, module: 'fueling', camera_id: null, label: null,                   r2_url: 'https://r2.recognition.dev/demo/fueling-generico.mp4', file_size_bytes: 512_331,    created_at: daysAgo(40) },
  ],
}

const DEMO_FIXTURES = {
  ...BASE_FIXTURES,
  '**/api/admin/demo-videos*': DEMO_VIDEOS,
}

async function gotoDemoVideosRich(page: Page) {
  await setupApp(page, { fixtures: DEMO_FIXTURES })
  await gotoAudit(page, '/admin/demo-videos')
  await page.getByText('Vídeos Demo').first().waitFor()
  await page.getByText('Pátio Baia 01').waitFor()
  await settle(page)
}

test('admin-demo-videos — default (rico)', async ({ page }) => {
  await gotoDemoVideosRich(page)
  await shootBothThemes(page, DEM_SLUG, 'default', true)
})

test('admin-demo-videos — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...BASE_FIXTURES, '**/api/admin/demo-videos*': { videos: [] } },
  })
  await gotoAudit(page, '/admin/demo-videos')
  await page.getByText('Nenhum vídeo demo cadastrado').waitFor()
  await settle(page)
  await shootBothThemes(page, DEM_SLUG, 'empty', true)
})

test('admin-demo-videos — modal-upload', async ({ page }) => {
  await gotoDemoVideosRich(page)
  await page.getByRole('button', { name: /Upload de vídeo/ }).click()
  await page.getByText('Upload de vídeo demo').waitFor()
  await page.getByPlaceholder('ex: Pátio Baia 01').fill('Pátio Baia 03 — turno noturno')
  await settle(page, 400)
  await shootBothThemes(page, DEM_SLUG, 'modal-upload')
})

/* ═══════════════════════════════════════════════════════════════════
 * 8) /admin/training-approvals — Aprovações de Treinamento
 * ═══════════════════════════════════════════════════════════════════ */

const APR_SLUG = 'admin-training-approvals'

const APPROVALS = [
  { id: 'ap-001', tenant_id: 't-0001', tenant_name: 'Tenant RVB Industrial',           training_job_id: 'job-45f2c1aa', module: 'epi',     job_name: 'EPI RVB — dataset v4 (capacete/colete)', metrics: { mAP50: 0.912, mAP50_95: 0.744, box_loss: 0.031, dataset_size: 4820, classes: ['helmet', 'no_helmet', 'vest', 'no_vest'], epochs: 120 }, status: 'pending', created_at: minsAgo(90) },
  { id: 'ap-002', tenant_id: 't-0002', tenant_name: 'Construtora Horizonte Sul',       training_job_id: 'job-77d3e2bb', module: 'epi',     job_name: 'EPI Canteiro — luvas e óculos',          metrics: { mAP50: 0.861, mAP50_95: 0.652, box_loss: 0.048, dataset_size: 2140, classes: ['gloves', 'no_gloves', 'glasses', 'no_glasses'], epochs: 80 }, status: 'pending', created_at: minsAgo(340) },
  { id: 'ap-003', tenant_id: 't-0005', tenant_name: 'Transportadora Andrade & Filhos', training_job_id: 'job-19a8f3cc', module: 'fueling', job_name: 'Fueling — bico e placa v2',              metrics: { mAP50: 0.883, mAP50_95: 0.701, dataset_size: 1675, classes: ['fuel_nozzle', 'plate', 'truck'], epochs: 100 }, status: 'pending', created_at: daysAgo(1) },
  { id: 'ap-004', tenant_id: 't-0003', tenant_name: 'Metalúrgica São Carlos',          training_job_id: 'job-52b6c4dd', module: 'epi',     job_name: 'EPI Fundição — retreino trimestral',     metrics: { mAP50: 0.794, mAP50_95: 0.588, dataset_size: 980, epochs: 60 }, status: 'pending', created_at: daysAgo(2) },
  { id: 'ap-005', tenant_id: 't-0001', tenant_name: 'Tenant RVB Industrial',           training_job_id: 'job-88c1d5ee', module: 'quality', job_name: 'Qualidade — inspeção de solda',          metrics: { mAP50: 0.928, mAP50_95: 0.802, dataset_size: 3410, epochs: 150 }, status: 'pending', created_at: daysAgo(3) },
]

test('admin-training-approvals — default (rico)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      ...BASE_FIXTURES,
      '**/api/v1/admin/training-approvals*': { items: APPROVALS, total: APPROVALS.length },
    },
  })
  await gotoAudit(page, '/admin/training-approvals')
  await page.getByText('Aprovações de Treinamento').waitFor()
  await page.getByText('EPI RVB — dataset v4 (capacete/colete)').waitFor()
  await settle(page)
  await shootBothThemes(page, APR_SLUG, 'default', true)
})

test('admin-training-approvals — empty', async ({ page }) => {
  await setupApp(page, {
    fixtures: { ...BASE_FIXTURES, '**/api/v1/admin/training-approvals*': { items: [], total: 0 } },
  })
  await gotoAudit(page, '/admin/training-approvals')
  await page.getByText('Nenhuma aprovação encontrada').waitFor()
  await settle(page)
  await shootBothThemes(page, APR_SLUG, 'empty', true)
})
