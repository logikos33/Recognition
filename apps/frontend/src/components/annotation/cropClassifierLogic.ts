/**
 * cropClassifierLogic — mapeamento puro estado→classe da aba "Classificar"
 * (4 tipos de EPI, estado exclusivo dentro do tipo, multilabel entre tipos).
 * Zero I/O, zero React — testável isolado (ver cropClassifierLogic.test.ts).
 *
 * Taxonomia e nomes candidatos vieram da especificação da feature — nomes de
 * classe são inconsistentes no catálogo real, por isso o match é
 * case-insensitive/trim (resolveClassId) e cada estado aceita uma LISTA de
 * candidatos (ex.: "Óculos" ou "óculos").
 */

export type StateKind = 'presente' | 'ausente' | 'nao_visivel' | 'uso_incorreto'

export interface EpiStateOption {
  key: string
  label: string
  kind: StateKind
  /** Nomes candidatos para resolver a classe real via GET /modules/epi/classes
   * (case-insensitive, trim, primeiro que bater vence). Vazio = este estado
   * NUNCA gera anotação (ex.: "não visível"). */
  classNameCandidates: string[]
}

export interface EpiTypeDef {
  key: string
  label: string
  states: EpiStateOption[]
}

export const EPI_TYPES: EpiTypeDef[] = [
  {
    key: 'auditiva',
    label: 'Proteção auditiva',
    states: [
      { key: 'presente', label: 'Presente', kind: 'presente', classNameCandidates: ['Protetor auditivo'] },
      { key: 'ausente', label: 'Ausente', kind: 'ausente', classNameCandidates: ['Sem protetor de ouvido'] },
      { key: 'nao_visivel', label: 'Não visível', kind: 'nao_visivel', classNameCandidates: [] },
    ],
  },
  {
    key: 'mascara',
    label: 'Máscara',
    states: [
      { key: 'presente', label: 'Presente', kind: 'presente', classNameCandidates: ['mascara'] },
      { key: 'ausente', label: 'Ausente', kind: 'ausente', classNameCandidates: ['Sem mascara'] },
      { key: 'uso_incorreto', label: 'Uso incorreto', kind: 'uso_incorreto', classNameCandidates: ['Uso incorreto de mascara', 'Uso incorreto'] },
      { key: 'nao_visivel', label: 'Não visível', kind: 'nao_visivel', classNameCandidates: [] },
    ],
  },
  {
    key: 'botas',
    label: 'Botas',
    states: [
      { key: 'presente', label: 'Presente', kind: 'presente', classNameCandidates: ['Botas'] },
      { key: 'ausente', label: 'Ausente', kind: 'ausente', classNameCandidates: ['Sem botas'] },
      { key: 'nao_visivel', label: 'Não visível', kind: 'nao_visivel', classNameCandidates: [] },
    ],
  },
  {
    // Entrou no núcleo depois da reunião com o Paulo (18/08): duas áreas exigem
    // luva. O catálogo já tinha `gloves`/`no_gloves` com 125 e 164 usos — a
    // classe existia, faltava a TELA.
    key: 'luvas',
    label: 'Luvas',
    states: [
      { key: 'presente', label: 'Presente', kind: 'presente', classNameCandidates: ['gloves', 'Luvas'] },
      { key: 'ausente', label: 'Ausente', kind: 'ausente', classNameCandidates: ['no_gloves', 'Sem Luvas'] },
      { key: 'nao_visivel', label: 'Não visível', kind: 'nao_visivel', classNameCandidates: [] },
    ],
  },
  {
    key: 'oculos',
    label: 'Óculos',
    states: [
      // O catálogo do tenant nomeia em INGLÊS (`glasses`/`no_glasses`, 188 e 75
      // usos). Os nomes em português nunca resolveram — todo veredito de óculos
      // caía no balde `missingCrops` com o aviso "crie a classe", exatamente
      // como aconteceu com "Uso incorreto de mascara". 3ª ocorrência do #445.
      { key: 'presente', label: 'Presente', kind: 'presente', classNameCandidates: ['glasses', 'Óculos', 'óculos'] },
      { key: 'ausente', label: 'Ausente', kind: 'ausente', classNameCandidates: ['no_glasses', 'Sem óculos'] },
      { key: 'nao_visivel', label: 'Não visível', kind: 'nao_visivel', classNameCandidates: [] },
    ],
  },
]

/**
 * Veredito de um recorte: typeKey → stateKey escolhido. `undefined`/`null` =
 * tipo ainda não decidido (não bloqueia Aprovar — nem todo tipo precisa
 * estar visível na cena). Exclusividade dentro do tipo é ESTRUTURAL: só
 * cabe uma chave por tipo neste objeto — setVerdictState troca, nunca
 * acumula.
 */
export type Verdict = Record<string, string | null | undefined>

/** Aplica um estado ao tipo — substitui o que já estava lá (exclusividade
 * dentro do tipo) sem tocar nos demais tipos (multilabel entre tipos). */
export function setVerdictState(verdict: Verdict, typeKey: string, stateKey: string): Verdict {
  return { ...verdict, [typeKey]: stateKey }
}

