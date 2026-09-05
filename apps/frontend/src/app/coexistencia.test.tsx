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
 * O FRONT NOVO NÃO É `src/app/` — É O FECHO TRANSITIVO DOS IMPORTS DELE.
 *
 * As duas varreduras abaixo passaram semanas VERDES com dois vazamentos vivos
 * (#760), medidos por clique no DEV: "Ver como tenant" no painel admin novo
 * caía em `/admin` e "Sair do contexto" caía em `/admin/tenants`, os dois no
 * front ANTIGO. O motivo é que elas olhavam SÓ o diretório `src/app/`, e o
 * salto não mora lá: `Tenants.tsx` só escreve `assumeTenantContext(t.id)` —
 * uma chamada de função, que não casa com `to=`, `href=`, `navigate()` nem
 * `window.location` — e quem de fato troca de aplicação é
 * `services/tenantContext.ts`, fora do escopo varrido.
 *
 * Guard que varre por DIRETÓRIO mede a arrumação das pastas. O que importa é
 * o que o front novo EXECUTA: todo módulo alcançável a partir das telas
 * novas, esteja ele em `app/`, `services/`, `hooks/` ou `components/`.
 * São ~208 módulos, ~113 fora de `app/` — e era nos 113 que os saltos de
 * #760 moravam, todos os oito.
 */
function fechoDeImports(entradas: string[]): string[] {
  const ESPECIFICADOR = /(?:from\s*|import\s*\(\s*)['"](\.[^'"]*)['"]/g
  const resolve = (deQual: string, spec: string): string | null => {
    const base = path.resolve(path.dirname(deQual), spec)
    for (const c of [base, `${base}.ts`, `${base}.tsx`,
                     path.join(base, 'index.ts'), path.join(base, 'index.tsx')]) {
      if (fs.existsSync(c) && fs.statSync(c).isFile()) return c
    }
    // Import que não resolve para arquivo (pacote, asset, `?raw`) — não é
    // módulo deste código, não entra no fecho. Silêncio aqui é correto.
    return null
  }
  const vistos = new Set<string>()
  const pilha = [...entradas]
  while (pilha.length) {
    const f = pilha.pop() as string
    if (vistos.has(f) || /\.test\.tsx?$/.test(f)) continue
    vistos.add(f)
    for (const m of fs.readFileSync(f, 'utf-8').matchAll(ESPECIFICADOR)) {
      const alvo = resolve(f, m[1])
      if (alvo && !vistos.has(alvo)) pilha.push(alvo)
    }
  }
  return [...vistos].sort()
}

const arquivosDe = (dir: string): string[] =>
  fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) return arquivosDe(p)
    return /\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name) ? [p] : []
  })

/**
 * Entradas do fecho: as telas novas — e `GlobalBanners`.
 *
 * `GlobalBanners` é montado por `App.tsx` FORA das rotas, então nenhum
 * arquivo de `app/` o importa; mas ele renderiza `TenantContextBanner` e
 * `ImpersonationBanner` em TODA tela nova, e os dois botões desses banners
 * ("Sair do contexto", "Sair da visualização") eram justamente dois dos
 * saltos de #760. Entrada explícita, e nunca por silêncio: sem ela o fecho
 * não alcança os banners e o guard volta a ficar verde com o furo aberto.
 */
const MODULOS_DO_FRONT_NOVO = fechoDeImports([
  ...arquivosDe(path.join(SRC, 'app')),
  path.join(SRC, 'components/layout/GlobalBanners.tsx'),
])

/**
 * Endereços absolutos fora do prefixo que NÃO são vazamento — por lista
 * explícita, nunca por silêncio.
 */
const EXCECOES = [
  // `/login` é o portão deslogado, comum aos dois fronts — `App.tsx` troca a
  // árvore INTEIRA pro Router sem Shell ao desautenticar (ver `aoSair` em
  // `Shell.tsx`), e o catch-all deslogado pinta `Entrar`, a tela NOVA.
  '/login',
  // A raiz. Deslogada pinta `Entrar` (novo; teste em `App.porta.test.tsx`);
  // LOGADA passou a resolver por `rotaHomeDoUsuario` (novo; teste em
  // `app/raizLogada.test.tsx`) — antes deste PR caía em `/admin`|`/modules`,
  // os dois no front antigo (#762). A exceção vale enquanto AQUELES DOIS
  // testes valerem: se alguém devolver o `RootRedirect` ao front antigo,
  // `raizLogada.test.tsx` fica vermelho e esta linha volta a ser mentira.
  '/',
  // Sem equivalente no front novo (C1, 31/08) — mantidos APONTANDO pro front
  // antigo de propósito (não existe tela nova de observabilidade nem de
  // integrações), mas honestos: texto e `title` avisam que é a área técnica
  // antiga, e ambos são visíveis só para `isSuperAdmin` (`Modulos.tsx`,
  // `Treino.tsx`). Um link "escapando calado" é o que estes testes reprovam —
  // um link honesto, gated por papel, apontando de propósito pro antigo, é o
  // comportamento certo até a tela nova existir.
  '/admin/observability',
  '/admin/integrations?type=vast_ai',
]

