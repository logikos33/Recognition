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
 * F5-LEVE (tema não pode estourar): três capturas do Vitor mostraram uma
 * FAIXA BRANCA (não roxa) em `/novo/epi/cameras`, em ações/eventos e no
 * Estúdio — causa raiz era o `body` sem fundo em `styles/global.css.ts` (o
 * arquivo REALMENTE importado por `main.tsx`; um `index.css` solto no
 * mesmo diretório nunca chegou a ser importado — código morto, não a causa).
 * A régua original só amostrava o centro/quadrantes sem rolar e sem viewport
 * grande, e por isso não pegou. Reforçada abaixo (itens a–c).
 *
 * O QUE É MEDIDO, POR ROTA (`ROTAS_NOVAS` + `ROTAS_NOVAS_SEM_SHELL`, a
 * MESMA lista que roteia o produto — se uma tela nova entrar lá, entra aqui
 * de graça), em duas passadas de viewport (padrão e 1440×2200):
 *
 *   (a) `getComputedStyle(document.body).backgroundColor` não é branco nem
 *       transparente — pega a regressão DIRETO na fonte, mesmo em rota cujo
 *       próprio conteúdo já cobre o viewport inteiro (onde os pontos abaixo
 *       não veriam diferença nenhuma).
 *   (a2) o fundo EFETIVO em 5 pontos do viewport (centro + 4 quadrantes) é
 *       ESCURO. `document.elementFromPoint` + andar pelos `parentElement`
 *       até achar um `background-color` opaco — achar "nenhum bg opaco em
 *       lugar nenhum" É a falha (luminância relativa < 0.25 é o piso).
 *   (b) depois de `window.scrollTo(0, document.body.scrollHeight)`, os
 *       mesmos 5 pontos MAIS 3 no rodapé (fy=0.97) são reamostrados — é a
 *       faixa de overscroll/fim de página que rolar até o fim revela.
 *   (c) tudo acima roda de novo com viewport 1440×2200 (`test.use`, describe
 *       separado) — conteúdo curto numa tela grande é o caso que mais
 *       revela o branco, já que sobra área abaixo do conteúdo real.
 *   (d) nenhum elemento VISÍVEL (área > 0 dentro do viewport) tem
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

interface Medicao {
  amostras: Amostra[]
  roxos: string[]
  /** F5-LEVE (tema não pode estourar): fundo EFETIVO de `document.body`, não
   * o walk-up por `elementFromPoint` — pega direto a regressão de
   * `styles/global.css.ts` mesmo em rota cujo próprio conteúdo já cobre
   * 100% do viewport (onde os `amostras` acima não veriam diferença). */
  bodyBg: string
  bodyEscuro: boolean
}

/** Roda NO BROWSER (page.evaluate) — não dá pra reusar função Node aqui.
 * `extras`: pontos normalizados (fx,fy) adicionais, além dos 5 padrão —
 * usado pro rodapé, depois de rolar até o fim. */
function medir(extras: Array<[number, number]> = []): Medicao {
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
    ...extras,
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

  const bodyBg = getComputedStyle(document.body).backgroundColor
  const corBody = parseRgb(bodyBg)
  const bodyEscuro = corBody !== null && corBody.a > 0.5 && luminancia(corBody) < 0.25

  return { amostras, roxos, bodyBg, bodyEscuro }
}

/** Node-side: falha com a rota, a fase (sem rolar / rolado / viewport alta) e
 * o dado bruto na mensagem — é o que aparece no CI quando a régua trava. */
function afirmarMedicao(rota: string, fase: string, m: Medicao) {
  expect(
    m.bodyEscuro,
    `${rota} (${fase}): body background-color é "${m.bodyBg}" — nem escuro nem opaco (branco padrão do navegador vazando)`,
  ).toBe(true)
  for (const a of m.amostras) {
    expect(
      a.escuro,
      `${rota} (${fase}): ponto (${a.x},${a.y}) NÃO está escuro — cor efetiva ${JSON.stringify(a.cor)}`,
    ).toBe(true)
  }
  expect(m.roxos, `${rota} (${fase}): roxo do tema legado encontrado —\n${m.roxos.join('\n')}`).toEqual([])
}

/** Os 3 pontos extras do rodapé, amostrados DEPOIS de rolar até o fim —
 * fy=0.97 fica colado na borda inferior do viewport sem cair fora dele. */
const PONTOS_RODAPE: Array<[number, number]> = [
  [0.25, 0.97],
  [0.5, 0.97],
  [0.75, 0.97],
]

test.describe('identidade — fundo escuro e zero roxo do tema legado', () => {
  for (const rota of ROTAS) {
    test(`${rota}`, async ({ page }) => {
      await entrarComoSuperadmin(page)
      await registrarMocksExtras(page, rota)
      await page.goto(rota)
      // Rede toda mockada e resolvida na hora — a folga é só pro React
      // montar (Suspense do lazy() + primeiro efeito de cada tela).
      await page.waitForTimeout(700)

      afirmarMedicao(rota, 'sem rolar', await page.evaluate(medir))

      // (b) rola até o fim e reamostra os 5 pontos padrão + 3 no rodapé —
      // é a faixa branca do overscroll/fim de página que o teste original
      // (sem rolar, sem rodapé) nunca alcançava.
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
      await page.waitForTimeout(100)
      afirmarMedicao(rota, 'rolado até o fim', await page.evaluate(medir, PONTOS_RODAPE))
    })
  }
})

