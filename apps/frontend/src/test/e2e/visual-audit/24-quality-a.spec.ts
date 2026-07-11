/**
 * Auditoria visual — Grupo 24-quality-a (tier 2): módulo Qualidade, parte A.
 *
 * Rotas REAIS (QualityLayout.tsx — /quality redireciona pra /quality/cameras):
 * - /quality/dashboard   → GET /api/v1/quality/dashboard/summary  → { summary, updated_at }
 *                          GET /api/v1/quality/dashboard/stations → { stations: StationLive[], updated_at }
 * - /quality/cameras     → GET /api/v1/quality/cameras            → { cameras: QualityCamera[] }
 *                          GET /api/v1/quality/cameras/available  → { cameras: QualityCamera[] }
 * - /quality/inspections → SEM API — página roda em "MODO DEMONSTRAÇÃO" com mock
 *                          client-side (200 inspeções geradas em runtime); estados
 *                          vazio/drawer obtidos via interação (filtro + célula Feedback)
 * - /quality/pieces      → GET /api/v1/quality/gate/pieces?page…  → { pieces, total, page, per_page }
 *                          GET /api/v1/quality/gate/pieces/:id    → { piece: PieceDetail }
 * - /quality/config      → GET /api/v1/quality/gate/stations      → { stations: QualityStation[] }
 *                          (seção "Parâmetros de Inspeção" nunca renderiza — editConfig
 *                          jamais é populado no load; registrado como issue)
 *
 * Tier 2: default + empty por página; modal/drawer/inline-edit quando barato.
 */
import { test, type Page } from '@playwright/test'
import { setupApp, shootBothThemes, settle, gotoAudit } from './helpers'

/* ── Helpers de data ────────────────────────────────────────────── */

const minsAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()
const hoursAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString()
const daysAgo = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString()

/* ═══════════════════════════════════════════════════════════════════
 * 1) /quality/dashboard — Dashboard de Qualidade (modo Pro)
 * ═══════════════════════════════════════════════════════════════════ */

const DASH_SLUG = 'quality-dashboard'

const DASH_SUMMARY = {
  summary: {
    pieces_total: 342,
    ok_pct: 94.7,
    nok_count: 18,
    rework_active: 3,
    stations_active: 3,
    stations_total: 4,
  },
  updated_at: minsAgo(0),
}

const DASH_STATIONS = {
  stations: [
    {
      id: 'st-001', station_code: 'bench_a', name: 'Bancada A — Montagem',
      camera_ids: ['cam-01', 'cam-02'], online: true,
      operator: { id: 'op-01', name: 'José Carlos Menezes' },
      active_piece: {
        op: 'OP-2026-0142', code: 'PC-88412', product_type: 'Chicote 12V',
        status: 'validating_v1', status_label: 'V1 Analisando', started_at: minsAgo(2),
      },
      shift_stats: { ok: 148, nok: 6 }, status: 'ok',
    },
    {
      id: 'st-002', station_code: 'bench_b', name: 'Bancada B — Acabamento',
      camera_ids: ['cam-03'], online: true,
      operator: { id: 'op-02', name: 'Marina Duarte' },
      active_piece: {
        op: 'OP-2026-0139', code: 'PC-88377', product_type: 'Chicote 24V',
        status: 'validating_v3', status_label: 'V3 Analisando', started_at: minsAgo(14),
      },
      shift_stats: { ok: 121, nok: 9 }, status: 'warning',
    },
    {
      id: 'st-003', station_code: 'bench_c', name: 'Bancada C — Retrabalho',
      camera_ids: ['cam-04'], online: true,
      operator: { id: 'op-03', name: 'Antônio Ferreira Lima' },
      active_piece: {
        op: 'OP-2026-0142', code: 'PC-88401', product_type: 'Chicote 12V',
        status: 'rework_v2', status_label: 'Retrabalho V2', started_at: minsAgo(27),
      },
      shift_stats: { ok: 64, nok: 3 }, status: 'critical',
    },
    {
      id: 'st-004', station_code: 'bench_d', name: 'Bancada D — Embalagem',
      camera_ids: [], online: false,
      operator: null, active_piece: null,
      shift_stats: { ok: 0, nok: 0 }, status: 'offline',
    },
  ],
  updated_at: minsAgo(0),
}

const DASH_SUMMARY_VAZIO = {
  summary: {
    pieces_total: 0, ok_pct: 0, nok_count: 0,
    rework_active: 0, stations_active: 0, stations_total: 0,
  },
  updated_at: minsAgo(0),
}