export interface RuntimeClass {
  classId: number
  name: string
}

function normName(s: string): string {
  return s.trim().toLowerCase()
}

/** Resolve o primeiro candidato que bater (case-insensitive/trim) contra o
 * catálogo runtime. `null` = nenhuma classe candidata existe ainda no
 * catálogo do tenant ("classe a criar"). Lista vazia (ex.: "não visível")
 * também devolve `null`, mas esse caso nunca chega a virar "missing" —
 * quem chama filtra por `classNameCandidates.length > 0` antes. */
export function resolveClassId(candidates: string[], classes: RuntimeClass[]): number | null {
  return resolveClass(candidates, classes)?.classId ?? null
}

/** Como resolveClassId, mas devolve a classe inteira — o nome precisa viajar
 * junto no payload (ver AnnotationBoxPayload). */
export function resolveClass(
  candidates: string[],
  classes: RuntimeClass[],
): RuntimeClass | null {
  for (const candidate of candidates) {
    const hit = classes.find(c => normName(c.name) === normName(candidate))
    if (hit) return hit
  }
  return null
}

/** Distância de edição (Levenshtein). Duas linhas de estado, sem matriz
 * completa — o catálogo tem poucas classes e os nomes são curtos. */
function distanciaEdicao(a: string, b: string): number {
  if (a === b) return 0
  if (a.length === 0) return b.length
  if (b.length === 0) return a.length

  let anterior = Array.from({ length: b.length + 1 }, (_, i) => i)
  for (let i = 1; i <= a.length; i++) {
    const atual = [i]
    for (let j = 1; j <= b.length; j++) {
      const custo = a[i - 1] === b[j - 1] ? 0 : 1
      atual[j] = Math.min(atual[j - 1] + 1, anterior[j] + 1, anterior[j - 1] + custo)
    }
    anterior = atual
  }
  return anterior[b.length]
}

/** Como normName, mais remoção de acento: "Oculos" e "Óculos" são o mesmo
 * nome digitado por duas pessoas diferentes, e é exatamente esse tipo de
 * divergência que a sugestão precisa enxergar. */
