/**
 * REGRA GLOBAL — nenhuma tela do front novo é beco sem saída (contrato A3).
 *
 * Percorre TODA rota de `ROTAS_NOVAS` + `ROTAS_NOVAS_SEM_SHELL` (as mesmas
 * listas que montam o app em `App.tsx`, não uma cópia) e falha se a tela não
 * oferecer um jeito de voltar. Critério objetivo:
 *
 *  · Shell COM a nav principal (sidebar visível — rota fora de
 *    `SEM_BARRA_LATERAL`) já satisfaz: a sidebar sempre mostra ao menos
 *    "Dashboard", mesmo sem NENHUMA permissão (`Shell.test.tsx` cobra isso à
 *    parte — "sem permissão nenhuma, sobra só o que não exige permissão").
 *  · Área com NAV PRÓPRIA (`SEM_BARRA_LATERAL`: a sidebar do Shell some) pede
 *    mais: o logo do topbar (link desde F5-LEVE item 1) chega lá, mas é
 *    pequeno e não é o que se procura quando a lateral inteira virou outra
 *    coisa — por isso a ÁREA precisa do PRÓPRIO link explícito, contando só
 *    o que está no arquivo daquela área (não vale o logo por tabela).
 *  · Rota SEM Shell (`ROTAS_NOVAS_SEM_SHELL`): `/modules` É a home de quem
 *    não é superadmin (a raiz do prefixo cai lá, `rotaHomeDoUsuario`) — não
 *    há "nível acima" dela. `/tablet/:station` é o kiosk físico da bancada
 *    (Quality Gate), sem chrome de propósito: tablet fixo, não é navegação
 *    de gente logada — ver docstring de `Kiosk.tsx`.
 *
 * Hoje só o Estúdio tem o link explícito (F5-LEVE item 2, este PR).
 * Quality/Carga/Admin têm a MESMA lacuna estrutural (nav própria, sem link de
 * volta) — dívida real, fora do escopo desta rodada, registrada em
 * `LAYOUT_DA_AREA` abaixo em vez de escondida: um `null` ali é uma lacuna
 * conhecida, não uma aprovação.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { PREFIXO_NOVO, ROTAS_NOVAS, ROTAS_NOVAS_SEM_SHELL } from '../RotasNovas'
import { SEM_BARRA_LATERAL } from './Shell'

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const leia = (rel: string) => fs.readFileSync(path.join(SRC, rel), 'utf-8')

/** Primeiro segmento de um caminho relativo ('quality/gestao' → 'quality'). */
const areaDe = (caminho: string) => caminho.split('/')[0]

/**
 * Área com nav própria → arquivo de layout que precisa do link explícito.
 * `null` = dívida conhecida (ver docstring do arquivo), fora do escopo desta
 * rodada — a rota ainda passa na varredura, mas SEM checar conteúdo nenhum.
 */
const LAYOUT_DA_AREA: Record<string, string | null> = {
  quality: null,
  carga: null,
  estudio: 'app/estudio/Estudio.tsx',
  admin: null,
}

const AREAS_SEM_BARRA = SEM_BARRA_LATERAL.map((r) => r.replace(`${PREFIXO_NOVO}/`, ''))

const caminhosDeTopo = ROTAS_NOVAS
  .map((r) => (r.props as { path?: string }).path)
  .filter((p): p is string => typeof p === 'string')

describe('nenhuma tela do front novo é beco sem saída', () => {
  it('SEM_BARRA_LATERAL não cresce sem entrar no mapa de layouts deste teste', () => {
    // Trava de sanidade do PRÓPRIO teste: área nova com nav própria e sem
    // entrada aqui seria um buraco silencioso na regra global.
    for (const area of AREAS_SEM_BARRA) {
      expect(
        Object.keys(LAYOUT_DA_AREA),
        `área nova em SEM_BARRA_LATERAL sem entrada em LAYOUT_DA_AREA: "${area}"`,
      ).toContain(area)
    }
  })

  it.each(caminhosDeTopo.filter((p) => AREAS_SEM_BARRA.includes(areaDe(p))))(
    'rota "%s" (nav própria): a área tem link explícito de volta — ou é dívida registrada',
    (caminho) => {
      const layout = LAYOUT_DA_AREA[areaDe(caminho)]
      if (layout === null) return // dívida conhecida, ver docstring do arquivo
      const fonte = leia(layout)
      expect(fonte, `${layout} precisa de um link "Voltar" via rotaNova()`).toMatch(/voltar/i)
      expect(fonte).toMatch(/rotaNova\(/)
    },
  )

  it('rotas SEM Shell são a própria home (/modules) ou o kiosk físico sem chrome (/tablet)', () => {
    const caminhos = ROTAS_NOVAS_SEM_SHELL.map((r) => (r.props as { path: string }).path)
    expect(caminhos).toEqual([`${PREFIXO_NOVO}/modules`, `${PREFIXO_NOVO}/tablet/:station`])
  })

  it('o logo do Shell é link para a home do usuário (superadmin → admin, demais → modules)', () => {
    const fonte = leia('app/shell/Shell.tsx')
    expect(fonte).toMatch(/<Link\b/)
    expect(fonte).toMatch(/rotaHomeDoUsuario\(/)
  })
})
