/**
 * Trava da rodada V1 (set/2026): o produto não fica roxo com um clique.
 *
 * ACHADO MEDIDO: `TopBar.tsx:96` renderizava `<ThemeToggle />` — um switch
 * SEM GATE nenhum, visível para qualquer usuário logado, que chamava
 * `themeStore.toggleMode()` e trocava o tema para `professional`, cuja
 * família `primary` era roxa (#8b5cf6 / #a78bfa / #7c3aed). Um clique de
 * qualquer um dos três usuários reais deixava o produto inteiro roxo.
 * Regra da casa: magenta/roxo só no loader.
 *
 * CONSERTO: o switch saiu do TopBar (ninguém pediu esse controle — mais
 * simples que gateá-lo a superadmin) E a família `primary` dos dois temas
 * legados passou a ler as CSS vars de white-label, com o ciano da marca
 * como default. Os dois juntos: nem o clique existe, nem um `mode:
 * 'professional'` já persistido no localStorage de alguém reintroduz roxo.
 *
 * Este arquivo trava as DUAS pontas — só uma delas não basta:
 *  - reinstalar o switch → teste 1 vermelho
 *  - repintar a família primary de roxo → teste 3 vermelho
 *  - religar `Header.tsx` (o outro componente que ainda importa o switch, e
 *    que hoje é ÓRFÃO: nenhum arquivo o importa) → teste 2 vermelho.
 *    É por isso que o teste 2 existe: sem ele, "tirei do TopBar" seria uma
 *    meia-verdade — bastaria alguém pendurar o Header de volta na árvore.
 *
 * ESCOPO deliberado da varredura de roxo (teste 3): os arquivos consertados
 * nesta rodada. O resto do roxo servido (`components/camera-grid/
 * CameraGrid.css.ts`, `components/dashboard/KPICard.css.ts` e `KPIRow.tsx`,
 * `pages/TrainingPage.css.ts`) é de telas de OUTRAS frentes, que este PR não
 * tem mandato para editar — está registrado em issue própria. O guard-rail
 * de cor da casa (`theme/__tests__/no-offbrand-colors.test.ts`) não pega
 * nenhum deles porque só varre `.tsx`, e todo roxo de tema mora em `.css.ts`.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const AQUI = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.resolve(AQUI, '../../..')

const ler = (rel: string) => fs.readFileSync(path.join(SRC, rel), 'utf-8')

/** Família roxa dos temas legados — mesma lista de `app/shell/Shell.css.test.ts`. */
const ROXO_LEGADO = /#8b5cf6|#a78bfa|#7c3aed|rgba\(\s*139\s*,\s*92\s*,\s*246/i

/** Arquivos de tema/CSS consertados nesta rodada. */
const CSS_SEM_ROXO = [
  'styles/themes/professional.css.ts',
  'styles/themes/cyberpunk.css.ts',
  'pages/ModuleSelectionPage.css.ts',
]

function arquivos(dir: string, acc: string[] = []): string[] {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) {
      if (e.name !== 'node_modules') arquivos(p, acc)
    } else if (/\.tsx?$/.test(e.name)) acc.push(p)
  }
  return acc
}

describe('tema: o produto não fica roxo com um clique (rodada V1)', () => {
  it('1) TopBar — o layout vivo — não renderiza o switch de tema', () => {
    const topBar = ler('components/layout/TopBar/TopBar.tsx')
    expect(topBar).not.toContain('ThemeToggle')
  })

  it('2) Header.tsx (ainda importa o switch) segue ÓRFÃO — nenhum arquivo o importa', () => {
    const importadores = arquivos(SRC)
      .filter((f) => !f.endsWith(path.join('layout', 'Header', 'Header.tsx')))
      .filter((f) => /from\s+['"][^'"]*layout\/Header\/Header['"]/.test(fs.readFileSync(f, 'utf-8')))
      .map((f) => path.relative(SRC, f))

    expect(
      importadores,
      'Header.tsx renderiza <ThemeToggle /> — religá-lo à árvore devolve ao ' +
        'usuário o switch que deixa o produto roxo. Tire o switch do Header antes.',
    ).toEqual([])
  })

  it.each(CSS_SEM_ROXO)('3) %s não declara a família roxa legada', (rel) => {
    const linhas = ler(rel).split('\n')
      .map((l, i) => ({ n: i + 1, l }))
      .filter(({ l }) => ROXO_LEGADO.test(l) && !l.trimStart().startsWith('//'))
      .map(({ n, l }) => `${rel}:${n}  ${l.trim()}`)

    expect(linhas, `roxo legado de volta no CSS servido:\n${linhas.join('\n')}`).toEqual([])
  })
})
