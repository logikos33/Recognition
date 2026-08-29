/**
 * Mede a PROPORÇÃO DE ÁREA ciana de cada tela do front novo, contra dado real.
 *
 * A regra do handoff é "ciano só interativo, ≤10% da tela". Na migração ela foi
 * conferida só de olho, porque o navegador de automação usado não expunha as
 * dimensões da página. Aqui há viewport de verdade.
 *
 * O que é medido: soma das áreas visíveis de elementos cuja cor de FUNDO cai na
 * faixa ciano, sobre a área do viewport. Borda e texto cianos não entram — são
 * área desprezível perto de um fundo, e incluí-los exigiria rasterizar. É uma
 * medida conservadora POR BAIXO, e é assim que deve ser lida.
 *
 * Não vai para o CI: depende do DEV e de credencial. Roda sob demanda.
 */
import { expect, test } from '@playwright/test'

/**
 * :3000, e não o servidor do próprio Playwright (:3001): a API do DEV libera
 * CORS só para `http://localhost:3000`. Medido em :3001, TODAS as telas caem no
 * estado de erro — e a medição seria de sete telas de erro, não do produto.
 * Foi o que aconteceu na primeira tentativa.
 */
const BASE = process.env.MEDIR_BASE ?? 'http://localhost:3000'

const SENHA = process.env.E2E_ANNOT_PASSWORD
const API = 'https://api-v3-desenvolvimento.up.railway.app'

const TELAS = [
  ['dashboard', '/epi/dashboard'],
  ['ao-vivo', '/epi/live'],
  ['eventos', '/epi/eventos'],
  ['verificacao', '/epi/verificacao'],
  ['acoes', '/epi/acoes'],
  ['cameras', '/epi/cameras'],
  ['relatorios', '/epi/relatorios'],
] as const

test.describe('proporção de ciano', () => {
  test.skip(!SENHA, 'sem E2E_ANNOT_PASSWORD — medição contra o DEV é sob demanda')

  test('nenhuma tela passa de 10% de área ciana', async ({ page, request }) => {
    test.setTimeout(180_000)
    const login = await request.post(`${API}/api/auth/login`, {
      data: { email: 'e2e-anotacao@recognition.dev', password: SENHA },
    })
    expect(login.ok(), 'login no DEV falhou').toBe(true)
    let token = (await login.json()).data.token

    // O tenant com dado é o RVB; o e2e nasce no tenant 'dev', que está vazio —
    // e medir ciano em tela vazia mediria a tela errada.
    const tenants = await request.get(`${API}/api/v1/admin/tenant-context/tenants`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const rvb = (await tenants.json()).data.tenants.find((t: any) => t.slug === 'rvb')
    if (rvb) {
      const assume = await request.post(
        `${API}/api/v1/admin/tenant-context/tenants/${rvb.id}/assume`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      if (assume.ok()) token = (await assume.json()).data.token
    }

    await page.addInitScript((t) => localStorage.setItem('token', t as string), token)
    await page.addInitScript(() =>
      localStorage.setItem('user', JSON.stringify({ role: 'superadmin', permissions: [] })),
    )

    const medidas: Array<Record<string, unknown>> = []
    for (const [nome, rota] of TELAS) {
      await page.goto(BASE + rota)
      await page.waitForTimeout(5000)
      // Medir a tela de ERRO ou de CARREGANDO mediria outra coisa. Se a tela não
      // chegou a mostrar conteúdo, o número não vale e o teste tem de dizer isso.
      const estado = await page.evaluate(() => ({
        erro: !!document.body.textContent?.match(/tentar novamente|falha ao/i),
        carregando: !!document.body.textContent?.match(/CARREGANDO|ABRINDO/),
      }))

      const m = await page.evaluate(() => {
        const ehCiano = (c: string) => {
          const x = c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?/)
          if (!x) return false
          const [r, g, b] = [+x[1], +x[2], +x[3]]
          const a = x[4] === undefined ? 1 : +x[4]
          return a > 0.5 && b > 120 && g > 100 && r < 90
        }
        const W = window.innerWidth
        const H = window.innerHeight
        let area = 0
        const itens: Array<[number, string]> = []
        for (const el of Array.from(document.querySelectorAll('*'))) {
          const r = el.getBoundingClientRect()
          const vis = Math.max(0, Math.min(r.bottom, H) - Math.max(r.top, 0)) *
                      Math.max(0, Math.min(r.right, W) - Math.max(r.left, 0))
          if (vis < 1) continue
          if (ehCiano(getComputedStyle(el).backgroundColor)) {
            area += vis
            itens.push([vis, `${el.tagName.toLowerCase()} "${(el.textContent || '').trim().slice(0, 24)}"`])
          }
        }
        itens.sort((a, b) => b[0] - a[0])
        return {
          pct: +((100 * area) / (W * H)).toFixed(2),
          maiores: itens.slice(0, 4).map(([a, d]) => `${Math.round(a)}px² ${d}`),
          viewport: `${W}x${H}`,
        }
      })
      medidas.push({ tela: nome, ...m, ...estado })
      console.log(`  ${nome.padEnd(14)} ${String(m.pct).padStart(6)}%   ${m.maiores[0] ?? '(nenhum fundo ciano)'}`)
    }

    console.log('\nRESUMO:', JSON.stringify(medidas, null, 1))
    const invalidas = medidas.filter((m: any) => m.erro || m.carregando)
    expect(
      invalidas.map((m: any) => m.tela),
      'telas que não carregaram — a medida delas não vale',
    ).toEqual([])

    for (const m of medidas) {
      expect(m.pct, `${m.tela} passou de 10% de área ciana`).toBeLessThanOrEqual(10)
    }
  })
})
