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
 * ATUALIZAÇÃO (rodada O2, issue #660): a estimativa de "~20 achados" acima
 * foi MEDIDA e vale para `src/components/**`, não para o front legado —
 * `src/pages/**` + `src/modules/**` inteiros dão DEZ achados, sete deles em
 * arquivos de outras frentes. Por isso a lista nominal
 * (`RAIZES_LEGADO_EM_ESCOPO`, um arquivo) caiu: hoje a régua varre esses dois
 * diretórios POR INTEIRO, com os sete arquivos de outra frente congelados um
 * a um em `DEBITO_DE_OUTRA_FRENTE`. Ver o bloco lá embaixo.
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
 * ATUALIZAÇÃO (rodada V1, set/2026 — jargão final): as 4 formas acima ficaram
 * VERDES enquanto o bundle SERVIDO do DEV mostrava três coisas na cara do
 * usuário. Não foi escopo nem string montada em runtime — os arquivos já eram
 * varridos e os textos já eram `JsxText` literal. Faltavam TRÊS formas:
 *   - `rota de API`        → `GET /API/MODULES/EPI/STATS` (epi/Dashboard.tsx:530)
 *   - `issue` sem "#"      → `(issue 519)`                (epi/Cameras.tsx:365)
 *   - `chave de permissão` → `(requer cameras:configure)` (epi/Cameras.tsx:366)
 * As três estão abaixo, cada uma com prova por mutação NO ARQUIVO REAL (bloco
 * "rodada V1" no fim deste arquivo). Elas acusaram 51 trechos em 22 telas; as
 * 3 do mandato deste PR foram traduzidas, os outros 41 pares estão congelados
 * um a um em `DEBITO_ESTRUTURAL_V1`.
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

/**
 * Atributos que viram texto/rótulo na tela: os 4 que o NAVEGADOR expõe
 * (`title`/`aria-label`/`placeholder`/`alt`) mais as 3 props de COPY que o
 * front usa para passar frase pronta a um componente de apresentação
 * (`desc`/`description`/`label`).
 *
 * As 3 últimas são o furo C da rodada O2 (issue #660): `HomePage.tsx:123`
 * passava `desc="…inspeção visual YOLO…"` para `<ModuleCard>` — texto que o
 * tenant lê, invisível para a régua porque `desc` não era nem `JsxText` nem
 * um dos 4 atributos. Não são convenção inventada: são as props que os
 * componentes de card deste repo já recebem.
 */
const ATRIBUTOS_DE_TEXTO = new Set([
  'title', 'aria-label', 'placeholder', 'alt', 'desc', 'description', 'label',
])

/**
 * Chaves de OBJETO que carregam copy: catálogo declarativo (`const CATALOGO =
 * [{ title: '…', description: '…' }]`) espalhado pelo componente por `.map()`.
 *
 * Furo D da mesma rodada: `modules/admin/components/IntegrationsPanel.tsx:62`
 * tinha `description: 'Treinamento de modelos YOLO em GPUs sob demanda.'` num
 * array de catálogo — renderizado como `<div>{item.description}</div>`, mas
 * a régua só via o `{item.description}` (uma property access, não literal).
 *
 * Falso positivo é limitado por CONSTRUÇÃO: a denylist é fechada (12 termos +
 * família de motor), então só dispara se a copy contiver de fato um daqueles
 * termos — `{ key: 'account_id', label: 'Access Key ID' }` não bate em nada.
 */
const CHAVES_DE_COPY = new Set(['title', 'description', 'desc', 'label', 'subtitle'])

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
    // FURO REAL (rodada V1, set/2026): `#\d{3,}` exige o "#", e o texto
    // servido em `app/epi/Cameras.tsx:365` escrevia "(issue 519)" — sem "#".
    // A régua ficou VERDE com o número de issue na cara do usuário. O "#" é
    // opcional quando a PALAVRA "issue"/"PR" já diz o que o número é.
    nome: 'issue #NNN',
    // O ramo da PALAVRA não aceita "#" — assim "issue #519" continua sendo
    // acusado como `#519` (a calibração antiga, com teste), e "issue 519"
    // entra pelo ramo novo.
    re: /#\d{3,}\b|\b(?:issues?|PRs?)\s+n?º?\s*\d+\b/i,
    sugestao: 'número de issue/PR interno — não aparece pro cliente; se for útil, vai pro modo avançado (superadmin)',
  },
  {
    // FURO REAL (rodada V1, set/2026): `app/epi/Dashboard.tsx:530` pintava
    // `GET /API/MODULES/EPI/STATS` no estado de erro — a rota crua da API como
    // única explicação de "não foi possível carregar". Nenhum dos 16 termos e
    // nenhuma das 3 formas estruturais de então batia nisso.
    //
    // Duas formas, ambas medidas no repo: verbo HTTP + caminho, e caminho que
    // começa por `/api/` ou `/v1/` (as duas bases que este front chama).
    // Não vira `\S*/\S*`: "24/7", "km/h" e data "05/09" não têm nem verbo nem
    // base — passam por CONSTRUÇÃO. A base é `api|v1` LITERAL, não `v\d`:
    // com `v\d` o texto real "(V1/V2/V3 = etapa da bancada)" de
    // `qualidade/GestaoQualidade.tsx:507` batia em "/V2/V3" — falso positivo
    // medido, não hipótese.
    nome: 'rota de API',
    re: /\b(?:GET|POST|PUT|PATCH|DELETE)\s+\/\S*|\/(?:api|v1)\/[\w/{}:.-]+/i,
    sugestao: 'rota da API — diga o que falhou ("não foi possível carregar os indicadores"), não o endereço; se for útil, vai pro modo avançado (superadmin)',
  },
  {
    // FURO REAL (rodada V1, set/2026): `app/epi/Cameras.tsx:366` pintava
    // "(requer cameras:configure)" — a CHAVE de permissão do registry, não o
    // nome do que o usuário precisa pedir. A forma `escopo ::` exige DOIS
    // dois-pontos; um só passava batido.
    //
    // Calibração: exige minúscula dos dois lados e ZERO espaço, então "Nota:
    // texto" (tem espaço), "10:30" (dígito) e "https://x" (o `//` quebra o
    // lado direito) não batem — todos conferidos contra o repo.
    nome: 'chave de permissão',
    re: /(?<![\w:/.])[a-z][a-z_]*:[a-z][a-z_*]+(?![\w:/])/,
    sugestao: 'chave de permissão do registry — diga o PODER em português ("permissão para configurar câmeras"), não a chave',
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
    } else if (
      ts.isPropertyAssignment(no) &&
      (ts.isIdentifier(no.name) || ts.isStringLiteralLike(no.name)) &&
      CHAVES_DE_COPY.has(ts.isIdentifier(no.name) ? no.name.text : no.name.text)
    ) {
      literaisRenderaveis(no.initializer).forEach(addLiteral)
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

const PAGES = path.join(path.dirname(APP), 'pages')
const MODULES = path.join(path.dirname(APP), 'modules')

/**
 * FRONT LEGADO — `src/pages/**` e `src/modules/**`, varridos POR INTEIRO.
 *
 * Terceiro furo da mesma família (issue #660, rodada O2). A rodada V1 tinha
 * fechado o furo de `src/components/**` e adicionado UMA tela de `src/pages`
 * nominalmente (`ModuleSelectionPage`), registrando na própria issue a
 * ESTIMATIVA de que varrer `src/pages/**` + `src/modules/**` inteiros traria
 * "~20 achados de outras rodadas" — cedo demais para este PR.
 *
 * A estimativa foi MEDIDA, e é o motivo de a lista nominal ter caído: com a
 * régua de hoje (sem os furos C e D abaixo) o total do front legado inteiro
 * é DEZ, não vinte — e cinco deles são os desta issue. Lista nominal, um
 * arquivo por vez, deixa a próxima tela entrar roxa/com jargão sem ninguém
 * ver; escopo inteiro + débito NOMEADO abaixo não deixa.
 *
 * É esse o front que os usuários da RVB abrem: `/quality/*`, `/epi/*` e o
 * seletor de módulo moram aqui, não em `src/app`.
 */
/**
 * Débito de OUTRAS frentes — arquivos com jargão real que este PR não tem
 * mandato para reescrever (outro agente está neles). Congelado por ARQUIVO,
 * mesmo espírito da ALLOWLIST do guard-rail de cor. Achados medidos:
 *
 *   DashboardIntegradoPage.tsx   `payload`, `scripts/…​.py`         (2)
 *   fueling/FuelingValidationPage.tsx  `threshold` ×2               (2)
 *   monitoring/InferencePanel.tsx      `Inferência` ×2              (2)
 *   monitoring/SiteMonitor.tsx         `Inferência`                 (1)
 *   admin/pages/observability/{EdgeFleet,Streams,Workers}Panel.tsx  (3)
 *
 * Rastreados na issue aberta junto com este PR. Tirar um arquivo desta lista
 * é o conserto — nada aqui expira sozinho.
 */
const DEBITO_DE_OUTRA_FRENTE = [
  // --- telas do front legado (medido na rodada O2) ---
  'pages/DashboardIntegradoPage.tsx',
  'pages/fueling/FuelingValidationPage.tsx',
  'pages/monitoring/InferencePanel.tsx',
  'pages/monitoring/SiteMonitor.tsx',
  'modules/admin/pages/observability/EdgeFleetPanel.tsx',
  'modules/admin/pages/observability/StreamsPanel.tsx',
  'modules/admin/pages/observability/WorkersPanel.tsx',
  // --- componentes RENDERIZADOS pelo front legado (furo F, cético O2) ---
  //
  // Estes NÃO são órfãos: são o texto que as rotas EPI da RVB pintam na
  // tela, e ficavam invisíveis porque a BFS só era semeada a partir de
  // `src/app`. Cadeia medida:
  //   /epi/cameras/:id/operations → EpiOperationsPage → TrainingModeLayout
  //        → OperationCreateModal/OperationEditModal → operationTypeForms/*
  //   /epi/cameras/:id/scenario   → EpiScenarioEditorPage → ScenarioEditor
  //   /epi/training               → TrainingPage → (mesmos modais)
  // Nenhuma dessas rotas redireciona para o front novo (AppRoutes.tsx).
  //
  //   scenario/ScenarioEditor.tsx                  `Threshold` x2      (2)
  //   cameras/CameraFpsConfig.tsx                  `inferência`        (1)
  //   training/modals/OperationCreateModal.tsx     `JSON` x2           (2)
  //   training/modals/OperationEditModal.tsx       `JSON`              (1)
  //   training/operationTypeForms/CountStaticForm.tsx    `threshold` x3 (3)
  //   training/operationTypeForms/OverlapDynamicForm.tsx `IoU`/`Threshold` (3)
  //   training/operationTypeForms/OverlapFixedForm.tsx   `Threshold`/`condition_satisfied` (2)
  //   training/operationTypeForms/ZoneTuningForm.tsx     `JSON` x3      (3)
  'components/scenario/ScenarioEditor.tsx',
  'components/cameras/CameraFpsConfig.tsx',
  'components/training/modals/OperationCreateModal.tsx',
  'components/training/modals/OperationEditModal.tsx',
  'components/training/operationTypeForms/CountStaticForm.tsx',
  'components/training/operationTypeForms/OverlapDynamicForm.tsx',
  'components/training/operationTypeForms/OverlapFixedForm.tsx',
  'components/training/operationTypeForms/ZoneTuningForm.tsx',
]

/**
 * DÉBITO ESTRUTURAL V1 — congelado por PAR `arquivo|termo`, não por arquivo.
 *
 * As três formas novas desta rodada (rota de API, chave de permissão, issue
 * sem "#") acusaram 51 trechos em 22 telas. Este PR tem mandato sobre TRÊS
 * arquivos (`epi/Dashboard.tsx`, `epi/Cameras.tsx`, `epi/Eventos.tsx` — as
 * telas das strings medidas no bundle servido e das issues #771/#795); os
 * outros 41 pares ficam NOMEADOS aqui, um a um, com a issue aberta junto com
 * este PR.
 *
 * Por PAR e não por ARQUIVO de propósito: congelar o arquivo inteiro
 * devolveria a cegueira que esta rodada acabou de tirar — uma rota NOVA em
 * `epi/Acoes.tsx` entraria calada. Congelado o par exato, qualquer rota ou
 * chave nova no mesmo arquivo continua reprovando.
 *
 * NÃO É UM CEMITÉRIO: o teste `o débito congelado ainda descreve achado real`
 * abaixo reprova se um par deixar de casar — quem consertar a tela é obrigado
 * a apagar a linha daqui.
 *
 * Caminho relativo a `src/`. Formato: `<arquivo>|<termo exato acusado>`.
 */
const DEBITO_ESTRUTURAL_V1 = [
  'app/admin/Auditoria.tsx|GET /v1/admin/audit-log',
  'app/admin/TenantDetalhe.tsx|/v1/admin/tenants/',
  'app/admin/TenantDetalhe.tsx|GET /v1/admin/tenants/',
  'app/admin/Tenants.tsx|GET /v1/admin/tenants',
  'app/admin/Usuarios.tsx|GET /v1/admin/users',
  'app/admin/VisaoGeral.tsx|GET /v1/admin/dashboard',
  'app/carga/Carga.tsx|GET /api',
  'app/carga/Carga.tsx|GET /api/fueling/events',
  'app/carga/Carga.tsx|PATCH /sessions/<id>',
  'app/carga/Carga.tsx|counting:read',
  'app/carga/Carga.tsx|counting:write',
  'app/epi/Acoes.tsx|GET /api/alerts',
  'app/epi/AoVivo.tsx|GET /cameras',
  'app/epi/AoVivo.tsx|cameras:read',
  'app/epi/Cenario.tsx|GET /api/cameras/',
  'app/epi/EventoDetalhe.tsx|GET /api/alerts/',
  'app/epi/EventoDetalhe.tsx|verification:write',
  'app/epi/Operacoes.tsx|GET /api/cameras/',
  'app/epi/Operacoes.tsx|PUT /operations/<id>',
  'app/epi/Relatorios.tsx|GET /api',
  'app/epi/Relatorios.tsx|reports:export',
  'app/epi/Verificacao.tsx|GET /api/verification/queue',
  'app/epi/Verificacao.tsx|verification:read',
  'app/epi/Verificacao.tsx|verification:write',
  'app/estudio/CamerasPorModulo.tsx|GET /api',
  'app/estudio/Classes.tsx|GET /api',
  'app/estudio/Modelo.tsx|GET /api/training/models',
  'app/modulos/Modulos.tsx|GET /api/modules',
  'app/qualidade/ConfigQualidade.tsx|GET /api',
  'app/qualidade/GestaoQualidade.tsx|GET /api',
  'app/qualidade/GestaoQualidade.tsx|GET /v1/quality/gate/pieces/export',
  'app/qualidade/GestaoQualidade.tsx|reports:export',
  'app/qualidade/Qualidade.tsx|PATCH /gate/reworks/<id>/complete',
  'app/qualidade/Qualidade.tsx|quality:write',
  'app/qualidade/RevisaoQualidade.tsx|GET /api',
  'app/qualidade/RevisaoQualidade.tsx|GET /inspections',
  'app/qualidade/RevisaoQualidade.tsx|GET /reference-snapshots/&lt;camera_id&gt;',
  'app/qualidade/RevisaoQualidade.tsx|PATCH /inspections/<id>/feedback',
  'app/qualidade/RevisaoQualidade.tsx|verification:read',
  'app/qualidade/RevisaoQualidade.tsx|verification:write',
  'modules/admin/pages/AdminAnnouncementsPage.tsx|tenant:uuid',
]

function ehDebitoDeOutraFrente(arquivo: string): boolean {
  const rel = path.relative(path.dirname(APP), arquivo).split(path.sep).join('/')
  return DEBITO_DE_OUTRA_FRENTE.includes(rel)
}

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
const SRC = path.dirname(APP)

/** Caminho do arquivo relativo a `src/` — a chave do `DEBITO_ESTRUTURAL_V1`. */
function relDoSrc(arquivo: string): string {
  return path.relative(SRC, arquivo).split(path.sep).join('/')
}

/**
 * MEMO — issue #766: este cálculo varre `src/app` + `src/pages` + `src/modules`
 * e faz uma BFS de imports sobre `src/components`. Nove testes deste arquivo o
 * chamam; sem memo, a árvore inteira era relida NOVE vezes (22 ms cada,
 * medidos), ~180 ms de trabalho puramente repetido num arquivo que já estourava
 * o teto de 5 s em máquina de dev. O conteúdo do repo não muda no meio da
 * suíte, então o resultado é o mesmo nas nove.
 */
let memoAlvo: string[] | null = null

/** Só para o teste que PROVA a memoização — conta quantas vezes a árvore foi varrida. */
export const contadorDeVarreduras = { valor: 0 }

export function arquivosVisiveisAoTenant(): string[] {
  if (memoAlvo) return memoAlvo
  memoAlvo = calcularArquivosVisiveisAoTenant()
  return memoAlvo
}

function calcularArquivosVisiveisAoTenant(): string[] {
  contadorDeVarreduras.valor += 1
  // Semeada TAMBÉM a partir do front legado (furo F, cético da rodada O2):
  // sem isto, 38 arquivos de `src/components/**` renderizados por `/epi/*`
  // ficavam invisíveis — 17 achados de jargão, medidos, nas telas de
  // operação e de cenário que o operador da RVB abre.
  const raizes = [...arquivos(APP), ...arquivos(PAGES), ...arquivos(MODULES)]
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
    (f) =>
      (f.startsWith(APP + path.sep) || f.startsWith(COMPONENTS + path.sep)) &&
      !ehDebitoDeOutraFrente(f),
  )
  // Somado DEPOIS do filtro: as próprias telas de `pages/`/`modules/` não
  // passam no filtro acima (não moram em app/ nem components/).
  const legado = [...arquivos(PAGES), ...arquivos(MODULES)].filter(
    (f) => !alcancados.includes(f) && !ehDebitoDeOutraFrente(f),
  )
  return [...alcancados, ...legado]
}

