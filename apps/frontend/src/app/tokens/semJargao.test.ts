/**
 * Trava: jargão técnico não aparece em TEXTO VISÍVEL de superfície de
 * TENANT, em `src/app/**` (o front novo).
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
 * ─── ESTRATÉGIA ANTI-FALSO-POSITIVO ─────────────────────────────────────
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

function regexDoTermo(termo: string): RegExp {
  const escapado = termo.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/ /g, '\\s+')
  return new RegExp(`\\b${escapado}\\b`, 'iu')
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

export type Achado = { termo: string; trecho: string; linha: number; sugestao: string }

/** Varre um arquivo e devolve os termos proibidos fora da exceção de modo avançado. */
export function acharJargao(caminho: string, codigo: string): Achado[] {
  const linhasBrutas = codigo.split('\n')
  const achados: Achado[] = []
  for (const frag of textosVisiveis(caminho, codigo)) {
    for (const termo of TERMOS) {
      const m = frag.texto.match(regexDoTermo(termo))
      if (!m) continue
      const linhaAnterior = linhasBrutas[frag.linha - 2] ?? ''
      if (linhaAnterior.includes(MARCADOR_EXCECAO)) continue
      achados.push({
        termo: m[0],
        trecho: frag.texto.trim(),
        linha: frag.linha,
        sugestao: TRADUCAO[termo.toLowerCase()] ?? '(sem tradução mapeada — reveja a aba Microcopy do desenho)',
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

describe('front novo: sem jargão técnico em texto de cliente', () => {
  it('nenhum termo da régua aparece fora do modo avançado', () => {
    const relatorio: string[] = []
    for (const arquivo of arquivos(APP)) {
      const rel = path.relative(APP, arquivo)
      const codigo = fs.readFileSync(arquivo, 'utf-8')
      for (const a of acharJargao(rel, codigo)) {
        relatorio.push(`${rel}:${a.linha}  "${a.termo}" em "${a.trecho}"  →  use: ${a.sugestao}`)
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
