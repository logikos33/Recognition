/**
 * propagationUi — lógica pura da UI de "buscar imagens iguais" (propagação
 * semeada, RunPod): mapeamento de fase→texto de gente, motivo de
 * desabilitado do CTA, formatação de custo/tempo decorrido.
 *
 * Zero dependência de React/DOM — só dados de/para `propagationService`,
 * pra ser testável sem harness de componente (ver
 * ../../test/components/annotation/propagationUi.test.ts).
 */
import type { PropagationJob, PropagationPreflight } from '../../services/propagationService'

export interface PhaseCounter {
  done: number
  total: number
}

export interface PropagationPhase {
  key: string
  label: string
  /** Detalhe expansível (ex.: `error_reason` bruto em falha não classificada). */
  detail?: string
  counter?: PhaseCounter
  terminal: boolean
  failed: boolean
}

const PREPARING_STAGES = new Set(['preparing'])
const GPU_STARTING_STAGES = new Set(['creating_pod', 'gpu_starting'])
const LOADING_MODEL_STAGES = new Set(['manifest', 'deps', 'weights'])
const SEED_STAGES = new Set(['seed_exemplars'])
// 'propagate'/'finalize' são os nomes do contrato original; 'pool'/'done'
// são os nomes REAIS emitidos pelo executor (training/propagate_seeded.py)
// — o dispatch (tasks/propagation.py) usa outro vocabulário ainda
// ('preparing', 'creating_pod'). Os dois lados de cada par levam à mesma
// fase pro usuário; "executor pode variar" (spec) — nunca travar por causa
// de um nome de stage diferente.
const PROPAGATE_STAGES = new Set(['propagate', 'pool'])
const FINALIZE_STAGES = new Set(['finalize', 'done'])

const FAILURE_LABELS: Record<string, string> = {
  cost_cap: 'a busca passou do limite de custo e foi interrompida',
  timeout: 'a busca demorou mais que o permitido',
  pod_died: 'a máquina de GPU falhou',
  stopped: 'busca interrompida',
}

function proposalsLabel(count: number): string {
  const n = Number.isFinite(count) ? count : 0
  return `${n} proposta${n === 1 ? '' : 's'} encontrada${n === 1 ? '' : 's'}`
}

/**
 * Mapa fase→nome de gente. `job.metrics.stage` só existe enquanto
 * queued/running (o dispatch grava o primeiro stage ANTES de qualquer
 * guard — cold start do pod dura minutos sem nenhum callback do executor,
 * ver tasks/propagation.py); status terminal (completed/failed/stopped)
 * decide sozinho, sem olhar stage (exceto `failure_kind`, que só existe
 * dentro de 'failed').
 */
export function mapJobToPhase(job: PropagationJob): PropagationPhase {
  if (job.status === 'completed') {
    return {
      key: 'completed',
      label: proposalsLabel(job.proposals_count),
      terminal: true,
      failed: false,
    }
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
  if (job.status === 'queued' || !stage || PREPARING_STAGES.has(stage)) {
    return { key: 'preparing', label: 'Preparando referências', terminal: false, failed: false }
  }
  if (GPU_STARTING_STAGES.has(stage)) {
    return {
      key: 'gpu_starting',
      label: 'Iniciando máquina de GPU (~2 a 4 min na primeira vez)',
      terminal: false,
      failed: false,
    }
  }
  if (LOADING_MODEL_STAGES.has(stage)) {
    return {
      key: 'loading_model',
      label: 'Carregando modelo na GPU (ainda pode levar minutos)',
      terminal: false,
      failed: false,
    }
  }
  if (SEED_STAGES.has(stage)) {
    return {
      key: 'seed_exemplars',
      label: 'Preparando referências na GPU',
      terminal: false,
      failed: false,
    }
  }
  if (PROPAGATE_STAGES.has(stage)) {
    const total = job.metrics?.frames_total
    const done = job.metrics?.frames_processed
    const counter =
      typeof total === 'number' && typeof done === 'number' ? { done, total } : undefined
    return { key: 'propagate', label: 'Analisando imagens', counter, terminal: false, failed: false }
  }
  if (FINALIZE_STAGES.has(stage)) {
    return { key: 'finalize', label: 'Recebendo propostas', terminal: false, failed: false }
  }

  // stage desconhecido (executor pode variar) — nunca quebra a barra
  return { key: 'unknown', label: 'Processando', terminal: false, failed: false }
}

/**
 * Motivo do CTA "Iniciar busca" estar desabilitado — `null` quando
 * liberado. Ordem importa (hasBoxes é checado ANTES de qualquer campo do
 * preflight — não faz sentido preflight sem sementes desenhadas).
 */
export function disabledReason(hasBoxes: boolean, preflight: PropagationPreflight): string | null {
  if (!hasBoxes) return 'desenhe ao menos uma caixa para usar como referência'
  if (!preflight.runpod_configured) return 'treino em nuvem não configurado'
  if (!preflight.third_party_cloud_enabled) {
    return 'envio para nuvem externa não autorizado neste tenant'
  }
  if (preflight.active_job) return 'busca em andamento'
  return null
}

export function formatUsd(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `US$ ${value.toFixed(2)}`
}

/** mm:ss decorridos desde `startIso` até agora — usado pela barra de
 * status enquanto o job está em andamento. */
export function formatElapsed(startIso: string | null | undefined): string {
  if (!startIso) return '00:00'
  const start = new Date(startIso).getTime()
  if (Number.isNaN(start)) return '00:00'
  const totalSeconds = Math.max(0, Math.floor((Date.now() - start) / 1000))
  const mm = Math.floor(totalSeconds / 60)
  const ss = totalSeconds % 60
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}
