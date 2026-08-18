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
