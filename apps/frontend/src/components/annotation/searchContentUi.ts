/**
 * searchContentUi — lógica pura da "busca por conteúdo" (termos prontos de
 * EPI → payload da API, fase do job de GPU → texto de gente, agrupamento de
 * achados por termo, ressurgimento pós-reload). Zero dependência de
 * React/DOM, pra ser testável sem harness de componente — mesmo padrão de
 * propagationUi.ts (ver ../../test/components/annotation/searchContentUi.test.ts).
 *
 * `formatUsd`/`formatElapsed` são puramente formatação (sem acoplamento ao
 * shape de PropagationJob) — reaproveitados de propagationUi.ts em vez de
 * duplicados; o resto (fase do job, ressurgimento) é duplicado de propósito
 * porque SearchJob e PropagationJob têm shapes/vocabulários diferentes e
 * generalizar mapJobToPhase/pickJobToResurface pra cobrir os dois seria
 * invasivo pro código já em produção da propagação semeada.
 */
import type { SearchFinding, SearchIneligibleFrame, SearchJob, SearchPreflight, SearchTerm } from '../../services/searchService'

// ── termos prontos de EPI ────────────────────────────────────────────────
//
// `query` é o termo em inglês que de fato vai pro modelo (ele entende
// inglês melhor) — o usuário nunca precisa saber disso, só vê o rótulo
// pt-BR marcado; a query aparece pequena/muted ao lado só como transparência.

export interface ReadyTerm {
  key: string
  labelPt: string
  query: string
}

export const READY_TERMS: ReadyTerm[] = [
  { key: 'capacete', labelPt: 'capacete', query: 'safety helmet' },
  { key: 'oculos', labelPt: 'óculos de proteção', query: 'safety goggles' },
  { key: 'luva', labelPt: 'luva', query: 'glove' },
  { key: 'colete', labelPt: 'colete refletivo', query: 'high-visibility safety vest' },
  { key: 'protetor_auricular', labelPt: 'protetor auricular', query: 'hearing protection ear muffs' },
  { key: 'mascara', labelPt: 'máscara', query: 'face mask' },
  { key: 'bota', labelPt: 'bota', query: 'safety boots' },
]

/** `_MAX_TERMS` de search_handlers.py::_parse_terms — o preflight/create
 * rejeitam (400) acima disso; a UI trava a adição antes de chegar lá. */
export const MAX_TERMS_PER_JOB = 12

/**
 * Monta o payload `terms` da API a partir dos termos prontos marcados +
 * termos livres digitados (chips). Dedupe por LABEL (case-insensitive) —
 * é a constraint real do backend (`_parse_terms`: "term.label duplicado"
 * rejeita o payload inteiro com 400) — e também por query, pra não pagar
 * duas vezes pela mesma busca em inglês sob rótulos diferentes. Ordem:
 * termos prontos (na ordem de READY_TERMS) primeiro, depois os livres na
 * ordem em que foram adicionados.
 */
export function buildSearchTerms(
  selectedReadyKeys: ReadonlySet<string>,
  freeTerms: readonly string[],
): SearchTerm[] {
  const terms: SearchTerm[] = []
  const seenLabels = new Set<string>()
  const seenQueries = new Set<string>()

  const tryAdd = (label: string, query: string) => {
    const labelKey = label.toLowerCase()
    const queryKey = query.toLowerCase()
    if (seenLabels.has(labelKey) || seenQueries.has(queryKey)) return
    seenLabels.add(labelKey)
    seenQueries.add(queryKey)
    terms.push({ label, query })
  }

  for (const t of READY_TERMS) {
    if (selectedReadyKeys.has(t.key)) tryAdd(t.labelPt, t.query)
  }

  for (const raw of freeTerms) {
    const term = raw.trim()
    if (term) tryAdd(term, term)
  }

  return terms
}

/** Motivo do botão "Buscar" estar desabilitado — `null` quando liberado.
 * Ordem importa: nuvem desabilitada (409 do preflight, SEARCH_CLOUD_ALLOWED_DATES
 * ausente) tem prioridade sobre qualquer outro estado; depois termos vazios
 * (nem faz sentido olhar o preflight sem termo nenhum); só então os gates
 * do próprio preflight (mesmos dois flags de propagationUi.disabledReason —
 * `runpod_configured`/`third_party_cloud_enabled`, ADR-0047/0060). */
export function searchSubmitDisabledReason(
  termsCount: number,
  preflight: SearchPreflight | null,
  cloudDisabled: boolean,
): string | null {
  if (cloudDisabled) return 'busca em nuvem desabilitada neste tenant'
  if (termsCount === 0) return 'marque ao menos um termo pronto ou digite um termo livre'
  if (!preflight) return 'calculando custo…'
  if (!preflight.runpod_configured) return 'busca em nuvem não configurada'
  if (!preflight.third_party_cloud_enabled) {
    return 'envio para nuvem externa não autorizado neste tenant'
  }
  if (preflight.eligible_count === 0) {
    return 'nenhuma das imagens selecionadas é elegível para a busca em nuvem'
  }
  if (preflight.gpu.price_error) return 'não foi possível estimar o custo — tente de novo'
  return null
}