test('quality-dashboard — default (rico, 4 estações)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/quality/dashboard/summary': DASH_SUMMARY,
      '**/api/v1/quality/dashboard/stations': DASH_STATIONS,
    },
  })
  await gotoAudit(page, '/quality/dashboard')
  await page.getByText('Dashboard de Qualidade').waitFor()
  await page.getByText('Bancada A — Montagem').waitFor()
  await settle(page)
  await shootBothThemes(page, DASH_SLUG, 'default', true)
})

test('quality-dashboard — empty (sem estações)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/quality/dashboard/summary': DASH_SUMMARY_VAZIO,
      '**/api/v1/quality/dashboard/stations': { stations: [], updated_at: minsAgo(0) },
    },
  })
  await gotoAudit(page, '/quality/dashboard')
  await page.getByText('Nenhuma estação configurada.').waitFor()
  await settle(page)
  await shootBothThemes(page, DASH_SLUG, 'empty', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 2) /quality/cameras — Câmeras do módulo Qualidade
 * ═══════════════════════════════════════════════════════════════════ */

const CAM_SLUG = 'quality-cameras'

const mkCam = (id: string, name: string, extra: Record<string, unknown> = {}) => ({
  id, name, rtsp_url: '', active_module: 'quality',
  model_quality_id: null, is_setup_mode: false,
  production_order: null, product_type: null,
  reference_snapshot_r2_key: null, created_at: daysAgo(30),
  ...extra,
})

const CAMS_ASSIGNED = {
  cameras: [
    mkCam('cam-01', 'Câmera Bancada A — Overview', {
      production_order: 'OP-2026-0142', product_type: 'Chicote 12V',
      model_quality_id: 'mdl-quality-v4',
    }),
    mkCam('cam-02', 'Câmera Bancada A — Closeup', {
      production_order: 'OP-2026-0142', product_type: 'Chicote 12V',
      is_setup_mode: true,
    }),
    mkCam('cam-03', 'Câmera Bancada B — Overview', {
      production_order: 'OP-2026-0139', product_type: 'Chicote 24V',
      model_quality_id: 'mdl-quality-v4',
    }),
    mkCam('cam-04', 'Câmera Pátio Norte — Retrabalho'),
  ],
}

const CAMS_AVAILABLE = {
  cameras: [
    mkCam('cam-08', 'Câmera Doca 3 — Expedição', { active_module: null }),
    mkCam('cam-09', 'Câmera Linha 2 — Solda', { active_module: null }),
    mkCam('cam-10', 'Câmera Almoxarifado', { active_module: null }),
  ],
}

async function gotoCamerasRich(page: Page) {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/quality/cameras': CAMS_ASSIGNED,
      '**/api/v1/quality/cameras/available': CAMS_AVAILABLE,
    },
  })
  await gotoAudit(page, '/quality/cameras')
  await page.getByText('Câmeras — Módulo Qualidade').waitFor()
  await page.getByText('Câmera Bancada A — Overview').waitFor()
  await settle(page)
}

test('quality-cameras — default (4 atribuídas + 3 disponíveis)', async ({ page }) => {
  await gotoCamerasRich(page)
  await shootBothThemes(page, CAM_SLUG, 'default', true)
})

test('quality-cameras — edit-config (form inline de OP/tipo de peça)', async ({ page }) => {
  await gotoCamerasRich(page)
  await page.getByRole('button', { name: 'Editar config' }).first().click()
  await page.getByPlaceholder('Ordem de produção').waitFor()
  await page.getByPlaceholder('Ordem de produção').fill('OP-2026-0155')
  await page.getByPlaceholder('Tipo de peça').fill('Chicote 48V blindado')
  await settle(page, 400)
  await shootBothThemes(page, CAM_SLUG, 'edit-config', true)
})

test('quality-cameras — empty (nenhuma câmera)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/quality/cameras': { cameras: [] },
      '**/api/v1/quality/cameras/available': { cameras: [] },
    },
  })
  await gotoAudit(page, '/quality/cameras')
  await page.getByText('Nenhuma câmera atribuída').waitFor()
  await settle(page)
  await shootBothThemes(page, CAM_SLUG, 'empty', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 3) /quality/inspections — Inspeções (MODO DEMONSTRAÇÃO, sem API)
 * ═══════════════════════════════════════════════════════════════════ */

