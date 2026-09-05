/**
 * Trava: jargão técnico não aparece em TEXTO VISÍVEL de superfície de
 * TENANT.
 *
 * Lista exata (12 termos, nesta ordem) — aba "Microcopy" do desenho
 * `docs/design/handoff-f5/Cenário e Operações.dc.html`, bloco "PALAVRAS
 * PROIBIDAS NESTA TELA" (linha ~455):
 *   threshold · IoU · condition_satisfied · bounding box · overlap ·
 *   polygon · payload · JSON · confidence score · inferência · YOLO ·
 *   tracker
 *
 * + os nomes de framework já cobertos pelo teste do alias Logikos
 * (`app/estudio/Modelo.test.tsx`, regex `/yolo|rf-?detr|onnx/i`) — mesma
 * família: o cliente não escolhe motor, não vê o nome dele.
 *
 * ─── ESCOPO DE ARQUIVOS (furo B3 corrigido, rodada UX 2026-08) ──────────
 *
 * Furo real, achado com evidência: `components/training/CameraModelScope.tsx`
 * tinha `tasks/inference.py::_no_escopo_da_camera` e "issue #519" direto no
 * `<Banner>` — texto que o tenant lê — e a régua NUNCA leu esse arquivo,
 * porque só andava por `src/app/**` (o front novo) e esse componente mora em
 * `src/components/training/`. Ele É renderizado ao tenant (via
 * `app/estudio/ModelosPorCamera.tsx`), só não morava sob `src/app`.
 *
 * A correção óbvia — varrer `src/components/**` inteiro — foi TESTADA e
 * DESCARTADA: traz ~20 achados de jargão reais (Threshold/IoU/JSON/
 * condition_satisfied) que vivem em telas do FRONT LEGADO
 * (`components/scenario/ScenarioEditor.tsx`,
 * `components/training/modals/Operation{Create,Edit}Modal.tsx`,
 * `components/training/operationTypeForms/*`, `CameraFpsConfig.tsx`) —
 * alcançáveis só a partir de `pages/`/`modules/` (o front antigo), nunca de
 * `src/app`. Isso é dívida real, mas é de OUTRA rodada — misturar as duas
 * neste PR trocaria "consertar o achado" por "reescrever telas que ninguém
 * pediu para mexer".
 *
 * Critério adotado: `arquivosVisiveisAoTenant()` varre `src/app/**` (como
 * antes) MAIS todo arquivo de `src/components/**` ALCANÇÁVEL a partir de
 * `src/app` por import relativo, transitivo (BFS sobre `import ... from
 * './...'`). É "o conjunto de superfícies que o front novo de fato
 * renderiza", calculado de verdade em vez de assumido por convenção de
 * pasta — robusto a arquivo mudar de lugar, e não engole o legado por
 * coincidência de diretório. Prova: teste "escopo" abaixo, com caminhos
 * reais do repo (`CameraModelScope.tsx` dentro, `OperationCreateModal.tsx`
 * fora).
 *
 * ─── VOCABULÁRIO ESTRUTURAL (2º furo do achado B3) ──────────────────────
 *
 * A denylist de 16 termos é FECHADA — "tasks/inference.py", "_no_escopo_da_
 * camera" e "#519" não estavam nela, então mesmo COM o arquivo em escopo a
 * régua deixaria passar. Em vez de caçar caso a caso, `ESTRUTURAIS` reconhece
 * a FORMA de uma referência a código-fonte, não o texto exato:
 *   - `[\w./-]*\.py\b`                    → caminho/arquivo Python
 *   - `\S*::\S*`                          → escopo `arquivo::função`
 *   - `(?<!\w)_[a-zA-Z][a-zA-Z0-9]*(_[a-zA-Z0-9]+)+` → identificador
 *     `_snake_case` com underscore líder (convenção de função "privada" em
 *     Python) E pelo menos 2 underscores. Underscore líder é o que separa
 *     isto de um NOME DE COLUNA/CAMPO legítimo já mostrado ao usuário
 *     avançado hoje em telas como `carga/Carga.tsx` (`<code>bay_id</code>`,
 *     `<code>counting_events</code>`) — nenhum desses tem underscore líder;
 *     varri o repo inteiro (`src/app` + `src/components`) pra confirmar ZERO
 *     ocorrência de `_snake_case` líder fora do achado real. O `(?<!\w)`
 *     (negative lookbehind) foi um SEGUNDO achado, direto rodando este
 *     teste: sem ele, `_list_reworks` batia DENTRO de `gate_list_reworks`
 *     (`app/qualidade/Qualidade.tsx`, `title=`) — nome de rota comum, sem
 *     "_" líder de verdade, mesma família de `bay_id`. O lookbehind garante
 *     que o "_" é o INÍCIO do identificador (não precedido de letra/dígito/
 *     "_"), não um "_" no meio de uma palavra snake_case qualquer.
 *   - `#\d{3,}\b`                          → número de issue (3+ dígitos).
 *     Calibrado no HISTÓRICO REAL do repo: as issues citadas em texto do
 *     projeto são #500/#519/#535/#608 (3 dígitos) — nunca `#1`/`#2` de
 *     ranking nem posição. Exigir 3+ dígitos deixa "#1" (ranking) e "v1.2"
 *     (versão) passarem por CONSTRUÇÃO (nem têm `#`) e pega o caso real sem
 *     tocar nenhuma tela hoje. Teto documentado: uma issue de 1–2 dígitos
 *     escaparia — trade-off aceito, mesmo espírito do trade-off já assumido
 *     acima para string solta fora de JSX.
 * Achado validado por MUTAÇÃO: teste "prova por mutação" abaixo reinstala o
 * texto antigo do banner (o que estava em produção) como fixture e mostra a
 * régua pegando — com os 4 furos JUNTOS: `.py`, `::`, `_snake_case` e `#519`.
 *
 * ─── ESTRATÉGIA ANTI-FALSO-POSITIVO (texto/JSX) ─────────────────────────
 *
 * `semHexSolto.test.ts` varre LINHA por LINHA (regex de hex é simples e
 * sem contexto). Jargão não dá para varrer assim: "YoloClass" é um tipo,
 * "threshold_pct" é um campo de API, "yolo_classes" é uma tabela — grep de
 * substring pegaria os três, e nenhum dos três é texto que o tenant lê.
 *
 * Por isso aqui varremos a AST de verdade (`typescript.createSourceFile`)
 * e só olhamos para os nós que SÃO texto visível:
 *   - `JsxText`            → o texto entre tags: <span>texto</span>
 *   - `title=` / `aria-label=` / `placeholder=` / `alt=` (literal ou
 *     `{'...'}`, inclusive `{cond ? 'a' : 'b'}` / `{cond && 'texto'}`)
 *   - `{...}` como FILHO de JSX com o mesmo formato — cobre o caso
 *     "exportar JSON" atrás de um ternário: <button>{ok ? 'exportar JSON' : '…'}</button>
 *
 * Isso ignora, por CONSTRUÇÃO — sem lista de exceção nenhuma —, imports,
 * chaves de objeto, nomes de variável, props de dados (`m.framework`,
 * `value="yolo26n"`) e comentários: nenhum desses é um `JsxText` nem um
 * desses 4 atributos. É por isso que `JSON.parse(...)` no código nunca
 * dispara, mas um botão "exportar JSON" dispara — sem regra especial para
 * nenhum dos dois casos, o tipo de nó já resolve.
 *
 * O que este corte deliberadamente NÃO cobre: string solta em `const` fora
 * de JSX (`const MSG = 'threshold alto'`). Dava para casar por convenção de
 * nome (`*Msg`, `*Label`...), mas essa heurística é exatamente onde entra
 * falso positivo (uma constante de URL, de classe CSS, de campo de API —
 * todas parecem "copy" pra um regex ingênuo). Trade-off aceito: o helper
 * `acharJargao` abaixo é testável e reaproveitável se um padrão real de
 * "arquivo de copy" aparecer no projeto.
 *
 * ─── EXCEÇÃO: MODO AVANÇADO (SUPERADMIN) ────────────────────────────────
 *
 * A própria aba Microcopy do desenho prevê a via de escape: `{ k: 'modo
 * avançado', v: 'Números crus do motor. O cliente nunca precisa abrir
 * isto.' }`. Trechos assim marcam a linha ANTERIOR com
 * `// jargao-ok: <motivo>` — mesma convenção em espírito do `allow:` que o
 * guard-rail de cor (`theme/__tests__/no-offbrand-colors.test.ts`) aceita,
 * adaptada para comentário de linha inteira (uma string de JSX não aceita
 * `//` no fim da própria linha).
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import * as ts from 'typescript'
import { describe, expect, it } from 'vitest'

const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

/** Os 4 atributos que o navegador expõe como texto/rótulo ao usuário. */
const ATRIBUTOS_DE_TEXTO = new Set(['title', 'aria-label', 'placeholder', 'alt'])

