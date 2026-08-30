/**
 * Régua PERMANENTE de identidade — roda no CI, sem backend real (mesmo
 * padrão auto-contido de `front-novo-perfis.spec.ts`: JWT fabricado no
 * localStorage, `**\/api/**` mockado com envelope vazio).
 *
 * POR QUE ESTE ARQUIVO EXISTE
 *
 * F5-LEVE (identidade): capturas do Vitor mostraram roxo do tema legado
 * (`professional`/`cyberpunk`, `#8b5cf6`) vazando pra dentro do shell novo
 * através de componentes compartilhados (`CameraPlayer`, `TrainingGallery`)
 * — a causa (contrato de tema antigo aplicado em `document.documentElement`,
 * cascateando pra dentro do shell) foi fechada com um remap em
 * `Shell.css.ts` (`paletaLkSobreTemaLegado`), mas aquele PR só provou o
 * remap na FONTE (o objeto `assignVars`), não o PRODUTO MONTADO — e é
 * exatamente esse buraco (unidade prova a peça, não a composição) que já
 * causou o vazamento original (10 links absolutos que só um teste no
 * produto real pegou, ver `coexistencia.test.tsx`).
 *
 * O QUE É MEDIDO, POR ROTA (`ROTAS_NOVAS` + `ROTAS_NOVAS_SEM_SHELL`, a
 * MESMA lista que roteia o produto — se uma tela nova entrar lá, entra aqui
 * de graça):
 *
 *   (a) o fundo EFETIVO em 5 pontos do viewport (centro + 4 quadrantes) é
 *       ESCURO. `document.elementFromPoint` + andar pelos `parentElement`
 *       até achar um `background-color` opaco — o `body` é transparente
 *       (`index.css` não pinta), então achar "nenhum bg opaco em lugar
 *       nenhum" É a falha (luminância relativa < 0.25 é o piso).
 *   (b) nenhum elemento VISÍVEL (área > 0 dentro do viewport) tem
 *       `background-color` computado na faixa roxa do tema legado
 *       (heurística: r 80–180, b>150, g<100 — cobre `#8b5cf6`/`#a78bfa`/
 *       `#7c3aed`, longe de qualquer token `lk` real).
 */
import { expect, test, type Page } from '@playwright/test'
import type { ReactElement } from 'react'

import { PREFIXO_NOVO, ROTAS_NOVAS, ROTAS_NOVAS_SEM_SHELL } from '../../app/RotasNovas'

/**
 * Constrói as URLs navegáveis a partir da MESMA árvore de rotas do produto —
 * concatenando `path` de pai→filho (`estudio` + `cobertura` = `estudio/cobertura`)
 * e pulando rotas `index` (sem `path` próprio: o pai já cobre a URL).
 * `ROTAS_NOVAS` é relativa ao prefixo; `ROTAS_NOVAS_SEM_SHELL` já vem absoluta.
 */
function caminhosDe(elementos: ReactElement[], baseInicial: string): string[] {
  const out: string[] = []
  const anda = (el: ReactElement, baseAtual: string) => {
    const props = el.props as { path?: unknown; children?: unknown }
    let proximaBase = baseAtual
    if (typeof props.path === 'string') {
      const completo = props.path.startsWith('/') ? props.path : `${baseAtual}/${props.path}`
      out.push(completo)
      proximaBase = completo
    }
    const filhos = props.children
    if (Array.isArray(filhos)) filhos.forEach((f) => anda(f as ReactElement, proximaBase))
    else if (filhos) anda(filhos as ReactElement, proximaBase)
  }
  elementos.forEach((el) => anda(el, baseInicial))
  return out
}

/** `:cameraId`, `:tenantId`, `:station`, `:id` → um id fake só pra montar a tela. */
const ROTAS = [
  ...caminhosDe(ROTAS_NOVAS, PREFIXO_NOVO),
  ...caminhosDe(ROTAS_NOVAS_SEM_SHELL, ''),
].map((p) => p.replace(/:[^/]+/g, 'e2e-fake'))

