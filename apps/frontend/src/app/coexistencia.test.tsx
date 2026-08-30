/**
 * Trava da COEXISTÊNCIA — a garantia mais importante desta rodada.
 *
 * A regra do Vitor (27/08) é que o front novo entra em rota paralela e o front
 * antigo continua inteiro e funcionando, até a migração terminar. A forma de
 * quebrar isso sem ninguém perceber é sempre a mesma: alguém registra uma tela
 * nova num caminho absoluto (`/epi/dashboard`), ela ganha do `*` do front
 * antigo por ser segmento estático, e a tela velha some da aplicação — sem erro
 * de compilação, sem teste vermelho, sem aviso. O usuário descobre clicando.
 *
 * Estes testes fecham essa porta.
 */
import type { ReactElement } from 'react'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { PREFIXO_NOVO, ROTAS_NOVAS } from './RotasNovas'

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

  it('o prefixo não colide com nenhum primeiro segmento do front antigo', () => {
    // Se o prefixo virasse '/epi', o `<Route path="/epi">` novo passaria a
    // capturar TODO o /epi/* antigo — inclusive as telas que ainda não foram
    // migradas, que morreriam em 404 dentro do Shell novo.
    const antigas = [...leia('AppRoutes.tsx').matchAll(/path="(\/[^"*]*)"/g)]
      .map((m) => `/${m[1].split('/')[1] ?? ''}`)
    expect(new Set(antigas)).not.toContain(PREFIXO_NOVO)
  })

  it('o front antigo continua sendo o catch-all', () => {
    // O `*` com AppLayout é o que mantém TODA tela ainda não migrada de pé.
    // Se alguém o remover "porque as rotas novas já cobrem", o resto do produto
    // cai junto.
    const app = leia('App.tsx')
    expect(app).toMatch(/path="\*"[\s\S]{0,200}<AppLayout/)
    expect(app).toContain('<AppRoutes />')
  })

  it('o Shell novo só monta sob o prefixo', () => {
    expect(leia('App.tsx')).toContain('path={PREFIXO_NOVO} element={<Shell />}')
  })

  it('nenhuma tela nova linka para fora do prefixo', () => {
    // O pior bug desta rodada, e o mais silencioso: `<Link to="/epi/cameras">`
    // dentro do front NOVO leva para a tela ANTIGA de mesmo endereço. Não dá
    // erro, não quebra teste, não avisa nada — o usuário só vê, de repente, o
    // produto velho. Aconteceu em 10 lugares na primeira leva.
    //
    // F5-LEVE (identidade): achado de sonda pegou o MESMO bug em `navegar(...)`
    // imperativo (`app/epi/Cameras.tsx`, botão "Operações") — `to="..."` só
    // cobria `<Link>`/`<NavLink>` declarativos, não `useNavigate()` chamado na
    // mão. A varredura abaixo cobre os dois: `to="/..."` / `to={`/...`}` E
    // `navigate('/...')` / `navegar(`/...`)` (qualquer nome de variável do
    // `useNavigate()` termina em "nav"/"navegar"/"navigate" neste código).
    //
    // Todo link/navegação interna passa por `rotaNova()`. Este teste é quem cobra.
    const infratores: string[] = []
    // Exceção conhecida: `/login` é o portão deslogado, comum aos dois fronts
    // — `App.tsx` troca a árvore INTEIRA pro Router sem Shell ao desautenticar
    // (ver `aoSair` em `Shell.tsx`), então não é "cair no front antigo", é
    // onde QUALQUER usuário deslogado cai, migrado ou não.
    const EXCECOES = ['/login']
    const varre = (dir: string) => {
      for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, e.name)
        if (e.isDirectory()) { varre(p); continue }
        if (!/\.tsx?$/.test(e.name) || /\.test\.tsx?$/.test(e.name)) continue
        if (path.relative(SRC, p) === 'app/RotasNovas.tsx') continue
        fs.readFileSync(p, 'utf-8').split('\n').forEach((linha, i) => {
          // `to="/..."` ou to={`/...`} com caminho absoluto que não é o prefixo
          const mLink = linha.match(/to=(?:"(\/[^"]*)"|\{`(\/[^`]*)`\})/)
          // `navigate('/...')` / `navegar('/...')` / `nav(`/...`)` imperativo
          const mNav = linha.match(
            /\b(?:navigate|navegar|nav)\(\s*(?:"(\/[^"]*)"|'(\/[^']*)'|`(\/[^`]*)`)/,
          )
          const alvo = mLink?.[1] ?? mLink?.[2] ?? mNav?.[1] ?? mNav?.[2] ?? mNav?.[3]
          if (alvo && !alvo.startsWith('/novo') && !EXCECOES.includes(alvo)) {
            infratores.push(`${path.relative(SRC, p)}:${i + 1}  ${alvo}`)
          }
        })
      }
    }
    varre(path.join(SRC, 'app'))
    expect(
      infratores,
      'link/navigate absoluto sai do front novo e cai no antigo — use rotaNova():\n' +
        infratores.join('\n'),
    ).toEqual([])
  })
})
