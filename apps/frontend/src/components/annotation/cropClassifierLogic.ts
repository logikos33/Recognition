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
    key: 'oculos',
    label: 'Óculos',
    states: [
      { key: 'presente', label: 'Presente', kind: 'presente', classNameCandidates: ['Óculos', 'óculos'] },
      { key: 'ausente', label: 'Ausente', kind: 'ausente', classNameCandidates: ['Sem óculos'] },
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
 */
export function buildApprovalPayload(
  verdict: Verdict,
  bbox: readonly [number, number, number, number],
  classes: RuntimeClass[],
  moduleCode = 'epi',
): ApprovalResult {
  const { x_center, y_center, width, height } = bboxToCenterForm(bbox)
  const payload: AnnotationBoxPayload[] = []
  const missing: MissingClass[] = []

  for (const type of EPI_TYPES) {
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
 * Tipos das 5 classes prioritárias da campanha: mascara · Sem mascara ·
 * Uso incorreto de mascara · Protetor auditivo · Sem protetor de ouvido.
 * Todas caem em dois tipos de EPI — daí o modo estreito ser tão barato.
 */
export const TIPOS_PRIORITARIOS = ['mascara', 'auditiva'] as const

/**
 * Modo estreito: esconde da TELA os tipos fora da prioridade.
 *
 * ⛔ Não filtra o banco e não apaga nada: as demais classes seguem existindo,
 * anotáveis a qualquer momento com o modo desligado. O que muda é só quanto o
 * humano precisa ler por recorte — e ler menos é o ganho.
 */
export function tiposVisiveis(modoEstreito: boolean): EpiTypeDef[] {
  if (!modoEstreito) return EPI_TYPES
  return EPI_TYPES.filter(t => (TIPOS_PRIORITARIOS as readonly string[]).includes(t.key))
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
export function vereditoInicialDaProposta(sugeridos: ReadonlySet<string>): Verdict {
  const inicial: Verdict = {}
  for (const chave of sugeridos) {
    const [typeKey, stateKey] = chave.split(':')
    if (typeKey && stateKey) inicial[typeKey] = stateKey
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
 * nem erro dele, e incluí-lo inflaria a taxa artificialmente.
 */
export function medirAceitacao(
  proposta: ReadonlySet<string>,
  final: Verdict,
): AceitacaoProposta[] {
  const saida: AceitacaoProposta[] = []
  for (const chave of proposta) {
    const [typeKey, stateKey] = chave.split(':')
    if (!typeKey || !stateKey) continue
    saida.push({ classe: `${typeKey}:${stateKey}`, aceita: final[typeKey] === stateKey })
  }
  return saida
}