// `reason` de search_cloud_guard.py::classify_frame_eligibility é um código
// snake_case pra máquina, não uma frase — traduzido aqui pro pt-BR que o
// painel mostra. Fallback: código cru (nunca esconde um motivo novo do
// backend atrás de um texto genérico).
const INELIGIBLE_REASON_LABELS: Record<string, string> = {
  frame_not_found: 'imagem não encontrada',
  missing_r2_key: 'imagem sem arquivo salvo',
  missing_captured_at: 'imagem sem data de captura registrada',
  date_not_allowed: 'fora das datas liberadas para busca em nuvem',
}

export function ineligibleReasonLabel(reason: string): string {
  return INELIGIBLE_REASON_LABELS[reason] ?? reason
}

export interface IneligibleSummary {
  /** já traduzido pt-BR (ver ineligibleReasonLabel) — pronto pra exibir. */
  reason: string
  count: number
}

/** Agrupa `preflight.ineligible` por motivo (frame_id não é legível pro
 * usuário — o que importa é "quantas e por quê"). Agrupa pelo código cru
 * (nunca por texto traduzido — dois códigos diferentes nunca deveriam
 * colidir só porque a tradução ficou parecida) e só traduz no resultado. */
export function summarizeIneligible(
  ineligible: readonly Pick<SearchIneligibleFrame, 'reason'>[],
): IneligibleSummary[] {
  const order: string[] = []
  const counts = new Map<string, number>()
  for (const item of ineligible) {
    const reason = item.reason || 'unknown'
    if (!counts.has(reason)) order.push(reason)
    counts.set(reason, (counts.get(reason) ?? 0) + 1)
  }
  return order.map(reason => ({ reason: ineligibleReasonLabel(reason), count: counts.get(reason) ?? 0 }))
}

// ── fase do job (barra de status) ────────────────────────────────────────

export interface SearchPhaseCounter {
  done: number
  total: number
}

export interface SearchPhase {
  key: string
  label: string
  /** Detalhe expansível (error_reason bruto em falha). */
  detail?: string
  counter?: SearchPhaseCounter
  terminal: boolean
  failed: boolean
}

// Vocabulário REAL hoje: dispatch (tasks/search.py) emite 'preparing' →
// 'creating_pod' → 'gpu_starting'; o executor (training/search_content.py)
// emite 'manifest' → 'deps' → 'model' → 'searching' (com frames_processed/
// frames_total) → 'done' (mandado JUNTO do status='completed' final, nunca
// visto por aqui — o branch `status === 'completed'` já retornou antes).
// Casamento por regex (não por lista fechada) porque o contrato desta task
// não fixa um enum e "executor pode variar" é a mesma cautela de
// propagationUi.ts — nunca trava a barra por um nome de stage novo.
const QUEUE_STAGE_RE = /queue|prepar|wait/i
const GPU_STAGE_RE = /pod|gpu|boot|creat/i
const LOADING_MODEL_STAGE_RE = /manifest|deps|model|weight/i
const SEARCHING_STAGE_RE = /search|infer|process|run|frame|scan/i

// Mesmo mapeamento de propagationUi.ts::FAILURE_LABELS — `failure_kind` é
// gravado por tasks/search.py::_record_failure_metrics com o MESMO
// vocabulário de tasks/propagation.py (cost_cap/timeout/pod_died/stopped);
// 'executor_error' (fallback genérico) fica sem label conhecido de propósito
// — cai no `error_reason` cru como detalhe expansível.
const FAILURE_LABELS: Record<string, string> = {
  cost_cap: 'a busca passou do limite de custo e foi interrompida',
  timeout: 'a busca demorou mais que o permitido',
  pod_died: 'a máquina de GPU falhou',
  stopped: 'busca interrompida',
}

function findingsLabel(count: number): string {
  const n = Number.isFinite(count) ? count : 0
  return `${n} achado${n === 1 ? '' : 's'} encontrado${n === 1 ? '' : 's'}`
}