/** Um destino que fica DENTRO do front novo, ou uma exceção declarada. */
const ehDoFrontNovo = (destino: string): boolean =>
  destino.startsWith(PREFIXO_NOVO) || EXCECOES.includes(destino)

/**
 * Todo nome deste arquivo que está amarrado a um caminho absoluto literal.
 *
 * Cobre os DOIS jeitos de esconder um endereço atrás de um identificador:
 *   const ROTA = '/epi/eventos'              ← constante de módulo (4º furo)
 *   function f(redirect = '/admin/tenants')  ← DEFAULT DE PARÂMETRO (7º furo)
 *   destino: string = '/'                    ← idem, com tipo anotado
 * Os dois terminam iguais na linha que navega: um identificador, nunca um
 * literal — invisível para qualquer varredura que só leia a linha do salto.
 *
 * O mapa é por ARQUIVO, não por escopo: dois `redirect = '/x'` em funções
 * diferentes do mesmo arquivo se confundem. Conservador de propósito — o erro
 * possível é um vermelho a mais (basta parar de escrever o endereço antigo),
 * nunca um verde a menos. Guard que erra para o lado do silêncio é o que já
 * deixou #760 passar.
 */
function literaisNomeados(texto: string): Map<string, string> {
  const mapa = new Map<string, string>()
  for (const m of texto.matchAll(
    /\b([A-Za-z_$][\w$]*)\s*(?::\s*[\w$<>[\]|.\s]+?)?\s*=\s*(?:"(\/[^"]*)"|'(\/[^']*)'|`(\/[^`]*)`)/g,
  )) {
    mapa.set(m[1], m[2] ?? m[3] ?? m[4])
  }
  return mapa
}

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

  it('nenhum módulo do front novo linka para fora do prefixo', () => {
    // O pior bug desta rodada, e o mais silencioso: `<Link to="/epi/cameras">`
    // dentro do front NOVO leva para a tela ANTIGA de mesmo endereço. Não dá
    // erro, não quebra teste, não avisa nada — o usuário só vê, de repente, o
    // produto velho. Aconteceu em 10 lugares na primeira leva.
    //
    // Furos já fechados, cada um com um jeito diferente de escapar:
    //  1. `to="/..."` declarativo (`<Link>`/`<NavLink>`) — a leva original;
    //  2. `navegar('/...')` imperativo (`useNavigate()`, `Cameras.tsx`);
    //  3. `<a href="/admin/...">` — âncora HTML pura, dentro do PRÓPRIO admin;
    //  4. `const ROTA = '/epi/eventos'` + `to={ROTA}` 400 linhas abaixo;
    //  5. `destino: '/quality'` numa TABELA lida por `navegar(c.destino)`.
    //
    // Todo link/navegação interna passa por `rotaNova()`. Este teste é quem
    // cobra — agora sobre o fecho de imports, não sobre o diretório `app/`.
    const infratores: string[] = []
    for (const p of MODULOS_DO_FRONT_NOVO) {
      if (path.relative(SRC, p) === 'app/RotasNovas.tsx') continue
      const texto = fs.readFileSync(p, 'utf-8')
      const constantes = literaisNomeados(texto)
      // Este arquivo navega para um campo de objeto SEM prefixar na hora
      // (`navegar(c.destino)`, `to={c.destino}`)? Então o prefixo tem de já
      // estar guardado na tabela, e os literais dela passam a ser cobrados
      // logo abaixo. `navegar(rotaNova(item.destino))` e `PREFIXO_NOVO + i.rota`
      // não casam aqui — o argumento não começa com identificador-ponto —, que
      // é justamente a diferença entre guardar um caminho relativo de propósito
      // e vazar um absoluto por descuido.
      const consomeBruto = /(?:to|href)=\{\s*[A-Za-z_$][\w$]*\.[\w$.]+\s*\}|\b(?:navigate|navegar|nav)\(\s*[A-Za-z_$][\w$]*\.[\w$.]+\s*[,)]/.test(texto)
      texto.split('\n').forEach((linha, i) => {
        const mLink = linha.match(/(?:to|href)=(?:"(\/[^"]*)"|\{`(\/[^`]*)`\})/)
        const mNav = linha.match(
          /\b(?:navigate|navegar|nav)\(\s*(?:"(\/[^"]*)"|'(\/[^']*)'|`(\/[^`]*)`)/,
        )
        const mConst = linha.match(
          /(?:to|href)=\{\s*([A-Za-z_$][\w$]*)\s*\}|\b(?:navigate|navegar|nav)\(\s*([A-Za-z_$][\w$]*)\s*[,)]/,
        )
        const viaConstante = constantes.get(mConst?.[1] ?? mConst?.[2] ?? '')
        const mProp = linha.match(
          /\b(?:destino|rota|caminho|to|href)\s*:\s*(?:"(\/[^"]*)"|'(\/[^']*)'|`(\/[^`]*)`)/,
        )
        const viaTabela = consomeBruto ? mProp?.[1] ?? mProp?.[2] ?? mProp?.[3] : undefined
        const alvo = mLink?.[1] ?? mLink?.[2] ?? mNav?.[1] ?? mNav?.[2] ?? mNav?.[3]
        for (const destino of [alvo, viaConstante, viaTabela]) {
          if (destino && !ehDoFrontNovo(destino)) {
            infratores.push(`${path.relative(SRC, p)}:${i + 1}  ${destino}`)
          }
        }
      })
    }
    expect(
      infratores,
      'link/navigate/href absoluto sai do front novo e cai no antigo — use rotaNova() ' +
        '(ou, se for exceção legítima pro front antigo, liste em EXCECOES, nunca por silêncio):\n' +
        infratores.join('\n'),
    ).toEqual([])
  })

  it('nenhum módulo do front novo troca de aplicação por window.location', () => {
    // Quinto furo (v1, 05/09): `Modulos.tsx` guardava o destino numa TABELA e
    // saltava com `window.location.href = c.destino`. Nem `to=`, nem `href=`,
    // nem `navigate()` — nenhuma varredura chegava perto, e quem clicava em
    // "Qualidade" no front NOVO era despejado no ANTIGO de página inteira.
    //
    // SÉTIMO furo (#760, o desta rodada, e o pior): o salto nem estava numa
    // tela — estava num SERVIÇO, atrás de um DEFAULT DE PARÂMETRO. Ninguém
    // escreve `'/admin/tenants'` em `TenantContextBanner.tsx`; ela chama
    // `exitTenantContext()`, que chama `restoreTenantContextBackup()`, cuja
    // assinatura dizia `(redirect = '/admin/tenants')` e terminava em
    // `window.location.href = redirect`. Ler só a linha do `window.location`
    // via literal não vê NADA: o alvo é uma variável. Por isso o destino é
    // resolvido por `literaisNomeados` — que casa tanto `const X = '/y'`
    // quanto `redirect = '/y'` e `destino: string = '/y'` de assinatura.
    //
    // (`reload()` e a LEITURA de `location.pathname` seguem livres em todo
    // lugar — não escolhem destino. O que cada metade cobra está dito no
    // corpo do laço abaixo: em `app/` é proibido escrever, e fora de `app/` o
    // que se cobra é o destino.)
    const saltos: string[] = []
    for (const p of MODULOS_DO_FRONT_NOVO) {
      const rel = path.relative(SRC, p)
      // TELA (`app/`): proibido, ponto — sem resolver destino nenhum. Tela nova
      // navega com `navegar(rotaNova(...))`; trocar a aplicação inteira nunca
      // é o que ela quer. Era esta a regra que pegou o 5º furo
      // (`window.location.href = c.destino`, destino vindo de uma TABELA — nem
      // literal, nem identificador simples: NENHUMA resolução o alcança).
      // Afrouxá-la para "só reprovo se eu conseguir LER o destino" trocaria um
      // guard que mede por um que quase nunca mede — medido: com a regra, o
      // mutante do 5º furo dá vermelho; sem ela, verde.
      //
      // SERVIÇO/HOOK (fora de `app/`): recarregar a página inteira é o
      // mecanismo legítimo deles (a troca de token exige releitura do
      // localStorage por todo hook montado). Aqui o que se cobra é o DESTINO,
      // resolvido por literal ou por identificador — inclusive default de
      // assinatura, que é onde #760 se escondeu.
      const eTela = rel.startsWith('app/')
      const texto = fs.readFileSync(p, 'utf-8')
      const constantes = literaisNomeados(texto)
      texto.split('\n').forEach((linha, i) => {
        const m = linha.match(
          /window\.location\s*(?:\.href\s*=|\.assign\(|\.replace\()\s*(?:"(\/[^"]*)"|'(\/[^']*)'|`(\/[^`]*)`|([A-Za-z_$][\w$]*))?/,
        )
        if (!m) return
        const destino = m[1] ?? m[2] ?? m[3] ?? constantes.get(m[4] ?? '')
        const vaza = eTela ? true : destino !== undefined && !ehDoFrontNovo(destino)
        if (vaza) {
          saltos.push(`${rel}:${i + 1}  → ${destino ?? '(destino não literal)'}   ${linha.trim()}`)
        }
      })
    }
    expect(
      saltos,
      'window.location leva a pessoa para FORA do front novo, de página inteira ' +
        '— use rotaNova()/PREFIXO_NOVO. Se o destino é mesmo outra aplicação, ' +
        'diga isso em EXCECOES em voz alta, nunca por silêncio:\n' + saltos.join('\n'),
    ).toEqual([])
  })
})