/** Marcador de exceção — mesmo espírito do `allow:` do guard-rail de cor. */
const MARCADOR_EXCECAO = 'jargao-ok'

/** Lista exata do desenho (12) + família de framework do teste do alias. */
const TERMOS = [
  'threshold', 'IoU', 'condition_satisfied', 'bounding box', 'overlap',
  'polygon', 'payload', 'JSON', 'confidence score', 'inferência', 'YOLO',
  'tracker', 'rfdetr', 'rf-detr', 'onnx', 'yolox',
] as const

/** termo → tradução recomendada, lida na aba Microcopy do desenho. */
const TRADUCAO: Record<string, string> = {
  threshold: 'sensibilidade — "bem perto · perto · na mesma área" (não o número cru)',
  iou: 'a mesma escala de sensibilidade acima; IoU é o número por trás dela, não aparece',
  condition_satisfied: 'o bloco de preview: "você verá um evento quando ___"',
  'bounding box': 'zona (a área desenhada sobre a câmera)',
  overlap: 'entrar / estar dentro de "<lugar>"',
  polygon: 'zona / área desenhada',
  payload: '(não aparece — o que a tela mostra já é o evento, não o dado cru)',
  json: '(não aparece — regra em português; linha de contagem troca JSON cru por 2 pontos + sentido)',
  'confidence score': '(não aparece — fica atrás de "modo avançado": "números crus do motor")',
  inferência: '"o que a câmera reconhece" / "evento"',
  yolo: 'nome do modelo do cliente — alias Logikos, nunca o nome do motor',
  tracker: 'contagem / linha de contagem',
  rfdetr: 'nome do modelo do cliente — alias Logikos, nunca o nome do motor',
  'rf-detr': 'nome do modelo do cliente — alias Logikos, nunca o nome do motor',
  onnx: 'nome do modelo do cliente — alias Logikos, nunca o nome do motor',
  yolox: 'nome do modelo do cliente — alias Logikos, nunca o nome do motor',
}