async function entrarComoSuperadmin(page: Page) {
  const exp = Math.floor(Date.now() / 1000) + 3600
  const b64 = (o: unknown) => Buffer.from(JSON.stringify(o)).toString('base64').replace(/=+$/, '')
  const token = `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64({ exp })}.assinatura-de-teste`
  await page.addInitScript(
    ([token]) => {
      localStorage.setItem('token', token as string)
      localStorage.setItem(
        'user',
        JSON.stringify({
          id: 'u-teste',
          email: 'superadmin@teste.local',
          name: 'Teste Superadmin',
          role: 'superadmin',
          tenant_id: '00000000-0000-0000-0000-000000000001',
          tenant_schema: 'teste',
          modules: ['ppe', 'quality', 'fueling'],
          permissions: [],
        }),
      )
    },
    [token] as const,
  )
  // Sem backend: superadmin passa por cima de toda permissão (useAuth.can) —
  // o que sobra pra montar cada tela é só o dado, e vazio honesto é dado
  // válido pra medir cor de fundo (o conteúdo NÃO é o que este arquivo mede).
  await page.route('**/api/**', (rota) =>
    rota.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, message: 'OK', data: {} }),
    }),
  )
}

/**
 * Endpoints cujo shape REAL não é um objeto vazio (é array direto, ou tem um
 * campo aninhado sem guarda completa a jusante) — sem isto o React CRASHA
 * (não há error boundary, a árvore some inteira) e o teste de cor nem chega
 * a rodar. Achado DESTA régua (as telas nunca foram exercitadas de ponta a
 * ponta sem backend real) — mock aqui, não conserto de produto: o backend de
 * verdade nunca manda `{}` puro pra estes endpoints.
 */
const DASHBOARD_ADMIN_ZERO = {
  tenants_active: 0, users_total: 0, cameras_online: 0, alerts_24h: 0,
  training_approvals_pending: 0, tickets_open: 0, mrr_estimated: 0,
  workers: { online: 0, fallback: 0, offline: 0 },
  recent_critical_events: [], top_tenants_users: [],
}
const COVERAGE_MATRIX_ZERO = {
  targets: { images_per_class: 0, cameras_per_class: 0, max_camera_share: 0, floor_images: 0, floor_cameras: 0 },
  totals: {
    boxes: 0, images: 0, boxes_in_rows: 0, rows_match_export: true, cameras_total: 0,
    cameras_active: 0, cameras_with_annotation: 0, classes_met: 0, classes_active: 0,
  },
  classes: [], cameras: [], matrix: [], gaps: [], needs_collection: [], imbalance: null,
  warnings: { orphan_boxes: 0, orphans: [], archived_excluded: [] },
}

const ROTA_PARA_MOCKS_EXTRA: Record<string, Array<[string, unknown]>> = {
  '/novo/admin': [['**/api/v1/admin/dashboard', DASHBOARD_ADMIN_ZERO]],
  '/novo/admin/usuarios': [
    ['**/api/v1/admin/tenants', { tenants: [] }],
    ['**/api/v1/admin/users**', { items: [], total: 0 }],
  ],
  '/novo/admin/auditoria': [['**/api/v1/admin/audit-log**', { items: [], total: 0 }]],
  '/novo/estudio/cobertura': [['**/api/training/coverage-matrix', COVERAGE_MATRIX_ZERO]],
  '/novo/estudio/modelo': [['**/api/training/models', []]],
  '/novo/estudio/modelos-por-camera': [
    ['**/api/v1/models', { models: [] }],
    // `classesCatalogo` (fallback de nomes) precisa ser ARRAY — `{}` não é.
    ['**/api/classes', []],
  ],
  '/novo/estudio/treino': [['**/api/training/jobs', []]],
  '/novo/quality/gestao': [
    ['**/api/v1/quality/dashboard/summary', {
      summary: { pieces_total: 0, ok_pct: 0, nok_count: 0, rework_active: 0, stations_active: 0, stations_total: 0 },
    }],
    ['**/api/v1/quality/dashboard/stations', { stations: [] }],
    ['**/api/v1/quality/gate/stats/rework', {
      stats: { by_validation: {}, avg_rework_duration_seconds: 0, most_common_defect: null },
    }],
    ['**/api/v1/quality/defect-categories', { categories: [] }],
    // Renderiza a "Fila de revisão" com `insp &&` — `{}` é truthy e passa
    // pelo guard, e as leituras internas (`insp.pending_feedback`, ...) não
    // têm `?.` (o guard é o único, e falso-positiva com objeto vazio).
    ['**/api/v1/quality/inspections/summary**', {
      total: 0, ok: 0, nok: 0, nok_rate: 0, pending_feedback: 0, confirmed: 0,
      rejected: 0, retrain_requested: 0, cep_alerts_count: 0, defect_distribution: {},
    }],
  ],
}