export function mapSearchJobToPhase(job: SearchJob): SearchPhase {
  if (job.status === 'completed') {
    return { key: 'completed', label: findingsLabel(job.findings_count), terminal: true, failed: false }
  }

  if (job.status === 'stopped') {
    return { key: 'stopped', label: 'busca interrompida', terminal: true, failed: false }
  }

  if (job.status === 'failed') {
    const kind = job.metrics?.failure_kind
    if (kind === 'stopped') {
      return { key: 'stopped', label: 'busca interrompida', terminal: true, failed: true }
    }
    const known = kind != null && Object.prototype.hasOwnProperty.call(FAILURE_LABELS, kind)
    return {
      key: 'failed',
      label: known ? FAILURE_LABELS[kind as string] : 'a busca falhou',
      detail: known ? undefined : job.error_reason ?? undefined,
      terminal: true,
      failed: true,
    }
  }

  // queued / running — fases intermediárias por metrics.stage
  const stage = job.metrics?.stage
  if (job.status === 'queued' || !stage || QUEUE_STAGE_RE.test(stage)) {
    return { key: 'queued', label: 'Na fila', terminal: false, failed: false }
  }
  if (GPU_STAGE_RE.test(stage)) {
    return {
      key: 'gpu_starting',
      label: 'Iniciando máquina de GPU (~2 a 4 min na primeira vez)',
      terminal: false,
      failed: false,
    }
  }
  if (LOADING_MODEL_STAGE_RE.test(stage)) {
    return {
      key: 'loading_model',
      label: 'Carregando modelo na GPU (ainda pode levar minutos)',
      terminal: false,
      failed: false,
    }
  }
  if (SEARCHING_STAGE_RE.test(stage)) {
    const total = job.metrics?.frames_total ?? job.selected_frame_ids?.length
    const done = job.metrics?.frames_processed
    const counter =
      typeof total === 'number' && total > 0 && typeof done === 'number' ? { done, total } : undefined
    return { key: 'searching', label: 'Buscando nas imagens', counter, terminal: false, failed: false }
  }

  // stage desconhecido (executor pode variar) — nunca quebra a barra
  return { key: 'unknown', label: 'Processando', terminal: false, failed: false }
}

// ── agrupamento de achados por termo (visão de resultados) ──────────────

export interface FindingGroup {
  term: string
  label: string
  /** índices em `SearchJob.results` — é o que promoteFindings espera. */
  indices: number[]
  /** imagens distintas onde o termo apareceu (um frame pode ter >1 achado). */
  frameCount: number
  avgConfidence: number
}

export function groupFindings(results: readonly SearchFinding[]): FindingGroup[] {
  const order: string[] = []
  const byTerm = new Map<
    string,
    { label: string; indices: number[]; frames: Set<string>; confidenceSum: number }
  >()

  results.forEach((finding, index) => {
    if (!byTerm.has(finding.term)) {
      order.push(finding.term)
      byTerm.set(finding.term, { label: finding.label, indices: [], frames: new Set(), confidenceSum: 0 })
    }
    const group = byTerm.get(finding.term)!
    group.indices.push(index)
    group.frames.add(finding.frame_id)
    group.confidenceSum += finding.confidence
  })

  return order.map(term => {
    const group = byTerm.get(term)!
    return {
      term,
      label: group.label,
      indices: group.indices,
      frameCount: group.frames.size,
      avgConfidence: group.indices.length > 0 ? group.confidenceSum / group.indices.length : 0,
    }
  })
}

// ── ressurgimento pós-reload ─────────────────────────────────────────────
//
// Mesma lógica de propagationUi.ts (job ATIVO sempre ressurge; job TERMINAL
// recente ressurge até dispensado) — duplicada com prefixo/namespace próprio
// porque SearchJob não é PropagationJob (proposals_count vs findings_count,
// metrics com shape diferente) e generalizar pickJobToResurface pra aceitar
// os dois shapes seria mais código do que duplicar estas ~15 linhas.

const SEARCH_DISMISSED_PREFIX = 'search_dismissed:'
const RECENT_TERMINAL_MS = 24 * 60 * 60 * 1000

export function isSearchJobDismissed(jobId: string): boolean {
  try {
    return localStorage.getItem(`${SEARCH_DISMISSED_PREFIX}${jobId}`) != null
  } catch {
    return false
  }
}

export function dismissSearchJob(jobId: string): void {
  try {
    localStorage.setItem(`${SEARCH_DISMISSED_PREFIX}${jobId}`, String(Date.now()))
  } catch {
    // sem localStorage (teste/SSR) — dispensa só não persiste
  }
}

export function pickSearchJobToResurface(jobs: SearchJob[]): SearchJob | null {
  const byNewest = [...jobs].sort((a, b) => {
    const ta = a.created_at ? new Date(a.created_at).getTime() : 0
    const tb = b.created_at ? new Date(b.created_at).getTime() : 0
    return tb - ta
  })
  const active = byNewest.find(j => j.status === 'queued' || j.status === 'running')
  if (active) return active
  for (const job of byNewest) {
    const created = job.created_at ? new Date(job.created_at).getTime() : NaN
    if (Number.isNaN(created) || Date.now() - created > RECENT_TERMINAL_MS) continue
    if (!isSearchJobDismissed(job.id)) return job
  }
  return null
}