const INSP_SLUG = 'quality-inspections'

async function gotoInspections(page: Page) {
  await setupApp(page)
  await gotoAudit(page, '/quality/inspections')
  await page.getByText('MODO DEMONSTRAÇÃO').waitFor()
  // 'Linha A — Frontal' também existe como <option> oculto no filtro — ancorar na tabela
  await page.locator('tbody tr').first().waitFor()
  await settle(page)
}

test('quality-inspections — default (tabela demo com 200 registros)', async ({ page }) => {
  await gotoInspections(page)
  await shootBothThemes(page, INSP_SLUG, 'default', true)
})

test('quality-inspections — empty (filtro sem resultado)', async ({ page }) => {
  await gotoInspections(page)
  await page.getByPlaceholder('Ordem de produção').fill('ORDEM-INEXISTENTE-999')
  await page.getByText('Nenhuma inspeção encontrada.').waitFor()
  await settle(page, 400)
  await shootBothThemes(page, INSP_SLUG, 'empty', true)
})

test('quality-inspections — modal-feedback-drawer (painel lateral)', async ({ page }) => {
  await gotoInspections(page)
  await page.locator('td[title="Clique para registrar feedback"]').first().click()
  await page.getByText('Feedback de Inspeção').waitFor()
  await page
    .getByPlaceholder('Observações sobre esta inspeção…')
    .fill('Defeito confirmado na conferência manual — arranhão visível na lateral esquerda.')
  await settle(page, 400)
  await shootBothThemes(page, INSP_SLUG, 'modal-feedback-drawer')
})

/* ═══════════════════════════════════════════════════════════════════
 * 4) /quality/pieces — Peças (Quality Gate RVB)
 * ═══════════════════════════════════════════════════════════════════ */

const PIECE_SLUG = 'quality-pieces'

const mkPiece = (
  id: string, piece_number: string, status: string,
  extra: Record<string, unknown> = {}
) => ({
  id, piece_number, work_order: 'OP-2026-0142', product_type: 'Chicote 12V',
  status, current_station: 'bench_a', operator_id: 'José C. Menezes',
  started_at: hoursAgo(3), completed_at: null,
  total_rework_count: 0, total_rework_time_seconds: 0,
  photo_quality_path: null, photo_quality_r2_key: null,
  wiser_exported: false, wiser_exported_at: null,
  created_at: hoursAgo(3), updated_at: minsAgo(5),
  ...extra,
})

const PIECES = [
  mkPiece('p-001', 'PC-88412', 'validating_v1', { started_at: minsAgo(4) }),
  mkPiece('p-002', 'PC-88409', 'rework_v2', {
    total_rework_count: 2, total_rework_time_seconds: 480, started_at: minsAgo(38),
  }),
  mkPiece('p-003', 'PC-88405', 'waiting_bench_b', { started_at: hoursAgo(1) }),
  mkPiece('p-004', 'PC-88398', 'approved', {
    completed_at: hoursAgo(1), wiser_exported: true, wiser_exported_at: hoursAgo(1),
    started_at: hoursAgo(2), current_station: 'bench_b',
    operator_id: 'Marina Duarte',
  }),
  mkPiece('p-005', 'PC-88391', 'rejected', {
    completed_at: hoursAgo(2), total_rework_count: 3, total_rework_time_seconds: 1240,
    started_at: hoursAgo(4), work_order: 'OP-2026-0139', product_type: 'Chicote 24V',
  }),
  mkPiece('p-006', 'PC-88387', 'identified', {
    started_at: minsAgo(1), work_order: 'OP-2026-0139', product_type: 'Chicote 24V',
  }),
  mkPiece('p-007', 'PC-88380', 'approved', {
    completed_at: hoursAgo(3), started_at: hoursAgo(5),
    total_rework_count: 1, total_rework_time_seconds: 190,
    wiser_exported: true, wiser_exported_at: hoursAgo(3),
  }),
]

const PIECES_PAGE = { pieces: PIECES, total: PIECES.length, page: 1, per_page: 20 }

const PIECE_DETAIL = {
  piece: {
    ...mkPiece('p-002', 'PC-88409', 'rework_v2', {
      total_rework_count: 2, total_rework_time_seconds: 480, started_at: minsAgo(38),
    }),
    reworks: [
      {
        id: 'rw-001', validation_type: 'v1', defect_type: 'Fio fora do anel',
        duration_seconds: 210, attempt_number: 1,
        started_at: minsAgo(34), completed_at: minsAgo(30),
      },
      {
        id: 'rw-002', validation_type: 'v2', defect_type: 'Saída sem isolamento',
        duration_seconds: 270, attempt_number: 2,
        started_at: minsAgo(18), completed_at: minsAgo(13),
      },
    ],
  },
}