/** Registrados DEPOIS do catch-all (`entrarComoSuperadmin`) — Playwright resolve
 * do último `page.route` registrado pro primeiro, então estes ganham. */
async function registrarMocksExtras(page: Page, rota: string) {
  for (const [glob, data] of ROTA_PARA_MOCKS_EXTRA[rota] ?? []) {
    await page.route(glob, (r) =>
      r.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data }),
      }),
    )
  }
}

interface Amostra {
  x: number
  y: number
  cor: { r: number; g: number; b: number; a: number } | null
  escuro: boolean
}

/** Roda NO BROWSER (page.evaluate) — não dá pra reusar função Node aqui. */
function medir() {
  const parseRgb = (c: string) => {
    const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?/.exec(c)
    if (!m) return null
    return {
      r: Number(m[1]),
      g: Number(m[2]),
      b: Number(m[3]),
      a: m[4] === undefined ? 1 : Number(m[4]),
    }
  }
  const luminancia = (c: { r: number; g: number; b: number }) =>
    (0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b) / 255

  const fundoEfetivo = (x: number, y: number) => {
    let el = document.elementFromPoint(x, y) as HTMLElement | null
    while (el) {
      const cor = parseRgb(getComputedStyle(el).backgroundColor)
      if (cor && cor.a > 0.5) return cor
      el = el.parentElement
    }
    return null
  }

  const W = window.innerWidth
  const H = window.innerHeight
  const pontos: Array<[number, number]> = [
    [0.5, 0.5],
    [0.25, 0.25],
    [0.75, 0.25],
    [0.25, 0.75],
    [0.75, 0.75],
  ]
  const amostras = pontos.map(([fx, fy]) => {
    const x = Math.round(W * fx)
    const y = Math.round(H * fy)
    const cor = fundoEfetivo(x, y)
    return { x, y, cor, escuro: cor !== null && luminancia(cor) < 0.25 }
  })

  const ehRoxoLegado = (c: { r: number; g: number; b: number }) =>
    c.r >= 80 && c.r <= 180 && c.b > 150 && c.g < 100

  const roxos: string[] = []
  for (const el of Array.from(document.querySelectorAll('*'))) {
    const r = el.getBoundingClientRect()
    const vis =
      Math.max(0, Math.min(r.bottom, H) - Math.max(r.top, 0)) *
      Math.max(0, Math.min(r.right, W) - Math.max(r.left, 0))
    if (vis < 1) continue
    const cor = parseRgb(getComputedStyle(el).backgroundColor)
    if (cor && cor.a > 0.3 && ehRoxoLegado(cor)) {
      const classe = Array.from(el.classList).join('.')
      roxos.push(`${el.tagName.toLowerCase()}${classe ? `.${classe}` : ''} rgb(${cor.r},${cor.g},${cor.b})`)
    }
  }

  return { amostras, roxos }
}