/**
 * Detecção ESTRUTURAL: reconhece a FORMA de uma referência a código-fonte
 * (arquivo/função/issue), não uma palavra específica — cobre o que a
 * denylist fechada acima nunca vai listar (`tasks/inference.py`,
 * `_no_escopo_da_camera`, `#519`). Calibração e por quê cada uma não pega
 * falso-positivo real do repo: ver bloco "VOCABULÁRIO ESTRUTURAL" no topo
 * do arquivo.
 */
const ESTRUTURAIS: Array<{ nome: string; re: RegExp; sugestao: string }> = [
  {
    nome: 'arquivo .py',
    re: /[\w./-]*\.py\b/,
    sugestao: 'caminho de arquivo de implementação — não aparece pro cliente; se for útil, mova pro modo avançado (superadmin)',
  },
  {
    nome: 'escopo ::',
    re: /\S*::\S*/,
    sugestao: 'referência arquivo::função — mesma regra: some do texto padrão, ou vai pro modo avançado',
  },
  {
    nome: 'identificador _snake_case',
    // `(?<!\w)` garante underscore REALMENTE líder (início do identificador,
    // não um "_" no meio de um snake_case comum tipo `gate_list_reworks` —
    // achado real ao rodar contra o repo inteiro: sem o lookbehind, a régua
    // batia em "_list_reworks" DENTRO de `gate_list_reworks`, que não é o
    // padrão que queremos (função "privada" com "_" líder), é só um nome de
    // rota comum, mesma família de `bay_id`/`counting_events`).
    re: /(?<!\w)_[a-zA-Z][a-zA-Z0-9]*(?:_[a-zA-Z0-9]+)+/,
    sugestao: 'nome de função/identificador interno (underscore líder) — descreva o QUE faz, não o nome da função',
  },
  {
    nome: 'issue #NNN',
    re: /#\d{3,}\b/,
    sugestao: 'número de issue/PR interno — não aparece pro cliente; se for útil, vai pro modo avançado (superadmin)',
  },
]

