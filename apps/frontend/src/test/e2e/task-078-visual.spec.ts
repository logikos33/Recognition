/**
 * Task-078 — evidência visual do detalhe do alerta.
 * Era um modal com fundo `#1a1d23`/`#ef4444` cru; virou tokens do tema e
 * depois virou a PÁGINA /epi/alerts/:alertId (deep-link do evento), que
 * desenha a bbox real sobre o frame inteiro em vez da caixa hardcoded.
 *
 * PR-B (30/08, pré-flip): `EpiAlerts.tsx`/`AlertDetailPage.tsx` foram
 * demolidas; `/epi/alerts` agora REDIRECIONA (client-side) para
 * `/novo/epi/eventos` — `page.goto('/epi/alerts')` segue o redirect sozinho.
 * A lista virou `app/epi/Eventos.tsx` (exige a permissão `alerts:read`, WS7 —
 * a tela antiga não tinha esse gate) e o detalhe virou `app/epi/EventoDetalhe.tsx`
 * (`<h1>Evento #...</h1>`, não mais "Detalhe do Alerta"). A navegação agora é
 * pelo link "Abrir →" de cada linha — a linha inteira não é mais clicável.
 * Recuperação: `git show
 * archive/front-antigo-epi-lote1-2026-08-30:apps/frontend/src/pages/epi/AlertDetailPage.tsx`.
 *
 * Não faz asserções funcionais: captura screenshots antes/depois da correção
 * visual (tokens WS1). Controle do prefixo via env SHOT_PREFIX=before|after.
 *
 * Uso:
 *   SHOT_PREFIX=before npx playwright test task-078-visual
 *   SHOT_PREFIX=after  npx playwright test task-078-visual
 */
import { test, type Page } from '@playwright/test'
import * as path from 'node:path'
import * as fs from 'node:fs'

const PREFIX = process.env.SHOT_PREFIX ?? 'after'
const OUT_DIR =
  process.env.EVIDENCE_DIR ??
  path.resolve(process.cwd(), '../../docs/quality/evidence/task-078')

const ALERT = {
  id: 'a1',
  camera_id: 'cam-1',
  camera_name: 'Câmera Pátio',
  violations: [{ class: 'no_helmet', confidence: 0.92 }],
  acknowledged: false,
  created_at: new Date().toISOString(),
}

async function setupRoutes(page: Page) {
  await page.route('**/api/**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: {} }),
    })
  )

  await page.route('**/alerts?**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        data: { alerts: [ALERT], total: 1, page: 1, per_page: 20, pages: 1 },
      }),
    })
  )

  // O modal foi substituído pela página /epi/alerts/:alertId (deep-link do
  // evento) — o clique na linha agora navega e busca o DETALHE, não o snapshot.
  await page.route('**/alerts/a1', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { alert: { ...ALERT, captured_at: ALERT.created_at, evidence_url: null } },
      }),
    })
  )

  await page.addInitScript(() => {
    localStorage.setItem('token', 'fake-jwt-token')
    localStorage.setItem(
      'user',
      JSON.stringify({
        email: 'test@test.com',
        role: 'admin',
        full_name: 'Test Admin',
        permissions: ['alerts:read'],
      })
    )
  })
}

async function shoot(page: Page, name: string) {
  fs.mkdirSync(OUT_DIR, { recursive: true })
  await page.screenshot({ path: path.join(OUT_DIR, `${PREFIX}-${name}.png`), fullPage: false })
}

test.describe('task-078 evidência visual — detalhe do evento', () => {
  test('Eventos — navega para o detalhe pelo link "Abrir →"', async ({ page }) => {
    await setupRoutes(page)
    await page.goto('/epi/alerts')
    await page.getByText('Câmera Pátio').first().waitFor({ state: 'visible' })
    await page.getByRole('link', { name: 'Abrir →' }).click()
    await page.getByRole('heading', { name: /^Evento #/ }).waitFor({ state: 'visible' })
    await page.waitForTimeout(400)
    await shoot(page, 'alert-detail')
  })
})