async function gotoPiecesRich(page: Page) {
  await setupApp(page, {
    fixtures: {
      // '*' não cruza '/' → lista (com querystring) sem colidir com o detalhe
      '**/api/v1/quality/gate/pieces*': PIECES_PAGE,
      '**/api/v1/quality/gate/pieces/*': PIECE_DETAIL,
    },
  })
  await gotoAudit(page, '/quality/pieces')
  await page.getByText('Peças — Quality Gate').waitFor()
  await page.getByText('PC-88412').waitFor()
  await settle(page)
}

test('quality-pieces — default (7 peças, status variados)', async ({ page }) => {
  await gotoPiecesRich(page)
  await shootBothThemes(page, PIECE_SLUG, 'default', true)
})

test('quality-pieces — expanded-detalhe (drill-down com retrabalhos)', async ({ page }) => {
  await gotoPiecesRich(page)
  await page.getByText('PC-88409').click()
  await page.getByText('Retrabalhos (2)').waitFor()
  await settle(page, 400)
  await shootBothThemes(page, PIECE_SLUG, 'expanded-detalhe', true)
})

test('quality-pieces — empty (sem peças)', async ({ page }) => {
  await setupApp(page, {
    fixtures: {
      '**/api/v1/quality/gate/pieces*': { pieces: [], total: 0, page: 1, per_page: 20 },
    },
  })
  await gotoAudit(page, '/quality/pieces')
  await page.getByText('Nenhuma peça encontrada com os filtros aplicados.').waitFor()
  await settle(page)
  await shootBothThemes(page, PIECE_SLUG, 'empty', true)
})

/* ═══════════════════════════════════════════════════════════════════
 * 5) /quality/config — Configurações do Quality Gate
 * ═══════════════════════════════════════════════════════════════════ */

const CFG_SLUG = 'quality-config'

const CFG_STATIONS = {
  stations: [
    {
      id: 'st-001', station_code: 'bench_a', name: 'Bancada A — Montagem',
      overview_camera_id: 'a1b2c3d4-0001-4bcd-9e01-camera000001',
      closeup_camera_id: 'a1b2c3d4-0002-4bcd-9e01-camera000002',
      tower_controller_type: 'gpio', is_active: true,
    },
    {
      id: 'st-002', station_code: 'bench_b', name: 'Bancada B — Acabamento',
      overview_camera_id: 'a1b2c3d4-0003-4bcd-9e01-camera000003',
      closeup_camera_id: null,
      tower_controller_type: 'modbus', is_active: false,
    },
  ],
}

async function gotoConfigRich(page: Page) {
  await setupApp(page, {
    fixtures: { '**/api/v1/quality/gate/stations': CFG_STATIONS },
  })
  await gotoAudit(page, '/quality/config')
  await page.getByText('Configurações — Quality Gate').waitFor()
  await page.getByText('Bancada A — V1 e V2').waitFor()
  await settle(page)
}

test('quality-config — default (2 bancadas)', async ({ page }) => {
  await gotoConfigRich(page)
  await shootBothThemes(page, CFG_SLUG, 'default', true)
})

test('quality-config — modal-adicionar-estacao', async ({ page }) => {
  await gotoConfigRich(page)
  await page.getByRole('button', { name: '+ Adicionar estação' }).click()
  await page.getByText('Adicionar estação', { exact: true }).waitFor()
  await page.getByPlaceholder('Ex: Bancada A').fill('Bancada C — Inspeção Final')
  await page.getByPlaceholder('Ex: bench_a').fill('bench_c')
  await settle(page, 400)
  await shootBothThemes(page, CFG_SLUG, 'modal-adicionar-estacao')
})

test('quality-config — empty (nenhuma estação)', async ({ page }) => {
  await setupApp(page, {
    fixtures: { '**/api/v1/quality/gate/stations': { stations: [] } },
  })
  await gotoAudit(page, '/quality/config')
  await page.getByText('Nenhuma estação configurada.').waitFor()
  await settle(page)
  await shootBothThemes(page, CFG_SLUG, 'empty', true)
})