/**
 * TETO DE TEMPO (issue #766) — o caso pesado varre 352 arquivos e faz AST de
 * todos. Medido nesta máquina: 640 ms sozinho; medido pelo relator da #766 num
 * laptop sob carga: 5.986 ms contra o `testTimeout` padrão de 5.000 ms. Verde
 * no CI, vermelho no laptop: o teste dependia da VELOCIDADE DA MÁQUINA.
 *
 * 30 s é ~5× o pior número já medido — folga que não some porque alguém abriu
 * o Chrome. O trabalho em si também caiu (a BFS deixou de rodar 9 vezes, ver
 * `arquivosVisiveisAoTenant`), mas o custo do AST é intrínseco: o teto tinha de
 * ser explícito e proporcional ao que o caso varre, não o default de 5 s.
 */
const TETO_DA_VARREDURA_MS = 30_000

describe('front novo: sem jargão técnico em texto de cliente', () => {
  it('nenhum termo da régua aparece fora do modo avançado', () => {
    const relatorio: string[] = []
    for (const arquivo of arquivosVisiveisAoTenant()) {
      const rel = path.relative(APP, arquivo)
      const congelados = new Set(DEBITO_ESTRUTURAL_V1)
      const codigo = fs.readFileSync(arquivo, 'utf-8')
      for (const a of acharJargao(rel, codigo)) {
        if (congelados.has(`${relDoSrc(arquivo)}|${a.termo}`)) continue
        relatorio.push(`${rel}:${a.linha}  [${a.tipo}] "${a.termo}" em "${a.trecho}"  →  use: ${a.sugestao}`)
      }
    }
    expect(
      relatorio,
      `jargão técnico em texto de tenant — traduza (aba Microcopy do desenho ` +
        `"Cenário e Operações.dc.html") ou marque \`// ${MARCADOR_EXCECAO}: <motivo>\` ` +
        `na linha anterior se for modo avançado (superadmin):\n${relatorio.join('\n')}`,
    ).toEqual([])
  }, TETO_DA_VARREDURA_MS)
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

  it('os 3 componentes do front legado ficam fora — mas por DÉBITO NOMEADO, não por cegueira', () => {
    const alvo = arquivosVisiveisAoTenant()
    const congelados = [
      path.join('components', 'training', 'modals', 'OperationCreateModal.tsx'),
      path.join('components', 'scenario', 'ScenarioEditor.tsx'),
      path.join('components', 'cameras', 'CameraFpsConfig.tsx'),
    ]
    for (const rel of congelados) {
      expect(alvo.some((f) => f.endsWith(rel)), `${rel} está congelado — deve sair do resultado`).toBe(false)
      // A diferença que importa: hoje eles saem porque ALGUÉM os escreveu na
      // lista, não porque a BFS não os enxerga. Tirar da lista é o conserto.
      expect(
        DEBITO_DE_OUTRA_FRENTE.includes(rel.split(path.sep).join('/')),
        `${rel} sairia do escopo em SILÊNCIO — tem de estar em DEBITO_DE_OUTRA_FRENTE`,
      ).toBe(true)
    }
  })
})