/**
 * Sufixo de versão colado no nome do motor: `YOLOv8`, `YOLOv5`, `YOLO11`,
 * `YOLOv8n`, `RF-DETR-L2`.
 *
 * FURO REAL (rodada V1, set/2026): `\bYOLO\b` NÃO casa "YOLOv8" — o "v" é
 * word char, então não existe fronteira `\b` entre o "O" e o "v". Resultado
 * medido: o CI ficou VERDE com "visão computacional YOLOv8" na PRIMEIRA tela
 * que o cliente lê depois do login (`pages/ModuleSelectionPage.tsx:65`), no
 * bundle servido. A régua pegava "YOLO" sozinho e deixava passar exatamente
 * a forma que a gente de verdade escreve o nome do motor — com a versão.
 *
 * O grupo é opcional, então "YOLO" cru continua batendo. Só admite sufixo
 * que COMEÇA por dígito ou por "v"+dígito: pega toda versão real sem virar
 * `\bYOLO\w*`, que engoliria identificador tipo `YoloClass` se um dia
 * aparecer em texto visível.
 */
const SUFIXO_DE_VERSAO = '(?:-?v?\\d+[a-z]*)?'

function regexDoTermo(termo: string): RegExp {
  const escapado = termo.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/ /g, '\\s+')
  return new RegExp(`\\b${escapado}${SUFIXO_DE_VERSAO}\\b`, 'iu')
}

type Fragmento = { texto: string; linha: number }

/**
 * Extrai todo TEXTO VISÍVEL de um arquivo .ts/.tsx: `JsxText` e os 4
 * atributos de rótulo. Exportado para o `acharJargao` abaixo poder ser
 * exercitado com código sintético em memória (prova da régua, sem sujar
 * o repo com fixture).
 */
export function textosVisiveis(caminho: string, codigo: string): Fragmento[] {
  const sf = ts.createSourceFile(
    caminho,
    codigo,
    ts.ScriptTarget.Latest,
    true,
    caminho.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  )
  const frags: Fragmento[] = []

  function add(no: ts.Node) {
    const start = no.getStart(sf)
    const linhaBase = sf.getLineAndCharacterOfPosition(start).line + 1
    sf.text.slice(start, no.getEnd()).split('\n').forEach((sub, i) => {
      if (sub.trim()) frags.push({ texto: sub, linha: linhaBase + i })
    })
  }

  function addLiteral(lit: ts.StringLiteralLike) {
    frags.push({ texto: lit.text, linha: sf.getLineAndCharacterOfPosition(lit.getStart(sf)).line + 1 })
  }

  /**
   * `{cond ? 'a' : 'b'}` / `{cond && 'texto'}` são o jeito comum de
   * condicionar texto dentro de JSX — recorre só nesses dois formatos
   * (mais parênteses) até achar o(s) literal(is) de verdade renderizado(s).
   * Não desce em chamada de função: `{track('threshold_evt')}` fica de
   * fora de propósito — o argumento não é o que a tela mostra.
   */
  function literaisRenderaveis(expr: ts.Expression): ts.StringLiteralLike[] {
    if (ts.isStringLiteralLike(expr)) return [expr]
    if (ts.isParenthesizedExpression(expr)) return literaisRenderaveis(expr.expression)
    if (ts.isConditionalExpression(expr)) {
      return [...literaisRenderaveis(expr.whenTrue), ...literaisRenderaveis(expr.whenFalse)]
    }
    if (
      ts.isBinaryExpression(expr) &&
      [ts.SyntaxKind.AmpersandAmpersandToken, ts.SyntaxKind.BarBarToken, ts.SyntaxKind.QuestionQuestionToken]
        .includes(expr.operatorToken.kind)
    ) {
      return literaisRenderaveis(expr.right)
    }
    return []
  }

  function visita(no: ts.Node) {
    if (ts.isJsxText(no)) {
      add(no)
    } else if (ts.isJsxAttribute(no) && ATRIBUTOS_DE_TEXTO.has(no.name.getText(sf))) {
      const init = no.initializer
      if (init && ts.isStringLiteralLike(init)) addLiteral(init)
      else if (init && ts.isJsxExpression(init) && init.expression) {
        literaisRenderaveis(init.expression).forEach(addLiteral)
      }
    } else if (ts.isJsxExpression(no) && no.expression && !(no.parent && ts.isJsxAttribute(no.parent))) {
      // `{...}` como FILHO de JSX (não como valor de atributo — esse já
      // caiu no ramo acima): mesmo texto renderizado, outro formato de nó.
      literaisRenderaveis(no.expression).forEach(addLiteral)
    }
    ts.forEachChild(no, visita)
  }
  visita(sf)
  return frags
}