function normParaComparar(s: string): string {
  return normName(s).normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

/** Nome real do catálogo mais parecido com algum dos candidatos.
 *
 * Existe porque a mensagem antiga AFIRMAVA um diagnóstico ("a classe não
 * existe") quando o que a tela sabia era outro: "eu não consegui resolver
 * este nome". No caso real (`Uso incorreto` × `Uso incorreto de mascara`) a
 * classe EXISTIA, e quem seguisse a instrução criaria uma duplicata.
 *
 * Aceita como sugestão em dois casos:
 *
 *  - um nome é PREFIXO do outro — o caso real: o catálogo tem uma versão mais
 *    específica do que a tela pediu ("Uso incorreto" → "Uso incorreto de
 *    mascara"), mesma polaridade;
 *  - a distância de edição é ≤ 2 — que é o tamanho de um acento perdido ou
 *    de um erro de digitação, e nada além disso.
 *
 * ⚠️ As duas restrições existem pelo MESMO motivo, e ele é o risco central
 * desta função: nesta taxonomia o estado oposto costuma ser o mesmo nome com
 * um prefixo de negação — "Botas" × "Sem botas", "Capacete" × "Sem capacete".
 * Sugerir um desses faria o anotador rotular o INVERSO do que marcou, o que é
 * pior do que não sugerir nada.
 *
 *  - por isso prefixo, e não "contém em qualquer posição" (pega "Sem botas");
 *  - por isso teto ABSOLUTO de 2, e não proporcional ao tamanho: um teto de
 *    um terço deixaria "Capacete" → "Sem capacete" passar (distância 4 em 12
 *    caracteres), enquanto "Botas" → "Sem botas" era barrado só por acaso, por
 *    a palavra ser curta.
 *
 * Os dois casos estão fixados em teste — o segundo foi encontrado por um teste
 * que já existia, não por revisão. */
/** Teto absoluto de distância de edição. Ver o ⚠️ em sugerirClasseProxima:
 * proporcional ao tamanho deixa a negação passar em nome longo. */
const DISTANCIA_MAXIMA = 2

export function sugerirClasseProxima(
  candidates: string[],
  classes: RuntimeClass[],
): string | null {
  let melhorNome: string | null = null
  let melhorDistancia = Infinity

  for (const candidato of candidates) {
    const c = normParaComparar(candidato)
    if (!c) continue
    for (const classe of classes) {
      const k = normParaComparar(classe.name)
      if (!k) continue

      const ehPrefixo = k.startsWith(c) || c.startsWith(k)
      const d = ehPrefixo ? 0 : distanciaEdicao(c, k)
      if (d <= DISTANCIA_MAXIMA && d < melhorDistancia) {
        melhorDistancia = d
        melhorNome = classe.name
      }
    }
  }
  return melhorNome
}

/** Aviso de classe não resolvida — diz o que a tela REALMENTE sabe.
 *
 * A versão anterior era `"N estado(s) sem classe no catálogo ainda — crie a
 * classe e volte depois."`: afirmava que a classe não existia, sem ter como
 * saber disso, e mandava criar o que já podia estar lá. */
export function mensagemClassesNaoResolvidas(
  missing: MissingClass[],
  classes: RuntimeClass[],
): string {
  if (missing.length === 0) return ''

  const catalogo = `${classes.length} classe(s) no catálogo carregado`
  const detalhes = missing.map(m => {
    const procurados = m.candidates.map(c => `"${c}"`).join(' ou ')
    return m.suggestion != null
      ? `${m.stateLabel}: procurei por ${procurados} — talvez seja "${m.suggestion}"?`
      : `${m.stateLabel}: procurei por ${procurados} — nada parecido`
  })

  return `${missing.length} estado(s) sem classe resolvida (${catalogo}). ${detalhes.join(' · ')}`
}

export function findState(typeKey: string, stateKey: string): EpiStateOption | null {
  const type = EPI_TYPES.find(t => t.key === typeKey)
  return type?.states.find(s => s.key === stateKey) ?? null
}

/** Shape aceito por POST /training/frames/{id}/annotations.
 *
 * `class_name` e `module_code` NÃO são decorativos: AnnotationService.
 * _validate_class rejeita o batch inteiro com 400 se qualquer um dos dois
 * vier vazio. Omiti-los fazia todo "Aprovar" da aba Classificar falhar de
 * forma permanente — a aprovação ficava pendente para sempre e nenhum
 * retry resolvia (o erro nunca foi transitório). Mesmo shape que o estúdio
 * já mandava por boxToPayload (studioTypes.ts:94).
 */
export interface AnnotationBoxPayload {
  class_id: number
  class_name: string
  module_code: string
  x_center: number
  y_center: number
  width: number
  height: number
}

export interface MissingClass {
  typeKey: string
  typeLabel: string
  stateKey: string
  stateLabel: string
  candidates: string[]
  /** Nome REAL do catálogo mais parecido com algum dos candidatos, quando há
   * um parecido o bastante. `null` = nenhum, e aí "crie a classe" é mesmo o
   * conselho certo. Ver sugerirClasseProxima. */
  suggestion: string | null
}

export interface ApprovalResult {
  payload: AnnotationBoxPayload[]
  missing: MissingClass[]
}

/** bbox topo-esquerda+wh (convenção SearchFinding['bbox'] / cropStyle) →
 * centro+wh (convenção Box/boxToPayload do estúdio) — mesma anotação, forma
 * diferente por endpoint histórico. */
export function bboxToCenterForm(bbox: readonly [number, number, number, number]) {
  const [x, y, w, h] = bbox
  return { x_center: x + w / 2, y_center: y + h / 2, width: w, height: h }
}

/**
 * Monta o payload de "Aprovar": uma caixa por estado ATIVO (presente/
 * ausente/uso_incorreto) que resolveu classe real, TODAS com o mesmo bbox
 * do recorte. "Não visível" nunca gera caixa. Estado escolhido cuja classe
 * ainda não existe no catálogo entra em `missing` (badge "classe a criar")
 * sem travar os demais tipos do mesmo recorte.
 *
 * `tipos` = os tipos VISÍVEIS na tela (`tiposVisiveis`). Default = todos.
 */
export function buildApprovalPayload(
  verdict: Verdict,
  bbox: readonly [number, number, number, number],
  classes: RuntimeClass[],
  moduleCode = 'epi',
  tipos: readonly EpiTypeDef[] = EPI_TYPES,
): ApprovalResult {
  const { x_center, y_center, width, height } = bboxToCenterForm(bbox)
  const payload: AnnotationBoxPayload[] = []
  const missing: MissingClass[] = []

  // ⛔ Só os tipos NA TELA viram anotação. O veredito pode carregar chave de
  // tipo escondido (rascunho restaurado de uma sessão com outro filtro,
  // proposta pré-selecionada antes de o filtro estreitar) — e anotação que o
  // humano não pôde ver é dado errado em silêncio.
  for (const type of tipos) {
    const stateKey = verdict[type.key]
    if (!stateKey) continue
    const state = type.states.find(s => s.key === stateKey)
    if (!state || state.kind === 'nao_visivel') continue
    if (state.classNameCandidates.length === 0) continue
    const cls = resolveClass(state.classNameCandidates, classes)
    if (cls != null) {
      payload.push({
        class_id: cls.classId,
        class_name: cls.name,
        module_code: moduleCode,
        x_center, y_center, width, height,
      })
    } else {
      missing.push({
        typeKey: type.key,
        typeLabel: type.label,
        stateKey: state.key,
        stateLabel: state.label,
        candidates: state.classNameCandidates,
        suggestion: sugerirClasseProxima(state.classNameCandidates, classes),
      })
    }
  }
  return { payload, missing }
}

/**
 * Sugestão de pré-anotação (bloco 3, soft): SÓ estados de PRESENÇA podem
 * ser sugeridos — nunca ausência (regra estrutural: o loop só olha
 * kind==='presente'). `proposalClassIds` = class_id das caixas com
 * source==='ai' do frame corrente (RawAnnotation.source, studioTypes.ts).
 */
export function suggestedPresenceStates(
  proposalClassIds: number[],
  classes: RuntimeClass[],
): Set<string> {
  const suggested = new Set<string>()
  for (const type of EPI_TYPES) {
    for (const state of type.states) {
      if (state.kind !== 'presente') continue
      const classId = resolveClassId(state.classNameCandidates, classes)
      if (classId != null && proposalClassIds.includes(classId)) {
        suggested.add(`${type.key}:${state.key}`)
      }
    }
  }
  return suggested
}

/**
 * Confiança visível no crop: `tipo:estado` sugerido → MAIOR confiança
 * (0..1) entre as propostas daquela classe; `null` quando nenhuma trouxe
 * confiança (DINO legado). Mesma regra de `suggestedPresenceStates` (só
 * PRESENÇA, nunca ausência) — as chaves são idênticas, aqui só se anexa
 * o % (ele prevê a aceitação: v9 0,25–0,35 → 62%, 0,65+ → 95%).
 */
export function confiancaDasPropostas(
  proposals: ReadonlyArray<{ class_id: number; confidence?: number | null }>,
  classes: RuntimeClass[],
): Map<string, number | null> {
  const out = new Map<string, number | null>()
  for (const type of EPI_TYPES) {
    for (const state of type.states) {
      if (state.kind !== 'presente') continue
      const classId = resolveClassId(state.classNameCandidates, classes)
      if (classId == null) continue
      const daClasse = proposals.filter(p => p.class_id === classId)
      if (daClasse.length === 0) continue
      const confs = daClasse.map(p => p.confidence).filter((c): c is number => typeof c === 'number')
      out.set(`${type.key}:${state.key}`, confs.length ? Math.max(...confs) : null)
    }
  }
  return out
}

export interface KeyBinding {
  key: string
  typeKey: string
  stateKey: string
}

/** Mapa de teclas por tipo — dígitos/letras distintos por tipo, sem
 * modificador (fluxo rápido). Ações globais (Aprovar/Pular/Reprovar/Não
 * sei/Desfazer) vivem em GLOBAL_KEYS, com Shift onde precisa desambiguar
 * de uma tecla de estado já usada aqui (ver nota em GLOBAL_KEYS). */
export const KEY_BINDINGS: KeyBinding[] = [
  { key: '1', typeKey: 'auditiva', stateKey: 'presente' },
  { key: '2', typeKey: 'auditiva', stateKey: 'ausente' },
  { key: '3', typeKey: 'auditiva', stateKey: 'nao_visivel' },
  { key: 'q', typeKey: 'mascara', stateKey: 'presente' },
  { key: 'w', typeKey: 'mascara', stateKey: 'ausente' },
  { key: 'e', typeKey: 'mascara', stateKey: 'uso_incorreto' },
  { key: 'r', typeKey: 'mascara', stateKey: 'nao_visivel' },
  { key: 'a', typeKey: 'botas', stateKey: 'presente' },
  { key: 's', typeKey: 'botas', stateKey: 'ausente' },
  { key: 'd', typeKey: 'botas', stateKey: 'nao_visivel' },
  { key: 'f', typeKey: 'luvas', stateKey: 'presente' },
  { key: 'g', typeKey: 'luvas', stateKey: 'ausente' },
  { key: 'v', typeKey: 'luvas', stateKey: 'nao_visivel' },
  { key: 'z', typeKey: 'oculos', stateKey: 'presente' },
  { key: 'x', typeKey: 'oculos', stateKey: 'ausente' },
  { key: 'c', typeKey: 'oculos', stateKey: 'nao_visivel' },
]

export function stateForKey(key: string): KeyBinding | null {
  const k = key.length === 1 ? key.toLowerCase() : key
  return KEY_BINDINGS.find(b => b.key === k) ?? null
}

/**
 * Ações globais (não são estado de tipo nenhum). 's' de "Pular" colide com
 * 's' = botas→Ausente em KEY_BINDINGS — resolvido com Shift (S maiúsculo)
 * só nesta ação; as demais (u, n) não colidem com nenhuma tecla de tipo e
 * ficam minúsculas, junto de Enter/Backspace tratados à parte no handler.
 */
export const GLOBAL_KEYS = {
  undo: 'u',
  skip: 'S', // Shift+S — 's' minúsculo já é botas→Ausente
  naoSei: 'n',
  reprovar: 'R', // Shift+R — 'r' minúsculo já é máscara→Não visível
} as const


/**
 * Auto-avanço: a tecla de classe sozinha fecha o recorte e passa ao próximo.
 *
 * Só vale quando há uma CLASSE EM FOCO (deep-link da matriz de cobertura) e a
 * tecla pertence ao tipo dono dela. Fora disso o recorte pode precisar de
 * veredito para vários tipos de EPI, e avançar no primeiro perderia os outros —
 * o ganho de velocidade viraria perda de dado.
 *
 * Sem foco, nada muda: continua `tecla` + `Enter`, como sempre foi.
 */
export function deveAutoAvancar(
  binding: KeyBinding,
  emphasizedTypeKey: string | null,
  ligado: boolean,
): boolean {
  return ligado && emphasizedTypeKey != null && binding.typeKey === emphasizedTypeKey
}

/** Uma lacuna da matriz de cobertura (`GET /api/training/coverage-matrix` → `gaps`). */
export interface LacunaCobertura {
  class_id: number
  class_name: string
  camera_id: string
  score: number
  reason: string
}

/**
 * Ordena a fila pela CARÊNCIA: recorte de câmera que falta primeiro.
 *
 * Por que por câmera e não por classe: antes de anotar não se sabe a classe do
 * recorte — é justamente o que o humano vai dizer. A câmera, sim, é conhecida,
 * e a matriz de cobertura já diz quais câmeras têm lacuna para quais classes.
 * Somar os `score` das lacunas de cada câmera dá uma prioridade honesta com o
 * que se sabe no momento da fila.
 *
 * Ordenação ESTÁVEL: empate mantém a ordem que o servidor devolveu (mais
 * recente primeiro). Sem isso, a fila embaralharia a cada recarga e o humano
 * perderia a noção de onde parou.
 *
 * Nada é removido — só reordenado. Recorte de classe farta continua na fila,
 * no fim.
 */
export function ordenarPorCarencia<T extends { camera_id: string | null }>(
  frames: T[],
  gaps: readonly LacunaCobertura[],
): T[] {
  if (gaps.length === 0) return frames

  const carenciaPorCamera = new Map<string, number>()
  for (const g of gaps) {
    carenciaPorCamera.set(g.camera_id, (carenciaPorCamera.get(g.camera_id) ?? 0) + g.score)
  }

  return frames
    .map((frame, ordemOriginal) => ({
      frame,
      ordemOriginal,
      carencia: frame.camera_id ? (carenciaPorCamera.get(frame.camera_id) ?? 0) : 0,
    }))
    .sort((a, b) => b.carencia - a.carencia || a.ordemOriginal - b.ordemOriginal)
    .map(x => x.frame)
}

/**
 * Todos os nomes candidatos de classe dos tipos escolhidos (presença E
 * ausência E uso incorreto — uma proposta de "Sem mascara" é do tipo máscara).
 * Vazio = sem filtro. É o que vai no `?proposal_classes=` da fila e o que
 * pesa em `lacunasDosTipos`.
 */
export function nomesDeClasseDosTipos(tipos: ReadonlySet<string>): string[] {
  if (tipos.size === 0) return []
  return Array.from(new Set(
    EPI_TYPES.filter(t => tipos.has(t.key))
      .flatMap(t => t.states)
      .flatMap(st => st.classNameCandidates),
  ))
}

/**
 * Lacunas SÓ das classes dos tipos escolhidos — a priorização por carência
 * passa a responder ao filtro da tela.
 *
 * ⚠️ Casa por NOME (sem acento/caixa — normParaComparar), não por `class_id`:
 * os dois catálogos têm ids que COLIDEM (`class_id` cru 4 é `gloves` no
 * catálogo global e uma classe custom qualquer no do tenant, task-077) e a
 * matriz emite o id CRU de yolo_classes. Por id, "Luvas" priorizaria a câmera
 * carente de "Protetor auditivo" em silêncio. Nome não colide.
 *
 * Conjunto vazio = sem filtro. ⛔ Nada sai da fila: gap fora do filtro só
 * deixa de PESAR na ordenação.
 */
export function lacunasDosTipos(
  gaps: readonly LacunaCobertura[],
  tipos: ReadonlySet<string>,
): readonly LacunaCobertura[] {
  if (tipos.size === 0) return gaps
  const nomes = new Set(nomesDeClasseDosTipos(tipos).map(normParaComparar))
  return gaps.filter(g => nomes.has(normParaComparar(g.class_name)))
}

/**
 * Primeira posição da fila que pode ser reordenada, sem confiar no relógio do
 * React.
 *
 * O corte óbvio seria `index + 1`, e ele está certo — quando `index` está em
 * dia. Só que quem reordena é o updater do `setQueue` (roda quando o fetch do
 * lote resolve) e o `index` só chega lá por um ref atribuído no corpo do
 * render. `approve()` é async e chama `advance()` DEPOIS do await: duas
 * aprovações resolvendo na mesma drenagem de microtasks viram um render só, e
 * o ref atrasa 2 enquanto o `+ 1` absorve 1. Resultado: uma posição já
 * anotada cairia dentro da faixa reordenável — o defeito de volta, por outra
 * porta.
 *
 * `jaVistos` é o único dos três refs que NÃO pode atrasar: `advance()` o muta
 * de forma síncrona, antes de qualquer `setState`. Então o corte sai do maior
 * entre o que o índice diz e o que o conjunto de vistos PROVA, mais uma
 * posição para o recorte que está na tela agora.
 */
export function corteSeguro<T extends { id: string }>(
  fila: readonly T[],
  index: number,
  jaVistos: ReadonlySet<string>,
): number {
  let ultimaVista = -1
  for (let i = 0; i < fila.length; i++) {
    if (jaVistos.has(fila[i].id)) ultimaVista = i
  }
  return Math.max(index, ultimaVista + 1) + 1
}

/**
 * Reordena por carência **só a parte da fila que o anotador ainda não
 * alcançou** — o prefixo já visto e o recorte na tela ficam onde estão.
 *
 * 🔴 A razão é o defeito que isto conserta. `index` é um ponteiro POSICIONAL
 * dentro da fila. Reordenar a fila inteira (prefixo incluído) faz um lote novo
 * de carência alta entrar ANTES do cursor, o que empurra para trás o que já
 * teve veredito — e o anotador recebe de volta recorte já excluído/marcado
 * dúvida. Medido no acervo real do RVB: 1045 reapresentações em 1500
 * vereditos, a 1ª no veredito 192; com a cauda congelada, zero.
 *
 * `corte` = primeira posição reordenável (use `index + 1`: nem o que passou,
 * nem o recorte que está na tela agora, podem se mover).
 */
export function reordenarCauda<T extends { camera_id: string | null }>(
  fila: readonly T[],
  corte: number,
  gaps: readonly LacunaCobertura[],
): T[] {
  const limite = Math.max(0, Math.min(corte, fila.length))
  return [...fila.slice(0, limite), ...ordenarPorCarencia(fila.slice(limite), gaps)]
}

/**
 * Tipos das 5 classes prioritárias da campanha: mascara · Sem mascara ·
 * Uso incorreto de mascara · Protetor auditivo · Sem protetor de ouvido.
 * Preset de um clique do filtro por classe (ver `tiposVisiveis`).
 */
export const TIPOS_PRIORITARIOS = ['mascara', 'auditiva', 'luvas', 'oculos'] as const

/**
 * Filtro por classe: os tipos escolhidos ficam na TELA (e só eles viram
 * anotação — ver `buildApprovalPayload`); a FILA passa a trazer só recorte
 * com proposta pendente de classe desses tipos (`?proposal_classes=`).
 *
 * Generaliza o antigo "modo estreito" (booleano que só sabia
 * `TIPOS_PRIORITARIOS`). ⛔ Não apaga nada do banco: as demais classes seguem
 * existindo, anotáveis desmarcando o filtro. Conjunto VAZIO = TODOS os tipos
 * e fila sem filtro de classe — quem nunca escolheu nada vê a tela inteira,
 * ⛔ nunca uma tela vazia.
 */
export function tiposVisiveis(selecionados: ReadonlySet<string>): EpiTypeDef[] {
  if (selecionados.size === 0) return EPI_TYPES
  return EPI_TYPES.filter(t => selecionados.has(t.key))
}

/** Quantos recortes restando disparam a busca do próximo lote. */
export const GATILHO_PREFETCH = 10

/**
 * Junta o lote novo à fila, sem repetir e SEM reordenar o que já está na tela.
 *
 * Duas garantias que o anotador sente:
 * - **sem duplicata**: id que já está na fila (ou já teve veredito na sessão)
 *   não volta — ver um recorte duas vezes destrói a confiança na contagem
 * - **ordem preservada**: o lote novo entra NO FIM. A carência continua
 *   mandando dentro de cada lote, mas ⛔ nada reordena o que o humano já está
 *   olhando — a fila mudar sob os olhos é pior que fila mal ordenada.
 */
export function anexarLote<T extends { id: string }>(
  fila: readonly T[],
  lote: readonly T[],
  jaVistos: ReadonlySet<string> = new Set(),
): T[] {
  const conhecidos = new Set([...fila.map(f => f.id), ...jaVistos])
  return [...fila, ...lote.filter(f => !conhecidos.has(f.id))]
}

/** Hora de buscar mais? Só se sobrou pouco, não está buscando e o servidor ainda tem. */
export function devePrefetch(
  restantes: number,
  buscando: boolean,
  esgotado: boolean,
  gatilho: number = GATILHO_PREFETCH,
): boolean {
  return !buscando && !esgotado && restantes < gatilho
}

/**
 * Veredito inicial a partir das propostas do modelo — fase A do propor-confirmar.
 *
 * ⛔ **Ausência NUNCA é proposta.** `suggestedPresenceStates` só devolve estados
 * `kind === 'presente'`, e esta função só consome o que ela devolve. A razão é
 * dura: das 1005 propostas de ausência feitas antes, **100% foram rejeitadas** —
 * e ausência é o gatilho do alerta. Um falso "sem máscara" pré-selecionado vira
 * alerta errado na cara do cliente; um falso "com máscara" vira só um veredito
 * corrigido com uma tecla.
 *
 * O humano confirma com Enter (barato) ou corrige com a tecla da classe (barato).
 * Em nenhum caminho a proposta vira anotação sem alguém olhar — o veredito
 * gravado é sempre `humana`.
 */
export function vereditoInicialDaProposta(
  sugeridos: ReadonlySet<string>,
  tipos: readonly EpiTypeDef[] = EPI_TYPES,
): Verdict {
  const inicial: Verdict = {}
  for (const chave of sugeridos) {
    const [typeKey, stateKey] = chave.split(':')
    // ⛔ Tipo escondido pelo filtro não é pré-selecionado: o humano não o vê,
    // logo não pode confirmar nem corrigir — e Enter o gravaria às cegas.
    if (typeKey && stateKey && tipos.some(t => t.key === typeKey)) inicial[typeKey] = stateKey
  }
  return inicial
}

/** Um veredito humano confrontado com o que o modelo propôs. */
export interface AceitacaoProposta {
  classe: string
  aceita: boolean
}

/**
 * Compara veredito final × proposta, por tipo. É a medição que decide a fase C.
 *
 * Só conta tipos em que o modelo PROPÔS algo — tipo sem proposta não é acerto
 * nem erro dele, e incluí-lo inflaria a taxa artificialmente. Idem tipo fora
 * de `tipos` (escondido pelo filtro): ninguém olhou, não entra na conta.
 */
export function medirAceitacao(
  proposta: ReadonlySet<string>,
  final: Verdict,
  tipos: readonly EpiTypeDef[] = EPI_TYPES,
): AceitacaoProposta[] {
  const saida: AceitacaoProposta[] = []
  for (const chave of proposta) {
    const [typeKey, stateKey] = chave.split(':')
    if (!typeKey || !stateKey) continue
    // Tipo fora da tela não foi julgado — não é aceite nem recusa.
    if (!tipos.some(t => t.key === typeKey)) continue
    saida.push({ classe: `${typeKey}:${stateKey}`, aceita: final[typeKey] === stateKey })
  }
  return saida
}

// ─── Intercalação normais/propostas (D5) ────────────────────────────────────
// Bloco ADITIVO: nada acima muda. `reordenarCauda` segue intacta; quem quer
// cadência chama `reordenarCaudaIntercalada`.

/**
 * Cadência da intercalação (D5): a cada `normais` recortes SEM proposta, um
 * bloco de `propostas` recortes COM proposta da IA — nesses, a classe proposta
 * já vem pré-selecionada (vereditoInicialDaProposta) e Enter confirma.
 * `null` = desligada: a fila fica só por carência (ordem do servidor +
 * reordenação estável da cauda) — desligar não reseta nada.
 *
 * ⛔ DESLIGADA por padrão (opt-in, decisão do dono): quem está anotando agora
 * não vê a fila mudar sem ter escolhido.
 */
export interface Cadencia {
  normais: number
  propostas: number
}

export const CADENCIA_PADRAO: Cadencia = { normais: 5, propostas: 3 }

/**
 * Cadência saneada: cada lado vira inteiro ≥ 0 (NaN/ausente/negativo/não-
 * número → 0) e `null` quando algum lado é 0 — "0 normais" ou "0 propostas"
 * não é intercalar. TUDO que entra em `intercalar` passa por aqui: a cadência
 * vem de localStorage e do <select>, e `Math.floor(undefined)` = NaN passava
 * pelo guard `n === 0 && m === 0` e travava o while (loop infinito).
 */
export function cadenciaValida(c: unknown): Cadencia | null {
  if (!c || typeof c !== 'object') return null
  const inteiro = (v: unknown) =>
    typeof v === 'number' && Number.isFinite(v) ? Math.max(0, Math.floor(v)) : 0
  const { normais, propostas } = c as Record<string, unknown>
  const n = inteiro(normais)
  const m = inteiro(propostas)
  return n > 0 && m > 0 ? { normais: n, propostas: m } : null
}

/** Item da fila como GET /training/images o entrega (FrameRepository.
 * list_images_filtered): contagem de propostas PENDENTES e os nomes de classe
 * delas (lower/trim, mesmo predicado do filtro ?pending_review). */
export interface ItemComProposta {
  pending_proposals_count?: number | null
  pending_proposal_classes?: readonly string[] | null
}

/** Nomes (normalizados como o filtro por classe — normParaComparar) das
 * classes de PRESENÇA dos tipos na tela. É exatamente o que
 * `suggestedPresenceStates`/`vereditoInicialDaProposta` podem pré-selecionar. */
export function nomesDePresencaDosTipos(tipos: readonly EpiTypeDef[]): Set<string> {
  return new Set(
    tipos.flatMap(t => t.states)
      .filter(st => st.kind === 'presente')
      .flatMap(st => st.classNameCandidates)
      .map(normParaComparar),
  )
}

/**
 * Recorte "com proposta" para a intercalação = tem proposta PENDENTE de classe
 * de PRESENÇA de tipo VISÍVEL — a única que é pré-selecionada (ausência nunca
 * é; tipo escondido nunca é). Sem isto o recorte entrava no braço "propostas"
 * sem nada marcado e o "Enter confirma" mentia. Mesma regra de nome do filtro
 * por classe (`nomesDeClasseDosTipos`/`lacunasDosTipos`).
 *
 * Item sem `pending_proposal_classes` (API antiga) cai na contagem — a regra
 * degrada para "tem proposta pendente", nunca para "não tem".
 */
export function temProposta(
  f: ItemComProposta,
  tipos: readonly EpiTypeDef[] = EPI_TYPES,
  presenca: ReadonlySet<string> = nomesDePresencaDosTipos(tipos),
): boolean {
  if (Array.isArray(f.pending_proposal_classes)) {
    return f.pending_proposal_classes.some(c => presenca.has(normParaComparar(c)))
  }
  return (f.pending_proposals_count ?? 0) > 0
}

/**
 * Intercala a fila: `normais` recortes sem proposta, depois `propostas` com
 * proposta, e repete. Ordem RELATIVA dentro de cada grupo é preservada (a
 * carência continua mandando dentro do grupo); nada é perdido nem duplicado.
 * Quando um grupo acaba, o resto do outro vem em sequência. `null`, ou os
 * dois números zerados, devolvem a fila como está.
 *
 * `prefixo` = o que já está congelado antes da fila (visto + recorte na tela):
 * a cadência CONTINUA de onde o prefixo parou — se ele termina com 2 normais
 * de um bloco de 5, a cauda abre com 3 normais, não com 5. Sem isto cada
 * reordenação (matriz chegando, lote novo) reiniciava a fase e o primeiro
 * bloco saía com até 2N-1 recortes.
 *
 * `tipos` = tipos NA TELA: decide quem conta como "com proposta" (temProposta).
 *
 * Cadência inválida (lixo de localStorage/<select>, ou um lado em 0) =
 * fila como está — ver cadenciaValida. Com n, m ≥ 1 o while SEMPRE avança.
 *
 * ponytail: só mexe no que JÁ está na fila local; se as propostas se
 * concentrarem longe do cursor do servidor, o upgrade é buscar o braço de
 * propostas com ?pending_review=true em paralelo.
 */
export function intercalar<T extends ItemComProposta>(
  fila: readonly T[],
  cadencia: Cadencia | null | undefined,
  prefixo: readonly T[] = [],
  tipos: readonly EpiTypeDef[] = EPI_TYPES,
): T[] {
  const c = cadenciaValida(cadencia)
  if (!c) return [...fila]
  const { normais: n, propostas: m } = c
  const presenca = nomesDePresencaDosTipos(tipos)
  const ehProposta = (f: T) => temProposta(f, tipos, presenca)

  const normais = fila.filter(f => !ehProposta(f))
  const propostas = fila.filter(ehProposta)
  const saida: T[] = []
  let i = 0
  let j = 0

  // Fase herdada: quantos do bloco em curso no fim do prefixo ainda faltam.
  let cotaN0 = n
  let cotaP0 = 0
  if (prefixo.length > 0) {
    const ultimoEhProposta = ehProposta(prefixo[prefixo.length - 1])
    let corrida = 0
    for (let k = prefixo.length - 1; k >= 0 && ehProposta(prefixo[k]) === ultimoEhProposta; k--) corrida++
    if (ultimoEhProposta) cotaP0 = Math.max(0, m - corrida)
    else cotaN0 = Math.max(0, n - corrida)
  }
  for (let k = 0; k < cotaP0 && j < propostas.length; k++) saida.push(propostas[j++])

  let primeiro = true
  while (i < normais.length || j < propostas.length) {
    // Grupo oposto esgotado → despeja o resto deste de uma vez.
    const cotaN = j >= propostas.length ? Infinity : primeiro ? cotaN0 : n
    const cotaP = i >= normais.length ? Infinity : m
    primeiro = false
    for (let k = 0; k < cotaN && i < normais.length; k++) saida.push(normais[i++])
    for (let k = 0; k < cotaP && j < propostas.length; k++) saida.push(propostas[j++])
  }
  return saida
}

/**
 * `reordenarCauda` + intercalação da mesma cauda, com a fase herdada do
 * prefixo congelado (já visto + recorte na tela). `cadencia` null = idêntico
 * a `reordenarCauda`.
 */
export function reordenarCaudaIntercalada<T extends { camera_id: string | null } & ItemComProposta>(
  fila: readonly T[],
  corte: number,
  gaps: readonly LacunaCobertura[],
  cadencia: Cadencia | null | undefined,
  tipos: readonly EpiTypeDef[] = EPI_TYPES,
): T[] {
  const limite = Math.max(0, Math.min(corte, fila.length))
  const base = reordenarCauda(fila, corte, gaps)
  const prefixo = base.slice(0, limite)
  return [...prefixo, ...intercalar(base.slice(limite), cadencia, prefixo, tipos)]
}

/**
 * Nº (1-based) do bloco de propostas em que a posição `index` cai; 0 = recorte
 * normal. Derivado da FILA, não de um contador: Backspace/desfazer voltam à
 * mesma posição → mesmo bloco, e o prefixo já visto nunca muda de número
 * (reordenarCauda só mexe depois do corte). É a chave da aceitação por lote.
 */
export function numeroDoBloco<T extends ItemComProposta>(
  fila: readonly T[],
  index: number,
  tipos: readonly EpiTypeDef[] = EPI_TYPES,
): number {
  const presenca = nomesDePresencaDosTipos(tipos)
  const ehProposta = (f: T) => temProposta(f, tipos, presenca)
  if (index < 0 || index >= fila.length || !ehProposta(fila[index])) return 0
  let bloco = 0
  for (let i = 0; i <= index; i++) {
    if (ehProposta(fila[i]) && (i === 0 || !ehProposta(fila[i - 1]))) bloco++
  }
  return bloco
}
