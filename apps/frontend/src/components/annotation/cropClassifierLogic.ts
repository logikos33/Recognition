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
      { key: 'uso_incorreto', label: 'Uso incorreto', kind: 'uso_incorreto', classNameCandidates: ['Uso incorreto'] },
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
  for (const candidate of candidates) {
    const hit = classes.find(c => normName(c.name) === normName(candidate))
    if (hit) return hit.classId
  }
  return null
}

export function findState(typeKey: string, stateKey: string): EpiStateOption | null {
  const type = EPI_TYPES.find(t => t.key === typeKey)
  return type?.states.find(s => s.key === stateKey) ?? null
}

export interface AnnotationBoxPayload {
  class_id: number
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
    const classId = resolveClassId(state.classNameCandidates, classes)
    if (classId != null) {
      payload.push({ class_id: classId, x_center, y_center, width, height })
    } else {
      missing.push({
        typeKey: type.key,
        typeLabel: type.label,
        stateKey: state.key,
        stateLabel: state.label,
        candidates: state.classNameCandidates,
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
