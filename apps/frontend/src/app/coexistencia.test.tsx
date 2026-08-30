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

import { ROTAS_NOVAS, ROTAS_NOVAS_SEM_SHELL } from './RotasNovas'

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
  it('as rotas do array são declaradas relativas, nem no topo nem aninhada — convenção que sobrevive ao flip', () => {
    // Hoje (PREFIXO_NOVO === '') path absoluto e relativo dão o MESMO
    // resultado — não há mais prefixo pra "escapar". A convenção continua de
    // propósito: se um prefixo voltar a existir (rollback), um path absoluto
    // aqui ignoraria o `<Route element={<Shell/>}>` que envolve `ROTAS_NOVAS`
    // e voltaria a colidir direto com o endereço antigo — o bug de 27/08.
    // Declarar relativo é o que mantém essa proteção viva, pronta se o
    // prefixo voltar. `todosOsCaminhos` desce em `children` porque o Estúdio
    // (PR-B) tem rota aninhada (`estudio/cobertura`, `estudio/classificar`) —
    // um `.map` raso deixaria um absoluto filho passar batido.
    const absolutas = todosOsCaminhos(ROTAS_NOVAS).filter((p) => p.startsWith('/'))
    expect(
      absolutas,
      'declare relativa (ex.: "epi/live", não "/epi/live") — path absoluto ' +
        'aqui quebra a convenção que protege contra colisão se um prefixo voltar.',
    ).toEqual([])
  })

  it('só as rotas antigas explicitamente sombreadas dividem endereço com a nova', () => {
    // A régua "prefixo não colide" morreu com o prefixo (29/08): sem prefixo,
    // uma rota nova pode ter o MESMO endereço de uma antiga de propósito — a
    // nova (estática) sempre vence e a antiga fica morta até a demolição
    // (MANIFESTO-FRONT-ANTIGO.md). O que ainda precisa de trava é o
    // INVENTÁRIO: só estas quatro colisões são intencionais. Qualquer outra
    // rota antiga que passe a dividir endereço com uma rota nova é a
    // regressão de 27/08 de novo — tela antiga apagada sem aviso.
    const SOMBREADAS_DE_PROPOSITO = new Set([
      '/epi/dashboard',
      '/epi/cameras',
      '/epi/cameras/:cameraId/operations',
      '/modules',
    ])

    const novas = new Set(
      [...todosOsCaminhos(ROTAS_NOVAS), ...todosOsCaminhos(ROTAS_NOVAS_SEM_SHELL)].map((p) =>
        p.startsWith('/') ? p : `/${p}`,
      ),
    )
    const antigas = [...leia('AppRoutes.tsx').matchAll(/<Route\s+path="(\/[^"*]*)"/g)].map((m) => m[1])
    const sombreadas = new Set(antigas.filter((p) => novas.has(p)))

    expect(sombreadas, `sombreadas: ${[...sombreadas].join(', ')}`).toEqual(SOMBREADAS_DE_PROPOSITO)
  })

  it('toda rota antiga demolida (PR-B) redireciona para a nova via rotaNova()', () => {
    // PR-B (30/08) demoliu 6 telas antigas; AppRoutes.tsx virou
    // <Redireciona para={rotaNova(...)}>/<AlertaRedirect> — quem tinha a URL
    // salva (favorito, link enviado) não pode cair em 404. `rotaNova()` (não
    // string crua) é o que faz o alvo acompanhar o flip sem editar esta rota
    // de novo se o prefixo um dia voltar. `/epi/reports` fica de fora: não
    // foi demolida nesta leva, `ReportsPage` continua viva ali.
    const appRoutes = leia('AppRoutes.tsx')
    const redirects = [
      "<Route path=\"/epi/dashboard\" element={<Redireciona para={rotaNova('/epi/dashboard')} />} />",
      "<Route path=\"/epi/cameras\" element={<Redireciona para={rotaNova('/epi/cameras')} />} />",
      "<Route path=\"/epi/alerts\" element={<Redireciona para={rotaNova('/epi/eventos')} />} />",
      '<Route path="/epi/alerts/:alertId" element={<AlertaRedirect />} />',
      "<Route path=\"/epi/verification\" element={<Redireciona para={rotaNova('/epi/verificacao')} />} />",
      "<Route path=\"/epi/monitoring\" element={<Redireciona para={rotaNova('/epi/live')} />} />",
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
