/**
 * SOAK do live view — caça ao congelamento 04/08.
 *
 * Mede no CLIENTE (a verdade está no navegador, não no servidor):
 *   - `<video>.currentTime` de cada player, 1 amostra/s — quando ele para de
 *     avançar, é o congelamento;
 *   - status HTTP de cada request de /stream/ (m3u8, .ts, start) — o instante
 *     exato do primeiro 401/404/410;
 *   - a URL da página a cada amostra — o instante em que o app decide ir
 *     para /login (a falha terminal do bug original).
 *
 * A duração vem de SOAK_MINUTES e deve cobrir ≥3× o TTL do token de playback
 * em vigor no backend (HLS_PLAYBACK_TOKEN_TTL) — foi um soak mais curto que o
 * TTL que deixou três rodadas anteriores passarem "limpas" com o bug vivo.
 *
 * Aceite (falha o teste se violar):
 *   1. NUNCA navega para /login;
 *   2. ZERO respostas 401 em /stream/;
 *   3. cada player TOCA (>60s reproduzidos) e a MAIOR janela sem mudança de
 *      currentTime fica abaixo de SOAK_MAX_STALL_S (default 45s). Mudança
 *      inclui o reset de timeline da renovação (loadSource re-assinado) —
 *      congelamento real é ct idêntico por segundos seguidos.
 *
 * Pré-requisitos (ver scripts/soak_liveview/README.md): API local com TTL
 * curto, Redis com câmeras sintéticas (synthetic_edge.py), usuário seedado.
 *
 * Rodar: SOAK_PASSWORD=... npx playwright test soak-liveview --timeout=0
 */
import { expect, test } from '@playwright/test'
import * as fs from 'node:fs'

const MIN = 60_000
const SOAK_MINUTES = Number(process.env.SOAK_MINUTES ?? '40')
const SOAK_MAX_STALL_S = Number(process.env.SOAK_MAX_STALL_S ?? '45')
const EMAIL = process.env.SOAK_EMAIL ?? 'admin@recognition.dev'
const PASSWORD = process.env.SOAK_PASSWORD ?? ''
const OUT = process.env.SOAK_OUT ?? 'soak-liveview-timeline.jsonl'
const MONITORING_PATH = process.env.SOAK_PATH ?? '/epi/monitoring'

interface HttpEvent {
  t: number
  status: number
  url: string
}

interface Sample {
  t: number
  page: string
  videos: Array<{ ct: number; rs: number; paused: boolean }>
}

// O soak NÃO é teste de CI: precisa da stack local (API com TTL curto, Redis
// com câmeras sintéticas, seed) e de dezenas de minutos. Sem SOAK_PASSWORD ele
// SKIPA — a versão anterior falhava com expect e derrubou o job "Frontend
// tests" da develop nos merges #309/#310.
test.skip(!process.env.SOAK_PASSWORD, 'soak só roda com SOAK_PASSWORD e a stack local (ver scripts/soak_liveview/README.md)')

test('soak live view — ≥3× TTL do token sem congelamento e sem logout', async ({ page }) => {
  test.setTimeout(0)

  const http: HttpEvent[] = []
  page.on('response', (res) => {
    const url = res.url()
    if (!url.includes('/stream/') && !url.includes('/tenant-context/')) return
    http.push({
      t: Date.now(),
      status: res.status(),
      // token de playback NUNCA em log — redige o path tokenizado
      url: url.replace(/\/stream\/s\/[^/]+\//, '/stream/s/<token>/'),
    })
  })

  await page.goto('/login')
  await page.locator('input[type="email"]').fill(EMAIL)
  await page.locator('input[type="password"]').fill(PASSWORD)
  await page.locator('form button[type="submit"]').click()
  await page.waitForURL((u) => !u.pathname.includes('login'), { timeout: 30_000 })

  await page.goto(MONITORING_PATH)
  // Pelo menos um player precisa nascer e começar a andar antes do relógio do
  // soak valer — senão mediríamos "congelamento" de um grid que nunca subiu.
  await expect
    .poll(
      async () =>
        page.evaluate(() =>
          Array.from(document.querySelectorAll('video')).filter((v) => v.currentTime > 0).length,
        ),
      { timeout: 90_000, message: 'nenhum player começou a tocar' },
    )
    .toBeGreaterThan(0)

  const samples: Sample[] = []
  const start = Date.now()
  let loginSeenAt: number | null = null

  while (Date.now() - start < SOAK_MINUTES * MIN) {
    const videos = await page
      .evaluate(() =>
        Array.from(document.querySelectorAll('video')).map((v) => ({
          ct: v.currentTime,
          rs: v.readyState,
          paused: v.paused,
        })),
      )
      .catch(() => [])
    const sample: Sample = { t: Date.now(), page: page.url(), videos }
    samples.push(sample)
    if (sample.page.includes('/login')) {
      loginSeenAt = sample.t
      break
    }
    await page.waitForTimeout(1000)
  }

  fs.writeFileSync(
    OUT,
    [
      ...samples.map((s) => JSON.stringify({ kind: 'sample', ...s })),
      ...http.map((e) => JSON.stringify({ kind: 'http', ...e })),
    ].join('\n') + '\n',
  )

  // ── Aceite 1: expiração de token NUNCA desloga ─────────────────────────────
  expect(loginSeenAt, 'o app navegou para /login durante o soak').toBeNull()

  // ── Aceite 2: zero 401 no caminho de vídeo/renovação ───────────────────────
  const unauthorized = http.filter((e) => e.status === 401)
  expect(unauthorized, `401s: ${JSON.stringify(unauthorized.slice(0, 5))}`).toHaveLength(0)

  // ── Aceite 3: todo player toca; maior janela SEM MUDANÇA < SOAK_MAX_STALL_S ─
  // Progresso = o ct MUDOU entre amostras consecutivas — avanço normal OU o
  // reset legítimo de timeline da renovação (a recuperação faz loadSource()
  // numa URL re-assinada e o relógio do MSE recomeça do zero; queda seguida de
  // subida é vídeo VIVO). A 1ª versão desta métrica só aceitava ct crescente e
  // acusou "stall de 1678s" num soak em que NENHUMA amostra de 1 Hz repetiu o
  // ct — congelamento de verdade é ct IDÊNTICO por segundos seguidos.
  const videoCount = Math.max(...samples.map((s) => s.videos.length))
  expect(videoCount).toBeGreaterThan(0)
  for (let i = 0; i < videoCount; i++) {
    const series = samples
      .map((s) => ({ t: s.t, ct: s.videos[i]?.ct }))
      .filter((p): p is { t: number; ct: number } => typeof p.ct === 'number')
    expect(series.length, `player ${i} sem amostras`).toBeGreaterThan(0)

    let playedS = 0
    let worstGapMs = 0
    let anchorT = series[0].t
    let lastCt = series[0].ct
    for (const p of series.slice(1)) {
      if (Math.abs(p.ct - lastCt) > 0.2) {
        if (p.ct > lastCt) playedS += p.ct - lastCt
        anchorT = p.t
      } else {
        worstGapMs = Math.max(worstGapMs, p.t - anchorT)
      }
      lastCt = p.ct
    }
    expect(playedS, `player ${i} não tocou de verdade`).toBeGreaterThan(60)
    expect(
      worstGapMs / 1000,
      `player ${i}: maior janela sem mudança de ct = ${(worstGapMs / 1000).toFixed(1)}s`,
    ).toBeLessThan(SOAK_MAX_STALL_S)
  }
})
