/**
 * Trava da COEXISTÊNCIA/FLIP — a garantia mais importante desta rodada.
 *
 * Até 29/08 o front novo entrava em rota paralela sob `/novo`; no FLIP virou
 * o padrão, no próprio endereço final. A forma de quebrar isso sem ninguém
 * perceber é sempre a mesma: alguém registra uma tela nova num caminho
 * absoluto por fora de `ROTAS_NOVAS`, ou tira um redirect de endereço antigo
 * sem ninguém notar — sem erro de compilação, sem teste vermelho, sem aviso.
 * O usuário descobre clicando, ou num link salvo que vira 404.
 *
 * Estes testes fecham essa porta.
 */
import type { ReactElement } from 'react'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { ROTAS_NOVAS } from './RotasNovas'

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const leia = (rel: string) => fs.readFileSync(path.join(SRC, rel), 'utf-8')

/**
 * Desce em `props.children` — rota aninhada (Estúdio, PR-B: `cobertura`,
 * `classificar` dentro de `estudio`) tem de passar pela MESMA checagem que a
 * de primeiro nível. Um `.map` raso deixaria caminho absoluto filho passar
 * batido, sem teste vermelho nenhum.
 */
function todosOsCaminhos(rotas: ReactElement[]): string[] {
  const caminhos: string[] = []
  const visita = (r: ReactElement) => {
    const props = r.props as { path?: unknown; children?: unknown }
    if (typeof props.path === 'string') caminhos.push(props.path)
    const filhos = props.children
    if (Array.isArray(filhos)) filhos.forEach(visita)
    else if (filhos) visita(filhos as ReactElement)
  }
  rotas.forEach(visita)
  return caminhos
}

describe('front novo e front antigo convivem', () => {
  it('nenhuma rota nova é absoluta — nem no topo, nem aninhada — só existe dentro do prefixo', () => {
    const absolutas = todosOsCaminhos(ROTAS_NOVAS).filter((p) => p.startsWith('/'))
    expect(
      absolutas,
      'rota com caminho absoluto escapa do prefixo e engole a tela antiga de ' +
        'mesmo endereço. Declare relativa (ex.: "epi/live", não "/epi/live").',
    ).toEqual([])
  })

  it('toda rota antiga que mudou de endereço no FLIP redireciona para a nova', () => {
    // De-para do FLIP (29/08): a URL velha sai de circulação, mas quem tinha
    // salva (favorito, link enviado) não pode cair em 404 — precisa de
    // <Redireciona>/<RedirecionaAlerta> te levando para o endereço novo.
    const appRoutes = leia('AppRoutes.tsx')
    const redirects = [
      '<Route path="/epi/alerts" element={<Redireciona para="/epi/eventos" />} />',
      '<Route path="/epi/alerts/:alertId" element={<RedirecionaAlerta />} />',
      '<Route path="/epi/reports" element={<Redireciona para="/epi/relatorios" />} />',
      '<Route path="/epi/verification" element={<Redireciona para="/epi/verificacao" />} />',
      '<Route path="/epi/monitoring" element={<Redireciona para="/epi/live" />} />',
    ]
    for (const linha of redirects) {
      expect(appRoutes, `esperado em AppRoutes.tsx: ${linha}`).toContain(linha)
    }
  })

  it('o front antigo continua sendo o catch-all', () => {
    // O `*` com AppLayout é o que mantém TODA tela ainda não migrada de pé.
    // Se alguém o remover "porque as rotas novas já cobrem", o resto do produto
    // cai junto.
    const app = leia('App.tsx')
    expect(app).toMatch(/path="\*"[\s\S]{0,200}<AppLayout/)
    expect(app).toContain('<AppRoutes />')
  })

  it('o Shell novo monta as rotas novas', () => {
    // Pós-flip a rota é pathless (sem `path`) — o prefixo virou identidade,
    // então um `path={PREFIXO_NOVO}` literal aqui seria `path=""`, ambíguo.
    expect(leia('App.tsx')).toContain('<Route element={<Shell />}>{ROTAS_NOVAS}</Route>')
  })

  it('nenhuma tela nova usa link absoluto literal — tudo via rotaNova()', () => {
    // O pior bug desta rodada, e o mais silencioso: `<Link to="/epi/cameras">`
    // dentro do front NOVO caía na tela ANTIGA de mesmo endereço. Não dava
    // erro, não quebrava teste, não avisava nada. Aconteceu em 10 lugares na
    // primeira leva.
    //
    // Pós-flip `rotaNova()` é identidade, então um `to="/epi/cameras"` literal
    // aponta pro mesmo lugar HOJE — mas volta a divergir no instante em que um
    // prefixo reaparecer. A regra fica mais forte, não mais frouxa: nenhum
    // `to=` absoluto literal em `app/`, mesmo os que hoje "dariam certo".
    const infratores: string[] = []
    const varre = (dir: string) => {
      for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, e.name)
        if (e.isDirectory()) { varre(p); continue }
        if (!/\.tsx?$/.test(e.name) || /\.test\.tsx?$/.test(e.name)) continue
        if (path.relative(SRC, p) === 'app/RotasNovas.tsx') continue
        fs.readFileSync(p, 'utf-8').split('\n').forEach((linha, i) => {
          // `to="/..."` ou to={`/...`} com caminho absoluto — proibido, sem exceção
          const m = linha.match(/to=(?:"(\/[^"]*)"|\{`(\/[^`]*)`\})/)
          const alvo = m?.[1] ?? m?.[2]
          if (alvo) {
            infratores.push(`${path.relative(SRC, p)}:${i + 1}  to="${alvo}"`)
          }
        })
      }
    }
    varre(path.join(SRC, 'app'))
    expect(
      infratores,
      'link absoluto literal em app/ — use rotaNova():\n' +
        infratores.join('\n'),
    ).toEqual([])
  })
})