test.describe('identidade — viewport alta (1440×2200, conteúdo curto revela o branco)', () => {
  // Tela grande + conteúdo curto = a área que sobra abaixo do conteúdo é
  // exatamente onde o branco padrão do navegador aparecia — o caso mais
  // direto pra pegar uma regressão em `styles/global.css.ts`.
  test.use({ viewport: { width: 1440, height: 2200 } })

  for (const rota of ROTAS) {
    test(`${rota}`, async ({ page }) => {
      await entrarComoSuperadmin(page)
      await registrarMocksExtras(page, rota)
      await page.goto(rota)
      await page.waitForTimeout(700)
      afirmarMedicao(rota, 'viewport alta', await page.evaluate(medir))
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

  /**
   * F5-LEVE (identidade, rodada 2): as réguas acima só visitam rota em
   * ESTADO NORMAL — nenhuma nunca abriu modal/dropdown/popover, então nunca
   * inspecionaram o que um `Dialog.Portal`/`Popover.Portal` do Radix (Modal,
   * ConfirmDialog, CameraFilterSelector) monta fora da árvore de `.raiz`
   * (anexado a `document.body`) — exatamente onde `paletaLkSobreTemaLegado`
   * (Shell.css.ts) não alcançava antes desta rodada. Este teste ABRE essas
   * camadas de verdade (achado do Vitor: "Arquivar câmera" saía roxo) — é a
   * prova de que a régua agora INSPECIONA o portal, não só a rota estática.
   */
  test('Camadas flutuantes (modal, popover) via Portal saem ciano, não roxo', async ({ page }) => {
    await entrarComoSuperadmin(page)
    // Mais específico DEPOIS do catch-all — mesmo motivo do teste do live view.
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

    await page.goto('/novo/epi/cameras')

    // "Adicionar câmera" (CameraOnboardingWizard, dentro de `Modal`/
    // `Dialog.Portal`) — o disparo mais barato: sem seleção prévia, só a
    // permissão de superadmin que a fixture já concede.
    await page.getByRole('button', { name: 'Adicionar câmera' }).click()
    const dialogoAdicionar = page.getByRole('dialog')
    await expect(dialogoAdicionar).toBeVisible({ timeout: 10_000 })
    const proximo = dialogoAdicionar.getByRole('button', { name: /Próximo/ })
    const corProximo = await proximo.evaluate((el) => getComputedStyle(el).backgroundColor)
    expect(corProximo, `botão "Próximo" do modal saiu ${corProximo} — família roxa do tema legado`).toBe('rgb(0, 229, 255)')
    let m = await page.evaluate(medir)
    expect(m.roxos, `roxo do tema legado com o modal de cadastro aberto —\n${m.roxos.join('\n')}`).toEqual([])
    await dialogoAdicionar.getByRole('button', { name: 'Fechar' }).click()
    await expect(dialogoAdicionar).toBeHidden()

    // ConfirmDialog "Arquivar câmera" — a evidência ORIGINAL do Vitor (botão
    // "Arquivar" saindo roxo). Mesma família de componente (`Modal`), gatilho
    // diferente: exige uma câmera já selecionada (a primeira da lista, por
    // `Cameras.tsx`).
    await page.getByRole('button', { name: 'Arquivar', exact: true }).click()
    const dialogoArquivar = page.getByRole('dialog')
    await expect(dialogoArquivar).toBeVisible({ timeout: 10_000 })
    const arquivar = dialogoArquivar.getByRole('button', { name: 'Arquivar' })
    const corArquivar = await arquivar.evaluate((el) => getComputedStyle(el).backgroundColor)
    expect(corArquivar, `botão "Arquivar" do modal saiu ${corArquivar} — família roxa do tema legado`).toBe('rgb(0, 229, 255)')
    m = await page.evaluate(medir)
    expect(m.roxos, `roxo do tema legado com o modal de arquivar aberto —\n${m.roxos.join('\n')}`).toEqual([])
    await evidencia(page, 'cameras-modal-arquivar-portal')

    // CameraFilterSelector (Popover/`Popover.Portal`) — mesma família de
    // escape (Radix Portal), mecanismo diferente do Dialog.
    await page.goto('/novo/estudio/dados')
    await page.getByRole('button', { name: 'Câmera: todas' }).click()
    const popover = page.getByRole('button', { name: 'Todas', exact: true }).last()
    await expect(popover).toBeVisible({ timeout: 10_000 })
    const corPopoverAcao = await popover.evaluate((el) => getComputedStyle(el).color)
    expect(corPopoverAcao, `ação "Todas" do popover saiu ${corPopoverAcao} — família roxa do tema legado`).toBe('rgb(0, 229, 255)')
    m = await page.evaluate(medir)
    expect(m.roxos, `roxo do tema legado com o popover de câmera aberto —\n${m.roxos.join('\n')}`).toEqual([])
    await evidencia(page, 'estudio-popover-camera')
  })
})