/**
 * Furo F (cético da rodada O2). O PR abriu o escopo para `src/pages/**` e
 * `src/modules/**` inteiros, mas NÃO semeou a BFS a partir deles — e o texto
 * que as rotas EPI pintam na tela mora, em boa parte, em `src/components/**`.
 * Medido com a própria régua: 38 arquivos de `components/` renderizados pelo
 * front legado ficavam fora, com 17 achados de jargão (`Threshold`, `IoU`,
 * `condition_satisfied`, `JSON`) — nas telas de operação e de cenário do
 * módulo EPI, que é o módulo da RVB. Nenhuma dessas rotas redireciona para o
 * front novo.
 */
describe('escopo O2/cético: a BFS é semeada TAMBÉM pelo front legado (furo F)', () => {
  it('inclui components/training/TrainingModeLayout.tsx — só alcançável via EpiOperationsPage', () => {
    const alvo = arquivosVisiveisAoTenant()
    expect(
      alvo.some((f) => f.endsWith(path.join('components', 'training', 'TrainingModeLayout.tsx'))),
      'TrainingModeLayout é o corpo de /epi/cameras/:id/operations — tem de estar no escopo',
    ).toBe(true)
  })

  it('nenhum componente alcançado pelo front legado escapa em silêncio', () => {
    // Todo arquivo de components/ que a BFS alcança ou está no resultado
    // (varrido) ou está NOMEADO no débito. Terceira via — sumir sem registro
    // — é o que este teste proíbe.
    const alvo = new Set(arquivosVisiveisAoTenant())
    const raiz = path.dirname(APP)
    const fora = [...arquivos(COMPONENTS)].filter(
      (f) => !alvo.has(f) && !ehDebitoDeOutraFrente(f),
    )
    // Sobram só os componentes que NINGUÉM renderiza (órfãos de verdade).
    for (const f of fora) {
      const rel = path.relative(raiz, f).split(path.sep).join('/')
      expect(
        acharJargao(rel, fs.readFileSync(f, 'utf-8')),
        `${rel} tem jargão e não está nem varrido nem no débito`,
      ).toEqual([])
    }
  })

  it('o débito congelado é a lista MEDIDA — 7 telas + 8 componentes', () => {
    expect(DEBITO_DE_OUTRA_FRENTE.length).toBe(15)
    expect(DEBITO_DE_OUTRA_FRENTE.filter((f) => f.startsWith('components/')).length).toBe(8)
  })
})