test.describe('identidade — fundo escuro e zero roxo do tema legado', () => {
  for (const rota of ROTAS) {
    test(`${rota}`, async ({ page }) => {
      await entrarComoSuperadmin(page)
      await registrarMocksExtras(page, rota)
      await page.goto(rota)
      // Rede toda mockada e resolvida na hora — a folga é só pro React
      // montar (Suspense do lazy() + primeiro efeito de cada tela).
      await page.waitForTimeout(700)

      const { amostras, roxos } = await page.evaluate(medir)

      for (const a of amostras as Amostra[]) {
        expect(
          a.escuro,
          `${rota}: ponto (${a.x},${a.y}) NÃO está escuro — cor efetiva ${JSON.stringify(a.cor)}`,
        ).toBe(true)
      }
      expect(roxos, `${rota}: roxo do tema legado encontrado —\n${roxos.join('\n')}`).toEqual([])
    })
  }
})

test.describe('evidência visual (F5-LEVE, rodada única)', () => {
  /**
   * Grava PNG só se `EVIDENCE_DIR` estiver setada (rodada manual do Vitor) —
   * no CI a var não existe, e o `test.step` de captura vira no-op. A
   * ASSERÇÃO de cor roda sempre, com ou sem `EVIDENCE_DIR`.
   */
  async function evidencia(page: Page, nome: string) {
    const dir = process.env.EVIDENCE_DIR
    if (!dir) return
    const { mkdirSync } = await import('node:fs')
    mkdirSync(dir, { recursive: true })
    await page.screenshot({ path: `${dir}/${nome}.png` })
  }

  test('CameraPlayer offline sob o Shell — "Reconectar" sai ciano, não roxo', async ({ page }) => {
    await entrarComoSuperadmin(page)
    // Mais específico DEPOIS do catch-all: page.route resolve do último
    // registrado pro primeiro, então o catch-all (registrado em
    // entrarComoSuperadmin) precisa perder pra estes.
    await page.route('**/api/cameras**', (rota) => {
      if (rota.request().method() !== 'GET') return rota.fallback()
      return rota.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          data: {
            cameras: [{
              id: 'cam-1', name: 'CAM-01', manufacturer: 'intelbras', host: '10.0.0.9',
              port: 554, channel: 1, is_active: true, created_at: '2026-08-01T00:00:00Z',
              location: 'DOCA', fps_target: 12, site_id: null,
            }],
          },
        }),
      })
    })
    await page.route('**/api/cameras/cam-1/stream/start', (rota) =>
      rota.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { hls_url: '/api/streams/cam-1/fake/stream.m3u8' } }),
      }),
    )
    // 404 no manifesto força o hls.js num erro FATAL de rede — o mesmo
    // caminho de "token de playback expirado" (ver useLiveView.ts) — sem
    // precisar esperar o watchdog de stall (14s).
    await page.route('**/api/streams/cam-1/fake/stream.m3u8', (rota) =>
      rota.fulfill({ status: 404, body: 'not found' }),
    )

    await page.goto('/novo/epi/live')
    const btn = page.getByRole('button', { name: 'Reconectar' })
    await expect(btn).toBeVisible({ timeout: 15_000 })
    const cor = await btn.evaluate((el) => getComputedStyle(el).backgroundColor)
    expect(cor, `botão "Reconectar" saiu ${cor} — família roxa do tema legado`).toBe('rgb(0, 229, 255)')
    await evidencia(page, 'camera-player-offline-shell')
  })

  test('Estúdio — chip ativo da galeria sai ciano, não roxo', async ({ page }) => {
    await entrarComoSuperadmin(page)
    await page.goto('/novo/estudio/dados')
    // Chip "Todas" (status) nasce ATIVO por padrão (`statusFilter = 'todos'`
    // é o estado inicial de `TrainingGallery`) — não precisa de clique.
    // `exact: true`: sem isto, "Câmera: todas" (o seletor de câmera, sempre
    // transparente) também bate por substring e `.first()` pega ele, não o chip.
    const chip = page.getByRole('button', { name: 'Todas', exact: true }).first()
    await expect(chip).toBeVisible({ timeout: 10_000 })
    const cor = await chip.evaluate((el) => getComputedStyle(el).backgroundColor)
    expect(cor, `chip ativo saiu ${cor} — família roxa do tema legado`).toBe('rgb(0, 145, 173)')
    await evidencia(page, 'estudio-chip-ativo-galeria')
  })
})