export type Achado = {
  termo: string
  trecho: string
  linha: number
  sugestao: string
  /** 'vocabulario' = bateu na denylist fechada; 'estrutural' = bateu num
   * PADRÃO de referência a código (arquivo/escopo/identificador/issue). */
  tipo: 'vocabulario' | 'estrutural'
}

/** Varre um arquivo e devolve os termos proibidos fora da exceção de modo avançado. */
export function acharJargao(caminho: string, codigo: string): Achado[] {
  const linhasBrutas = codigo.split('\n')
  const achados: Achado[] = []
  for (const frag of textosVisiveis(caminho, codigo)) {
    const foraDaExcecao = (linha: number) => !(linhasBrutas[linha - 2] ?? '').includes(MARCADOR_EXCECAO)
    for (const termo of TERMOS) {
      const m = frag.texto.match(regexDoTermo(termo))
      if (!m) continue
      if (!foraDaExcecao(frag.linha)) continue
      achados.push({
        termo: m[0],
        trecho: frag.texto.trim(),
        linha: frag.linha,
        sugestao: TRADUCAO[termo.toLowerCase()] ?? '(sem tradução mapeada — reveja a aba Microcopy do desenho)',
        tipo: 'vocabulario',
      })
    }
    for (const estrutural of ESTRUTURAIS) {
      const m = frag.texto.match(estrutural.re)
      if (!m) continue
      if (!foraDaExcecao(frag.linha)) continue
      achados.push({
        termo: m[0],
        trecho: frag.texto.trim(),
        linha: frag.linha,
        sugestao: estrutural.sugestao,
        tipo: 'estrutural',
      })
    }
  }
  return achados
}

function arquivos(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) return arquivos(p)
    // Testes ficam de fora: mock de "yolo26n"/"onnx" em fixture não é texto
    // pintado na tela — é exatamente o que os testes do alias Logikos
    // (Modelo.test.tsx etc.) precisam poder escrever.
    return /\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name) ? [p] : []
  })
}

const COMPONENTS = path.join(path.dirname(APP), 'components')

/**
 * Telas do front LEGADO que o tenant lê HOJE e que não são alcançáveis a
 * partir de `src/app` — entram na régua nominalmente, uma a uma.
 *
 * SEGUNDO furo da mesma rodada V1: `ModuleSelectionPage` é a primeira tela
 * depois do login (o seletor de módulo), mora em `src/pages/` e por isso
 * NUNCA foi lida por esta régua — nem com a regex consertada o achado
 * apareceria. Os dois furos juntos são o motivo de o CI estar verde com o
 * nome do motor na cara do cliente.
 *
 * NÃO varremos `src/pages/**` inteiro de propósito: ver "ESCOPO DE ARQUIVOS"
 * no topo — isso traz ~20 achados de telas de outra rodada, que este PR não
 * tem mandato para reescrever. Toda tela legada que o cliente de fato abrir
 * entra aqui, nominalmente, com o conserto do texto no mesmo commit.
 */
const RAIZES_LEGADO_EM_ESCOPO = [
  path.join(path.dirname(APP), 'pages', 'ModuleSelectionPage.tsx'),
]

/** `import ... from '../coisa'` / `export ... from './coisa'` — só
 * specifiers RELATIVOS (começam com `.`): é tudo que o front usa (repo não
 * tem alias `@/` em uso — conferido). */