/**
 * Rodada O2 (issues #660/#661). Três furos MEDIDOS, cada um com a linha
 * REAL que estava servida como fixture — sem isso "a régua cobre agora"
 * seria afirmação, e afirmação foi o que deixou o CI verde sobre 5 telas.
 */
describe('escopo O2: o front legado inteiro (furo C) e copy passada como prop (furos D/E)', () => {
  it('varre `src/pages/**` e `src/modules/**` inteiros — não uma lista nominal', () => {
    const alvo = arquivosVisiveisAoTenant()
    // As 5 telas da issue #660 — nenhuma delas alcançável a partir de src/app.
    for (const rel of [
      path.join('pages', 'HomePage.tsx'),
      path.join('modules', 'quality', 'pages', 'QualityConfigPage.tsx'),
      path.join('modules', 'admin', 'components', 'IntegrationsPanel.tsx'),
      path.join('modules', 'admin', 'pages', 'AdminIntegrationsPage.tsx'),
      path.join('modules', 'admin', 'pages', 'AdminTestConsolePage.tsx'),
    ]) {
      expect(alvo.some((f) => f.endsWith(rel)), `${rel} fora do escopo da régua`).toBe(true)
    }
  })

  it('o débito congelado de outra frente fica FORA — e é nomeado, não silencioso', () => {
    const alvo = arquivosVisiveisAoTenant()
    expect(alvo.some((f) => f.endsWith(path.join('pages', 'monitoring', 'SiteMonitor.tsx')))).toBe(false)
    expect(DEBITO_DE_OUTRA_FRENTE.filter((f) => f.startsWith('pages/') || f.startsWith('modules/')).length).toBe(7)
  })

  it('furo D — copy em prop (`desc=`) acusa: a linha REAL de HomePage.tsx:123', () => {
    const antes = `<ModuleCard title="Qualidade Industrial"
      desc="Controle de qualidade com inspeção visual YOLO, CEP e relatórios de turno." />`
    expect(acharJargao('HomePage.tsx', antes).map((a) => a.termo)).toEqual(['YOLO'])
  })

  it('furo E — copy em chave de objeto acusa: a linha REAL de IntegrationsPanel.tsx:62', () => {
    const antes = `const CATALOGO = [{ type: 'vast_ai', title: 'Provedor GPU — Vast.ai',
      description: 'Treinamento de modelos YOLO em GPUs sob demanda.' }]`
    expect(acharJargao('IntegrationsPanel.ts', antes).map((a) => a.termo)).toEqual(['YOLO'])
  })

  it('sem falso positivo: chave de dado e label de campo comuns do mesmo catálogo', () => {
    const ok = `const F = [{ key: 'account_id', label: 'Access Key ID', placeholder: 'recognition-prod' },
      { type: 'generic_gpu', description: 'Provedor GPU alternativo (SSH/API personalizado).' }]`
    expect(acharJargao('integrationCatalog.ts', ok)).toEqual([])
  })

  it('prova por MUTAÇÃO no ARQUIVO REAL: reinstalar as 5 telas de antes acusa 5 termos', () => {
    const raiz = path.dirname(APP)
    const casos: Array<[string, string, string, string]> = [
      ['pages/HomePage.tsx', 'inspeção visual automática', 'inspeção visual YOLO', 'YOLO'],
      ['modules/quality/pages/QualityConfigPage.tsx', 'Confiança mínima do reconhecimento', 'Confiança Mínima YOLO', 'YOLO'],
      ['modules/admin/components/IntegrationsPanel.tsx', 'modelos de visão em GPUs', 'modelos YOLO em GPUs', 'YOLO'],
      ['modules/admin/pages/AdminIntegrationsPage.tsx', 'modelos de visão em GPUs', 'modelos YOLO em GPUs', 'YOLO'],
      ['modules/admin/pages/AdminTestConsolePage.tsx', 'Pré-treinado (modelo base do sistema)', 'Pré-treinado (YOLOv8n base)', 'YOLOv8n'],
    ]
    for (const [rel, hoje, antes, termo] of casos) {
      const arquivo = path.join(raiz, rel)
      const atual = fs.readFileSync(arquivo, 'utf-8')
      expect(atual.includes(hoje), `${rel}: texto de hoje não encontrado`).toBe(true)
      expect(acharJargao(rel, atual), `${rel} ainda tem jargão`).toEqual([])
      const mutado = atual.replace(hoje, antes)
      expect(acharJargao(rel, mutado).map((a) => a.termo), `${rel}: régua não pegou o texto antigo`).toContain(termo)
    }
  })

  it('prova por MUTAÇÃO: os 4 "threshold" de QualityConfigPage voltam a acusar', () => {
    const arquivo = path.join(path.dirname(APP), 'modules/quality/pages/QualityConfigPage.tsx')
    const atual = fs.readFileSync(arquivo, 'utf-8')
    const mutado = atual
      .replace(/Aprovação mínima V(\d) \(votação\)/g, 'Threshold V$1 (votação)')
      .replace('Reconhecimentos abaixo desta confiança são ignorados.', 'Detecções abaixo deste threshold são ignoradas.')
    expect(acharJargao('QualityConfigPage.tsx', mutado).filter((a) => /threshold/i.test(a.termo))).toHaveLength(4)
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

/**
 * ─── RODADA V1 (jargão final) ────────────────────────────────────────────
 *
 * As duas réguas anti-jargão estavam VERDES enquanto o bundle servido do DEV
 * mostrava, na cara do usuário:
 *
 *   `epi/Dashboard.tsx:530`  <span>GET /API/MODULES/EPI/STATS</span>
 *   `epi/Cameras.tsx:365`    "…não recebe classe por câmera (issue 519)."
 *   `epi/Cameras.tsx:366`    "…somente de leitura (requer cameras:configure)."
 *
 * POR QUE NÃO ERAM VISTAS — não é escopo, e não é string montada em runtime:
 * os três arquivos JÁ estavam no escopo, e os três textos são `JsxText`
 * literal, que a régua JÁ lia. O furo era o VOCABULÁRIO ESTRUTURAL, que
 * cobria 4 formas e não cobria estas 3:
 *
 *   1. `GET /API/MODULES/EPI/STATS` — rota de API. Não é `.py`, não tem `::`,
 *      não tem `_` líder, não tem `#`. Nenhuma das 4 formas descrevia "rota".
 *   2. `(issue 519)` — número de issue SEM `#`. A forma era `#\d{3,}`; o texto
 *      servido escrevia a palavra "issue" e o número, sem o "#".
 *   3. `(requer cameras:configure)` — chave de permissão. A forma `escopo ::`
 *      exige DOIS dois-pontos; `recurso:acao` tem um só.
 *
 * Cada um dos três ganhou uma forma nova em `ESTRUTURAIS`, e cada uma é
 * provada por MUTAÇÃO no ARQUIVO REAL abaixo: o texto de hoje passa, o texto
 * servido ontem reprova. Sem isso "a régua cobre agora" seria afirmação.
 */
describe('rodada V1: as 3 formas que deixavam jargão servido passar', () => {
  const casos: Array<[string, string, string, string]> = [
    [
      'app/epi/Dashboard.tsx',
      'Os indicadores deste módulo não responderam.',
      'GET /API/MODULES/EPI/STATS',
      'GET /API/MODULES/EPI/STATS',
    ],
    [
      'app/epi/Cameras.tsx',
      'o box edge ainda não recebe classe por câmera.',
      'o box edge ainda não recebe classe por câmera (issue 519).',
      'issue 519',
    ],
    [
      'app/epi/Cameras.tsx',
      'peça a quem administra o seu acesso a permissão de configurar câmeras',
      'requer cameras:configure',
      'cameras:configure',
    ],
    [
      'app/epi/Cameras.tsx',
      'A lista de câmeras não respondeu · {erro}',
      'GET /api/cameras · {erro}',
      'GET /api/cameras',
    ],
    [
      'app/epi/Eventos.tsx',
      'Ver eventos exige permissão para consultar eventos.',
      'Ver eventos exige a permissão <code>alerts:read</code>.',
      'alerts:read',
    ],
  ]

  it.each(casos)(
    'prova por MUTAÇÃO em %s: reinstalar o texto servido volta a acusar',
    (rel, hoje, servidoAntes, termo) => {
      const arquivo = path.join(SRC, rel)
      const atual = fs.readFileSync(arquivo, 'utf-8')
      expect(atual.includes(hoje), `${rel}: o texto de hoje não está no arquivo`).toBe(true)
      expect(acharJargao(rel, atual), `${rel} ainda tem jargão`).toEqual([])
      const mutado = atual.replace(hoje, servidoAntes)
      expect(mutado, `${rel}: a mutação não mudou nada`).not.toEqual(atual)
      expect(
        acharJargao(rel, mutado).map((a) => a.termo),
        `${rel}: a régua NÃO pegou o texto que estava servido`,
      ).toContain(termo)
    },
  )

  it('calibração das 3 formas novas: o que NÃO pode disparar', () => {
    // Cada linha é uma forma real de texto de UI que se PARECE com as novas
    // regras. Se qualquer uma disparar, a régua vira ruído e alguém a desliga.
    const codigo = [
      'export const X = () => (',
      '  <div>',
      '    <span>Cobertura 24/7 · 60 km/h · turno 05/09</span>',
      '    <span>Início às 10:30, fim às 18:45</span>',
      '    <span>Manual em https://logikos.com.br/ajuda</span>',
      '    <span>Nota: a contagem reinicia à meia-noite</span>',
      '    <span>(V1/V2/V3 = etapa da bancada)</span>',
      '    <span>Versão 2 do relatório, item 12</span>',
      '  </div>',
      ')',
      '',
    ].join('\n')
    expect(acharJargao('fixture.tsx', codigo)).toEqual([])
  })

  it('rota de API dispara nas duas formas medidas (verbo+caminho e base /api|/v1)', () => {
    const comVerbo = acharJargao('f.tsx', 'export const X = () => <p>GET /cameras · 500</p>\n')
    expect(comVerbo.map((a) => a.termo)).toEqual(['GET /cameras'])
    const semVerbo = acharJargao('f.tsx', 'export const X = () => <p>falhou em /v1/admin/users</p>\n')
    expect(semVerbo.map((a) => a.termo)).toEqual(['/v1/admin/users'])
  })

  it('chave de permissão dispara com um dois-pontos (a forma `::` exigia dois)', () => {
    const achados = acharJargao('f.tsx', 'export const X = () => <p>exige quality:write aqui</p>\n')
    expect(achados.map((a) => a.termo)).toEqual(['quality:write'])
    expect(achados[0].sugestao).toMatch(/em português/)
  })
})

/**
 * O congelamento de 41 pares só é honesto enquanto DESCREVE achado real. Um
 * par que não casa mais é lixo que fica no caminho de quem lê a lista para
 * saber o que falta — e, pior, dá a impressão de dívida maior do que a que
 * existe. Este teste obriga quem consertar a tela a apagar a linha daqui.
 */
describe('débito estrutural V1: congelado por par, e sem cemitério', () => {
  it('todo par congelado ainda casa com um achado de hoje', () => {
    const vivos = new Set<string>()
    for (const arquivo of arquivosVisiveisAoTenant()) {
      const rel = relDoSrc(arquivo)
      for (const a of acharJargao(rel, fs.readFileSync(arquivo, 'utf-8'))) vivos.add(`${rel}|${a.termo}`)
    }
    const mortos = DEBITO_ESTRUTURAL_V1.filter((par) => !vivos.has(par))
    expect(
      mortos,
      `pares congelados que não descrevem mais achado nenhum — apague estas ` +
        `linhas de DEBITO_ESTRUTURAL_V1:\n${mortos.join('\n')}`,
    ).toEqual([])
  }, TETO_DA_VARREDURA_MS)

  it('a lista é a MEDIDA de hoje — 41 pares em 22 telas', () => {
    expect(DEBITO_ESTRUTURAL_V1.length).toBe(41)
    expect(new Set(DEBITO_ESTRUTURAL_V1.map((p) => p.split('|')[0])).size).toBe(22)
    // Nenhuma das 3 telas do mandato deste PR pode estar congelada.
    expect(
      DEBITO_ESTRUTURAL_V1.filter((p) => /epi\/(Dashboard|Cameras|Eventos)\.tsx/.test(p)),
    ).toEqual([])
  })
})

/**
 * Issue #766 — o teto de 5 s estourava porque a árvore era varrida NOVE vezes
 * (uma por teste que chama `arquivosVisiveisAoTenant`). Guard por CONTAGEM, não
 * por relógio: cronômetro num teste é exatamente o que produziu a #766.
 *
 * PROVA POR MUTAÇÃO: apague o `if (memoAlvo) return memoAlvo` e este teste fica
 * vermelho na hora (o contador vira 10+, não 1).
 */
describe('teto de tempo (#766): a árvore é varrida UMA vez por execução', () => {
  it('duas chamadas seguidas não varrem duas vezes', () => {
    const a = arquivosVisiveisAoTenant()
    const b = arquivosVisiveisAoTenant()
    expect(b).toBe(a)
    expect(
      contadorDeVarreduras.valor,
      'a BFS rodou mais de uma vez nesta execução — a memoização caiu',
    ).toBe(1)
  })
})