function importsRelativos(caminho: string): string[] {
  const codigo = fs.readFileSync(caminho, 'utf-8')
  const re = /(?:import|export)(?:[^'";]*?)from\s+['"](\.[^'"]+)['"]/g
  const specifiers: string[] = []
  let m: RegExpExecArray | null
  while ((m = re.exec(codigo))) specifiers.push(m[1])
  return specifiers
}

function resolveImport(arquivoBase: string, specifier: string): string | null {
  const candidato = path.resolve(path.dirname(arquivoBase), specifier)
  const tentativas = [
    candidato, `${candidato}.tsx`, `${candidato}.ts`,
    path.join(candidato, 'index.tsx'), path.join(candidato, 'index.ts'),
  ]
  return tentativas.find((t) => fs.existsSync(t) && fs.statSync(t).isFile()) ?? null
}

/**
 * Conjunto de arquivos que a régua varre: `src/app/**` (front novo) MAIS
 * todo arquivo de `src/components/**` alcançável a partir dele por import
 * relativo transitivo (BFS). Ver "ESCOPO DE ARQUIVOS" no topo do arquivo —
 * é o critério que pega `CameraModelScope.tsx` (achado real) sem trazer
 * telas do front legado que só `pages/`/`modules/` ainda usam.
 */
export function arquivosVisiveisAoTenant(): string[] {
  const raizes = arquivos(APP)
  const visitados = new Set(raizes)
  const fila = [...raizes]
  while (fila.length) {
    const atual = fila.pop() as string
    for (const specifier of importsRelativos(atual)) {
      const resolvido = resolveImport(atual, specifier)
      if (resolvido && !visitados.has(resolvido)) {
        visitados.add(resolvido)
        fila.push(resolvido)
      }
    }
  }
  const alcancados = [...visitados].filter(
    (f) => f.startsWith(APP + path.sep) || f.startsWith(COMPONENTS + path.sep),
  )
  // Somados DEPOIS do filtro (moram em `src/pages`) e sem semear a BFS: só
  // a tela em si entra, não a árvore de imports legada pendurada nela.
  return [...alcancados, ...RAIZES_LEGADO_EM_ESCOPO.filter((f) => !alcancados.includes(f))]
}

describe('front novo: sem jargão técnico em texto de cliente', () => {
  it('nenhum termo da régua aparece fora do modo avançado', () => {
    const relatorio: string[] = []
    for (const arquivo of arquivosVisiveisAoTenant()) {
      const rel = path.relative(APP, arquivo)
      const codigo = fs.readFileSync(arquivo, 'utf-8')
      for (const a of acharJargao(rel, codigo)) {
        relatorio.push(`${rel}:${a.linha}  [${a.tipo}] "${a.termo}" em "${a.trecho}"  →  use: ${a.sugestao}`)
      }
    }
    expect(
      relatorio,
      `jargão técnico em texto de tenant — traduza (aba Microcopy do desenho ` +
        `"Cenário e Operações.dc.html") ou marque \`// ${MARCADOR_EXCECAO}: <motivo>\` ` +
        `na linha anterior se for modo avançado (superadmin):\n${relatorio.join('\n')}`,
    ).toEqual([])
  })
})

describe('escopo: a régua alcança components/** renderizado pelo front novo (furo B3.a)', () => {
  it('inclui CameraModelScope.tsx (achado real — renderizado via app/estudio/ModelosPorCamera.tsx)', () => {
    const alvo = arquivosVisiveisAoTenant()
    expect(alvo.some((f) => f.endsWith(path.join('components', 'training', 'CameraModelScope.tsx')))).toBe(true)
  })

  it('inclui pages/ModuleSelectionPage.tsx (primeira tela pós-login — furo V1.a)', () => {
    const alvo = arquivosVisiveisAoTenant()
    expect(alvo.some((f) => f.endsWith(path.join('pages', 'ModuleSelectionPage.tsx')))).toBe(true)
  })

  it('NÃO inclui telas só do front legado (pages/modules) — evita trazer dívida de outra rodada', () => {
    const alvo = arquivosVisiveisAoTenant()
    const legado = [
      path.join('components', 'training', 'modals', 'OperationCreateModal.tsx'),
      path.join('components', 'scenario', 'ScenarioEditor.tsx'),
      path.join('components', 'cameras', 'CameraFpsConfig.tsx'),
    ]
    for (const rel of legado) {
      expect(alvo.some((f) => f.endsWith(rel)), `${rel} não devia estar alcançável a partir de src/app`).toBe(false)
    }
  })
})

describe('a régua funciona (fixture em memória — nada gravado no repo)', () => {
  it('acusa jargão em texto JSX visível', () => {
    const codigo = `export const X = () => <span>Ajuste o threshold do alerta</span>\n`
    const achados = acharJargao('fixture.tsx', codigo)
    expect(achados).toHaveLength(1)
    expect(achados[0].termo.toLowerCase()).toBe('threshold')
    expect(achados[0].sugestao).toMatch(/sensibilidade/)
  })

  it('não acusa identificador, prop de dado nem comentário — só texto visível', () => {
    const codigo = [
      '// threshold vem do backend em m.threshold, YOLO é o framework interno',
      'interface Props { threshold: number; framework: string }',
      "const YoloClass = 'x'",
      'export const X = ({ threshold, framework }: Props) => (',
      '  <span data-framework={framework}>{threshold}</span>',
      ')',
      '',
    ].join('\n')
    expect(acharJargao('fixture.tsx', codigo)).toEqual([])
  })

  it('JSON.parse no código não dispara — "exportar JSON" no botão dispara', () => {
    const codigo = [
      'export const X = () => {',
      "  const dados = JSON.parse('{}')",
      '  return <button>{dados ? "exportar JSON" : "carregando"}</button>',
      '}',
      '',
    ].join('\n')
    const achados = acharJargao('fixture.tsx', codigo)
    expect(achados).toHaveLength(1)
    expect(achados[0].trecho).toBe('exportar JSON')
  })

  it('marcador `// jargao-ok` na linha anterior suspende a régua (modo avançado)', () => {
    const codigo = [
      'export const X = ({ isSuperAdmin }: { isSuperAdmin: boolean }) => isSuperAdmin && (',
      '  // jargao-ok: modo avançado (superadmin) — números crus do motor',
      '  <span>IoU {"0.10"} · confidence score bruto</span>',
      ')',
      '',
    ].join('\n')
    expect(acharJargao('fixture.tsx', codigo)).toEqual([])
  })

  it('sem o marcador, o mesmo trecho acusa dois termos', () => {
    const codigo = [
      'export const X = ({ isSuperAdmin }: { isSuperAdmin: boolean }) => isSuperAdmin && (',
      '  <span>IoU {"0.10"} · confidence score bruto</span>',
      ')',
      '',
    ].join('\n')
    const achados = acharJargao('fixture.tsx', codigo)
    expect(achados.map((a) => a.termo.toLowerCase()).sort()).toEqual(['confidence score', 'iou'])
  })

  it('atributo title/aria-label/placeholder/alt conta como texto visível', () => {
    const codigo = 'export const X = () => <img alt="bounding box detectado" title="overlap alto" />\n'
    const achados = acharJargao('fixture.tsx', codigo)
    expect(achados.map((a) => a.termo.toLowerCase()).sort()).toEqual(['bounding box', 'overlap'])
  })
})

describe('nome do motor com versão colada (furo V1.b — `\\bYOLO\\b` não casa "YOLOv8")', () => {
  it.each(['YOLOv8', 'YOLOv5', 'YOLO11', 'YOLOv8n', 'yolov8'])('pega %s', (nome) => {
    const achados = acharJargao('fixture.tsx', `export const X = () => <p>visão computacional ${nome}.</p>\n`)
    expect(achados.map((a) => a.termo)).toEqual([nome])
    expect(achados[0].sugestao).toMatch(/alias Logikos/)
  })

  it('"YOLO" cru continua batendo (o sufixo é opcional)', () => {
    const achados = acharJargao('fixture.tsx', 'export const X = () => <p>motor YOLO aqui</p>\n')
    expect(achados.map((a) => a.termo)).toEqual(['YOLO'])
  })

  it('não vira `\\bYOLO\\w*`: sufixo só de LETRA não dispara (identificador em texto)', () => {
    // `YoloClass` não é o nome do motor com versão — é um identificador.
    // O guard só admite sufixo que começa por dígito (ou "v"+dígito).
    expect(acharJargao('fixture.tsx', 'export const X = () => <p>o campo YoloClass</p>\n')).toEqual([])
  })

  it('prova por MUTAÇÃO no arquivo REAL: reinstalar o texto servido acusa a linha', () => {
    // Texto que estava em produção em `pages/ModuleSelectionPage.tsx:65`
    // (bundle servido) e que passou pelo CI verde: os DOIS furos juntos —
    // arquivo fora do escopo E `\bYOLO\b` sem casar "YOLOv8".
    const codigo = [
      'export const X = () => (',
      '  <p>',
      '    Monitoramento inteligente de Equipamentos de Proteção Individual.',
      '    Detecção em tempo real via câmeras CCTV com visão computacional YOLOv8.',
      '  </p>',
      ')',
      '',
    ].join('\n')
    const achados = acharJargao('pages/ModuleSelectionPage.tsx', codigo)
    expect(achados.map((a) => a.termo)).toEqual(['YOLOv8'])
    expect(achados[0].linha).toBe(4)
  })
})

describe('detecção estrutural: referência a código-fonte em texto de UI (furo B3.b)', () => {
  it('pega arquivo .py', () => {
    const achados = acharJargao('fixture.tsx', 'export const X = () => <span>ajustado em tasks/inference.py</span>\n')
    expect(achados.some((a) => a.tipo === 'estrutural' && a.termo.endsWith('.py'))).toBe(true)
  })

  it('pega escopo ::', () => {
    const achados = acharJargao('fixture.tsx', 'export const X = () => <span>regra em tasks/inference.py::_resolve_camera_model</span>\n')
    expect(achados.some((a) => a.tipo === 'estrutural' && a.termo.includes('::'))).toBe(true)
  })

  it('pega identificador _snake_case com underscore líder', () => {
    const achados = acharJargao('fixture.tsx', 'export const X = () => <span>bloqueado por _no_escopo_da_camera</span>\n')
    expect(achados.some((a) => a.tipo === 'estrutural' && a.termo === '_no_escopo_da_camera')).toBe(true)
  })

  it('pega issue #NNN (3+ dígitos)', () => {
    const achados = acharJargao('fixture.tsx', 'export const X = () => <span>pendência rastreada na issue #519</span>\n')
    expect(achados.some((a) => a.tipo === 'estrutural' && a.termo === '#519')).toBe(true)
  })

  it('calibração: "#1" de ranking e "v1.2" de versão NÃO disparam (só #\\d{3,})', () => {
    const codigo = [
      'export const X = () => (',
      '  <div>',
      '    <span>Câmera #1 do ranking do mês</span>',
      '    <span>Guia da versão v1.2</span>',
      '  </div>',
      ')',
      '',
    ].join('\n')
    expect(acharJargao('fixture.tsx', codigo)).toEqual([])
  })

  it('calibração: nome de coluna/campo já mostrado hoje (sem underscore líder) não dispara', () => {
    // Mesmo padrão real de `carga/Carga.tsx` (<code>bay_id</code>,
    // <code>counting_events</code>) — dado legítimo, não referência a função.
    const codigo = 'export const X = () => <code>counting_events</code>\n'
    expect(acharJargao('fixture.tsx', codigo)).toEqual([])
  })

  it('marcador `// jargao-ok` também suspende achado estrutural (mesmo modo avançado)', () => {
    const codigo = [
      'export const X = ({ isSuperAdmin }: { isSuperAdmin: boolean }) => isSuperAdmin && (',
      '  // jargao-ok: modo avançado (superadmin) — referência de implementação',
      '  <span>tasks/inference.py::_no_escopo_da_camera · issue #519</span>',
      ')',
      '',
    ].join('\n')
    expect(acharJargao('fixture.tsx', codigo)).toEqual([])
  })

  it('prova por MUTAÇÃO: reinstalar o texto antigo do banner (achado real) — a régua pega os 4 furos juntos', () => {
    // Texto que estava em produção em `CameraModelScope.tsx` antes do
    // conserto desta rodada (achado B3) — reinstalado aqui como fixture,
    // sem sujar o repo. Antes desta rodada (escopo só `src/app` + denylist
    // fechada) NADA disto disparava: nem o arquivo era lido, nem os termos
    // estavam na lista.
    const codigo = [
      'export const X = () => (',
      '  <Banner variant="warning">',
      '    Será substituído pela matriz de exigência da RVB (issue #535) — uma área sem nenhuma luva anotada.',
      '    Onde este escopo vale hoje: no shadow sobre os frames que o box envia E no worker de inferência da nuvem, que passou a descartar detecção fora do escopo antes de virar violação (tasks/inference.py::_no_escopo_da_camera). O box edge ainda NÃO recebe classe por câmera — essa ponta segue aberta na issue #519.',
      '  </Banner>',
      ')',
      '',
    ].join('\n')
    const achados = acharJargao('components/training/CameraModelScope.tsx', codigo)
    expect(achados.some((a) => a.tipo === 'vocabulario' && a.termo === 'inferência')).toBe(true)
    expect(achados.some((a) => a.tipo === 'estrutural' && a.termo.includes('.py'))).toBe(true)
    expect(achados.some((a) => a.tipo === 'estrutural' && a.termo.includes('::'))).toBe(true)
    expect(achados.some((a) => a.tipo === 'estrutural' && a.termo === '_no_escopo_da_camera')).toBe(true)
    expect(achados.filter((a) => /^#\d{3,}$/.test(a.termo)).map((a) => a.termo).sort()).toEqual(['#519', '#535'])
    // não fica silencioso — a mutação FALHA a régua, como devia (é o que prova que a régua funciona)
    expect(achados.length).toBeGreaterThanOrEqual(5)
  })
})
